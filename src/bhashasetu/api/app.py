"""FastAPI application.

Design notes that matter for the editor:

* Every offset in the response indexes the text the client **sent**, not the
  normalized text. Stage 0 can change length, so the two coordinate systems
  diverge; `_remap_to_original` converts before serializing. `normalized` and
  `normalizedDiffers` are still reported, for display, but the client never has
  to reconcile coordinates.
* Checking is CPU-bound and synchronous. Handlers are `def`, not `async def`, so
  Starlette runs them in the threadpool instead of blocking the event loop —
  the opposite of the usual advice, and correct here.
* Rate limiting is per `deviceId` (spec §5, §6.2). In-process and approximate;
  Redis replaces it in Phase 3 when there is more than one worker.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import replace
from typing import Annotated, Any

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from bhashasetu import __version__
from bhashasetu.api.models import (
    CheckRequest,
    CheckResponse,
    ConvertRequest,
    ConvertResponse,
    ErrorClassOut,
    IdentityOut,
    LanguageOut,
    RecoveryOut,
)
from bhashasetu.core.identity import generate_recovery_phrase, new_device_id
from bhashasetu.core.pipeline import Pipeline, PipelineConfig
from bhashasetu.core.registry import UnknownLanguageError, available, get_pack
from bhashasetu.core.storage import FORCE_TIER
from bhashasetu.core.types import (
    CATEGORY_OF,
    CheckResult,
    Edit,
    NormalizationResult,
)

DEVICE_COOKIE = "bhashasetu_device"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2  # 2 years, per spec §5

RATE_LIMIT_REQUESTS = 120
RATE_LIMIT_WINDOW_S = 60.0

_hits: dict[str, deque[float]] = defaultdict(deque)


def _rate_limit(device_id: str) -> None:
    now = time.monotonic()
    window = _hits[device_id]
    while window and now - window[0] > RATE_LIMIT_WINDOW_S:
        window.popleft()
    if len(window) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"rate limit: {RATE_LIMIT_REQUESTS} requests per minute per device",
            headers={"Retry-After": str(int(RATE_LIMIT_WINDOW_S))},
        )
    window.append(now)


def device_id_dep(
    response: Response,
    bhashasetu_device: Annotated[str | None, Cookie(alias=DEVICE_COOKIE)] = None,
) -> str:
    """Anonymous identity (spec §5).

    No login. The cookie is httpOnly so script cannot read it; the frontend keeps
    its own copy in localStorage, and the two are reconciled client-side. Either
    surviving is enough to keep a streak alive.
    """
    device_id = bhashasetu_device or new_device_id()
    response.set_cookie(
        DEVICE_COOKIE,
        device_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    _rate_limit(device_id)
    return device_id


def _remap_to_original(result: CheckResult, norm: NormalizationResult) -> CheckResult:
    """Rewrite every edit span from normalized offsets to original offsets."""
    if not norm.applied_rules:
        return result  # nothing moved

    def remap(edit: Edit) -> Edit:
        start, end = norm.to_original_span(edit.start, edit.end)
        return replace(edit, start=start, end=end)

    return replace(
        result,
        edits=[remap(e) for e in result.edits],
        suppressed=[remap(e) for e in result.suppressed],
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="BhashaSetu",
        version=__version__,
        description=(
            "Bengali grammar and writing assistant. No login, no signup, every "
            "feature free. Stages 0-1 of the 5-stage pipeline are implemented; "
            "stages 2-4 report as skipped rather than returning empty results."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        # Dev only. Phase 6 pins this to the deployed origin.
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _pack(code: str) -> Any:
        try:
            return get_pack(code)
        except UnknownLanguageError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/languages", response_model=list[LanguageOut])
    def languages() -> list[LanguageOut]:
        out: list[LanguageOut] = []
        for code in available():
            pack = _pack(code)
            out.append(
                LanguageOut(
                    code=pack.code,
                    nameEn=pack.name_en,
                    nameNative=pack.name_native,
                    lexiconSize=pack.lexicon.size,
                    dictionary=(
                        "hunspell"
                        if type(pack.lexicon).__name__ == "HunspellLexicon"
                        else "seed"
                    ),
                )
            )
        return out

    @app.get("/api/classes", response_model=list[ErrorClassOut])
    def classes(language: str = "bn") -> list[ErrorClassOut]:
        pack = _pack(language)
        return [
            ErrorClassOut(
                code=code.value,
                category=spec.category,
                label_native=spec.label_native,
                label_en=spec.label_en,
                ruleReference=spec.rule_reference,
                implementedAtStage=spec.implemented_at_stage,
            )
            for code, spec in pack.error_classes.items()
        ]

    @app.post("/api/check", response_model=CheckResponse)
    def check(
        body: CheckRequest,
        device_id: Annotated[str, Depends(device_id_dep)],
    ) -> CheckResponse:
        pack = _pack(body.language)
        pipeline = Pipeline(pack, PipelineConfig(min_confidence=body.min_confidence))
        result = pipeline.check(body.text)

        # Map every span from normalized coordinates back onto the text the
        # caller actually sent.
        #
        # Stage 0 changes length: composing `ড + ়` into `ড়` removes a character,
        # so an edit at offset 40 of the normalized text is at offset 41 of the
        # original if one nukta was composed before it. Handing back normalized
        # offsets makes a client's replacement land one character early and eat
        # the preceding space — which is exactly what happened the first time
        # this ran in a browser.
        #
        # `NormalizationResult.offset_map` exists for this. The alternative,
        # having the client adopt the normalized text, would reset the caret on
        # every keystroke that produces a decomposed sequence — which on a
        # Bengali keyboard is most of them.
        norm = pack.normalizer.normalize(body.text)
        applied_rules = norm.applied_rules
        result = _remap_to_original(result, norm)

        readability = None
        missing: list[str] = []
        if body.include_readability and result.normalized.strip():
            readability = pack.readability.score(result.normalized, result.sentences)
            missing = list(getattr(pack.readability, "components_missing", []))

        # Computed on the ORIGINAL text, so no coordinate remapping is needed
        # and a normalization that changes length cannot shift the highlight.
        out_of_scope = (
            pack.out_of_scope(body.text) if hasattr(pack, "out_of_scope") else []
        )

        return CheckResponse.of(
            result,
            {k.value: v for k, v in CATEGORY_OF.items()},
            include_suppressed=body.include_suppressed,
            readability=readability,
            readability_missing=missing,
            applied_rules=applied_rules,
            out_of_scope=out_of_scope,
        )

    @app.post("/api/convert/bijoy", response_model=ConvertResponse)
    def convert_bijoy_route(body: ConvertRequest) -> ConvertResponse:
        """Bijoy/ANSI -> Unicode.

        Detection is complete; conversion refuses below 95% table coverage, so
        this reliably answers "is this Bijoy?" and only sometimes answers
        "here it is in Unicode". Completing the table is Phase 4 — a partial
        table produces convincing garbage, which is worse than saying no.
        """
        from bhashasetu.language_packs.bn.bijoy import (
            convert_bijoy,
            coverage,
            looks_like_bijoy,
        )

        detected = looks_like_bijoy(body.text)
        cov = coverage(body.text)
        converted_text = convert_bijoy(body.text) if detected else body.text
        did_convert = converted_text != body.text
        note = None
        if detected and not did_convert:
            note = (
                f"Detected as Bijoy, but the glyph table covers only {cov:.0%} of "
                "this text and conversion needs 95%. Completing the table is a "
                "Phase 4 task; a partial table would produce plausible-looking "
                "nonsense rather than a partial conversion."
            )
        return ConvertResponse(
            text=converted_text,
            detected=detected,
            coverage=round(cov, 4),
            converted=did_convert,
            note=note,
        )

    @app.get("/api/identity", response_model=IdentityOut)
    def identity(device_id: Annotated[str, Depends(device_id_dep)]) -> IdentityOut:
        # Spec §2: entitlement plumbing exists, everyone is free_unlimited.
        return IdentityOut(deviceId=device_id, tier=FORCE_TIER or "free")

    @app.post("/api/identity/recovery", response_model=RecoveryOut)
    def recovery(device_id: Annotated[str, Depends(device_id_dep)]) -> RecoveryOut:
        """Mint a 12-word recovery phrase.

        Returns the phrase once and never again. Only the HMAC is storable, and
        persisting it belongs with the rest of the storage layer in Phase 3 —
        this route currently mints without saving, which the UI states plainly
        rather than implying the progress is already safe.
        """
        phrase, _secret_hash = generate_recovery_phrase()
        return RecoveryOut(phrase=phrase, words=len(phrase.split()))

    return app


app = create_app()
