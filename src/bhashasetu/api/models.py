"""Pydantic v2 request/response models.

Field names are camelCase on the wire to match the TypeScript `Edit` interface in
the spec, and snake_case in Python. `populate_by_name` lets both work.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from bhashasetu.core.types import CheckResult, Edit, OutOfScopeSpan


class _Wire(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class CheckRequest(_Wire):
    text: str = Field(max_length=200_000, description="Text to check")
    language: str = "bn"
    # Exposed so the UI can offer a "show low-confidence suggestions" toggle
    # without a second round trip.
    min_confidence: float = Field(default=0.55, ge=0.0, le=1.0, alias="minConfidence")
    include_suppressed: bool = Field(default=False, alias="includeSuppressed")
    include_readability: bool = Field(default=True, alias="includeReadability")


class EditOut(_Wire):
    id: str
    start: int
    end: int
    original: str
    suggestions: list[str]
    error_class: str = Field(alias="errorClass")
    category: str
    confidence: float
    stage: int
    explanation_bn: str
    explanation_en: str
    rule_reference: str | None = Field(default=None, alias="ruleReference")

    @classmethod
    def of(cls, edit: Edit, category: str) -> EditOut:
        return cls(
            id=edit.id,
            start=edit.start,
            end=edit.end,
            original=edit.original,
            suggestions=list(edit.suggestions),
            errorClass=edit.error_class.value,
            category=category,
            confidence=round(edit.confidence, 4),
            stage=edit.stage,
            explanation_bn=edit.explanation_bn,
            explanation_en=edit.explanation_en,
            ruleReference=edit.rule_reference,
        )


class StageOut(_Wire):
    stage: int
    name: str
    edits: int
    ms: float
    skipped: str | None = None


class OutOfScopeOut(_Wire):
    """Text the engine has no opinion about. Not an error — see scope.py."""

    start: int
    end: int
    text: str
    script: str


class SentenceOut(_Wire):
    index: int
    start: int
    end: int


class CheckResponse(_Wire):
    language: str
    normalized: str
    # True when Stage 0 rewrote the input. The editor needs to know, because
    # every offset below indexes the normalized text.
    normalized_differs: bool = Field(alias="normalizedDiffers")
    # Which Stage 0 rules fired. The editor shows these when it silently
    # rewrites the user's text, so a normalization is never invisible.
    applied_rules: list[str] = Field(default=[], alias="appliedRules")
    edits: list[EditOut]
    suppressed: list[EditOut] = []
    sentences: list[SentenceOut] = []
    out_of_scope: list[OutOfScopeOut] = Field(default=[], alias="outOfScope")
    stages: list[StageOut]
    stage_distribution: dict[int, int] = Field(alias="stageDistribution")
    total_ms: float = Field(alias="totalMs")
    readability: dict[str, float] | None = None
    readability_missing: list[str] = Field(default=[], alias="readabilityMissing")

    @classmethod
    def of(
        cls,
        result: CheckResult,
        categories: dict[str, str],
        *,
        include_suppressed: bool,
        readability: dict[str, float] | None,
        readability_missing: list[str],
        applied_rules: list[str],
        out_of_scope: list[OutOfScopeSpan],
    ) -> CheckResponse:
        return cls(
            language=result.language,
            normalized=result.normalized,
            normalizedDiffers=result.normalized != result.original,
            appliedRules=applied_rules,
            edits=[EditOut.of(e, categories[e.error_class.value]) for e in result.edits],
            suppressed=(
                [EditOut.of(e, categories[e.error_class.value]) for e in result.suppressed]
                if include_suppressed
                else []
            ),
            sentences=[
                SentenceOut(index=s.index, start=s.start, end=s.end)
                for s in result.sentences
            ],
            outOfScope=[
                OutOfScopeOut(start=s.start, end=s.end, text=s.text, script=s.script)
                for s in out_of_scope
            ],
            stages=[
                StageOut(
                    stage=r.stage,
                    name=r.name,
                    edits=r.edits_emitted,
                    ms=round(r.duration_ms, 2),
                    skipped=r.skipped_reason,
                )
                for r in result.stage_reports
            ],
            stageDistribution=result.stage_distribution,
            totalMs=round(result.total_ms, 2),
            readability=readability,
            readabilityMissing=readability_missing,
        )


class ErrorClassOut(_Wire):
    code: str
    category: str
    label_native: str
    label_en: str
    rule_reference: str | None = Field(default=None, alias="ruleReference")
    # None means "declared and evaluated, but no detector yet". The UI shows
    # these greyed out rather than hiding them.
    implemented_at_stage: int | None = Field(alias="implementedAtStage")


class LanguageOut(_Wire):
    code: str
    name_en: str = Field(alias="nameEn")
    name_native: str = Field(alias="nameNative")
    lexicon_size: int = Field(alias="lexiconSize")
    dictionary: Literal["hunspell", "seed"]


class IdentityOut(_Wire):
    device_id: str = Field(alias="deviceId")
    tier: str


class RecoveryOut(_Wire):
    phrase: str
    words: int


class ConvertRequest(_Wire):
    text: str = Field(max_length=200_000)


class ConvertResponse(_Wire):
    text: str
    detected: bool
    coverage: float
    converted: bool
    note: str | None = None
