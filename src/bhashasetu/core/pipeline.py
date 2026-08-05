"""The 5-stage cascading pipeline.

Stage 0  NORMALIZE   implemented (Phase 1)
Stage 1  LEXICAL     implemented (Phase 1)
Stage 2  DETECT      BanglaBERT token classification  - Phase 2
Stage 3  CORRECT     BanglaT5 span-constrained seq2seq - Phase 2
Stage 4  REASON      LLMProvider                       - Phase 2

Stages 2-4 are absent, not stubbed-with-fake-output. `CheckResult.stage_reports`
records them as skipped so the eval harness never silently credits work that did
not happen.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from bhashasetu.core.protocols import LanguagePack
from bhashasetu.core.types import (
    CheckResult,
    Edit,
    ErrorClass,
    Sentence,
    StageReport,
)

_STAGE_NAMES: dict[int, str] = {
    0: "NORMALIZE",
    1: "LEXICAL",
    2: "DETECT",
    3: "CORRECT",
    4: "REASON",
}


@dataclass(slots=True)
class PipelineConfig:
    """Every threshold that shapes user-visible output lives here, not inline.

    `min_confidence` is the surface gate. Edits below it are returned in
    `CheckResult.suppressed` rather than dropped, so the eval harness can measure
    what a threshold change would cost before we ship it.
    """

    min_confidence: float = 0.55
    # Spec §1: escalate to stage 4 when stage 3 is not confident enough.
    escalate_below: float = 0.70
    max_suggestions: int = 5
    enabled_classes: frozenset[ErrorClass] | None = None
    # Cap on edits returned for a single request; protects the editor from
    # rendering ten thousand decorations on a pasted book.
    max_edits: int = 500


class Pipeline:
    def __init__(self, pack: LanguagePack, config: PipelineConfig | None = None) -> None:
        self.pack = pack
        self.config = config or PipelineConfig()

    def check(self, text: str) -> CheckResult:
        t0 = time.perf_counter()
        reports: list[StageReport] = []

        # --- Stage 0 --------------------------------------------------------
        s = time.perf_counter()
        norm = self.pack.normalizer.normalize(text)
        stage0_edits = list(norm.edits)
        reports.append(
            StageReport(0, _STAGE_NAMES[0], len(stage0_edits), _ms(s))
        )

        sentences = self.pack.tokenizer.sentences(norm.text)

        # --- Stages 1..N (whatever the pack registers) ----------------------
        collected: list[Edit] = list(stage0_edits)
        for detector in self.pack.detectors:
            s = time.perf_counter()
            found = detector.detect(norm.text, sentences)
            collected.extend(found)
            reports.append(
                StageReport(
                    detector.stage,
                    _STAGE_NAMES.get(detector.stage, f"STAGE_{detector.stage}"),
                    len(found),
                    _ms(s),
                )
            )

        for corrector in self.pack.correctors:
            s = time.perf_counter()
            collected = corrector.correct(norm.text, collected)
            reports.append(
                StageReport(
                    corrector.stage,
                    _STAGE_NAMES.get(corrector.stage, f"STAGE_{corrector.stage}"),
                    len(collected),
                    _ms(s),
                )
            )

        implemented = {r.stage for r in reports}
        for stage in (2, 3, 4):
            if stage not in implemented:
                reports.append(
                    StageReport(
                        stage,
                        _STAGE_NAMES[stage],
                        0,
                        0.0,
                        skipped_reason="not implemented until Phase 2",
                    )
                )
        reports.sort(key=lambda r: r.stage)

        kept, suppressed = self._resolve(collected)

        return CheckResult(
            language=self.pack.code,
            original=text,
            normalized=norm.text,
            edits=kept,
            suppressed=suppressed,
            sentences=sentences,
            stage_reports=reports,
            total_ms=_ms(t0),
        )

    # ------------------------------------------------------------------
    def _resolve(self, edits: list[Edit]) -> tuple[list[Edit], list[Edit]]:
        """Deduplicate overlapping edits and apply the confidence gate.

        Overlap policy: highest confidence wins; ties break toward the later
        (more informed) stage, then toward the shorter span. Two stages
        disagreeing about the same span is normal - showing the user both is not.
        """
        cfg = self.config
        allowed = cfg.enabled_classes

        candidates = [
            e for e in edits if allowed is None or e.error_class in allowed
        ]
        candidates.sort(key=lambda e: (-e.confidence, -e.stage, e.end - e.start, e.start))

        kept: list[Edit] = []
        suppressed: list[Edit] = []
        for edit in candidates:
            if any(edit.overlaps(k) for k in kept):
                suppressed.append(edit)
                continue
            if edit.confidence < cfg.min_confidence:
                suppressed.append(edit)
                continue
            if len(edit.suggestions) > cfg.max_suggestions:
                edit = _truncate_suggestions(edit, cfg.max_suggestions)
            kept.append(edit)

        kept.sort(key=lambda e: e.start)
        if len(kept) > cfg.max_edits:
            suppressed.extend(kept[cfg.max_edits :])
            kept = kept[: cfg.max_edits]
        return kept, suppressed


def _truncate_suggestions(edit: Edit, limit: int) -> Edit:
    from dataclasses import replace

    return replace(edit, suggestions=edit.suggestions[:limit])


def _ms(since: float) -> float:
    return (time.perf_counter() - since) * 1000.0


def new_edit_id() -> str:
    return uuid.uuid4().hex[:16]


def sentence_at(sentences: list[Sentence], offset: int) -> Sentence | None:
    for sent in sentences:
        if sent.start <= offset < sent.end:
            return sent
    return None
