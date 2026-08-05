"""Core value types shared by every language pack.

Nothing in this module may contain language-specific data. See
`scripts/lint_core_language_purity.py` - CI fails if it does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

Stage = Literal[0, 1, 2, 3, 4]


class ErrorClass(StrEnum):
    """The 12 fine-grained classes from the spec, in 5 broad categories.

    The enum is intentionally closed: a language pack may declare that it does
    not implement a class, but it may not invent a new one without a spec
    change. Cross-language comparability of the eval slices depends on this.
    """

    # 1. Spelling / orthography
    NON_WORD = "NON_WORD"
    HOMONYM = "HOMONYM"
    NOTVA_SHOTVA = "NOTVA_SHOTVA"
    # 2. Morphology / inflection
    CASE_MARKER = "CASE_MARKER"
    CLASSIFIER = "CLASSIFIER"
    VERB_INFLECTION = "VERB_INFLECTION"
    # 3. Syntax
    WORD_ORDER = "WORD_ORDER"
    POS_ERROR = "POS_ERROR"
    AGREEMENT = "AGREEMENT"
    # 4. Register / style
    GURUCHANDALI_DOSHA = "GURUCHANDALI_DOSHA"
    REGISTER_INCONSISTENCY = "REGISTER_INCONSISTENCY"
    # 5. Punctuation
    PUNCTUATION = "PUNCTUATION"


CATEGORY_OF: dict[ErrorClass, str] = {
    ErrorClass.NON_WORD: "orthography",
    ErrorClass.HOMONYM: "orthography",
    ErrorClass.NOTVA_SHOTVA: "orthography",
    ErrorClass.CASE_MARKER: "morphology",
    ErrorClass.CLASSIFIER: "morphology",
    ErrorClass.VERB_INFLECTION: "morphology",
    ErrorClass.WORD_ORDER: "syntax",
    ErrorClass.POS_ERROR: "syntax",
    ErrorClass.AGREEMENT: "syntax",
    ErrorClass.GURUCHANDALI_DOSHA: "register",
    ErrorClass.REGISTER_INCONSISTENCY: "register",
    ErrorClass.PUNCTUATION: "punctuation",
}


@dataclass(frozen=True, slots=True)
class Edit:
    """A single proposed change. Stages emit these; they never emit rewritten text.

    `start`/`end` are character offsets into the *normalized* text. Callers that
    need offsets against the user's original input must map them back through
    `NormalizationResult.offset_map`.
    """

    id: str
    start: int
    end: int
    original: str
    suggestions: list[str]
    error_class: ErrorClass
    confidence: float
    stage: Stage
    explanation_bn: str
    explanation_en: str
    rule_reference: str | None = None
    # Free-form, never shown to users. Used by the eval harness and for debugging
    # why a rule fired.
    debug: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span [{self.start}, {self.end})")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence}")

    @property
    def top_suggestion(self) -> str | None:
        return self.suggestions[0] if self.suggestions else None

    def overlaps(self, other: Edit) -> bool:
        return self.start < other.end and other.start < self.end

    def to_json(self) -> dict[str, Any]:
        """Camel-cased to match the TypeScript `Edit` interface in the spec."""
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "original": self.original,
            "suggestions": list(self.suggestions),
            "errorClass": self.error_class.value,
            "confidence": round(self.confidence, 4),
            "stage": self.stage,
            "explanation_bn": self.explanation_bn,
            "explanation_en": self.explanation_en,
            "ruleReference": self.rule_reference,
        }


@dataclass(frozen=True, slots=True)
class ErrorClassSpec:
    """Loaded from `<pack>/error_classes.yaml`. Never hard-coded in app logic."""

    code: ErrorClass
    category: str
    label_native: str
    label_en: str
    explanation_template_native: str
    explanation_template_en: str
    rule_reference: str | None
    implemented_at_stage: Stage | None
    gold_cases: list[str] = field(default_factory=list)
    # Used when the detector found an error but has no correction to offer.
    # Optional: most classes always produce one.
    explanation_template_native_no_fix: str | None = None
    explanation_template_en_no_fix: str | None = None

    def render(self, **kwargs: str) -> tuple[str, str]:
        """Fill both explanation templates. Missing keys are left as-is rather
        than raising - a half-rendered explanation is still shippable, a crash
        in the hot path is not.

        When `right` is empty the no-fix templates are used instead, if the pack
        supplies them. The default templates quote the correction, so with
        nothing to quote they rendered a bare pair of quotation marks in the
        middle of the sentence - which reads as a bug in the product rather than
        as an honest "no automatic fix". A detector is allowed to have no
        suggestion; it is not allowed to pretend it has one.
        """
        native = self.explanation_template_native
        english = self.explanation_template_en
        if not kwargs.get("right", "x"):
            native = self.explanation_template_native_no_fix or native
            english = self.explanation_template_en_no_fix or english
        return (_safe_format(native, kwargs), _safe_format(english, kwargs))


def _safe_format(template: str, values: dict[str, str]) -> str:
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", value)
    return out


@dataclass(frozen=True, slots=True)
class Sentence:
    """A sentence span within the normalized text."""

    index: int
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class Token:
    start: int
    end: int
    text: str
    is_word: bool


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Stage 0 output.

    `offset_map[i]` is the offset in the *original* text that normalized
    character `i` came from. Length is `len(text) + 1` so end-exclusive spans map
    cleanly.
    """

    text: str
    original: str
    offset_map: list[int]
    applied_rules: list[str] = field(default_factory=list)
    edits: list[Edit] = field(default_factory=list)

    def to_original_span(self, start: int, end: int) -> tuple[int, int]:
        if not self.offset_map:
            return start, end
        last = len(self.offset_map) - 1
        return self.offset_map[min(start, last)], self.offset_map[min(end, last)]


@dataclass(slots=True)
class StageReport:
    stage: Stage
    name: str
    edits_emitted: int
    duration_ms: float
    skipped_reason: str | None = None


@dataclass(slots=True)
class CheckResult:
    """What the pipeline returns. The CLI, the API, and the eval harness all
    consume this exact shape."""

    language: str
    original: str
    normalized: str
    edits: list[Edit]
    suppressed: list[Edit]
    sentences: list[Sentence]
    stage_reports: list[StageReport]
    total_ms: float

    @property
    def stage_distribution(self) -> dict[int, int]:
        """First-class metric per spec §1: where edits actually resolve.

        If stage 4's share climbs above 25%, stages 0-3 need retraining.
        """
        dist: dict[int, int] = {}
        for edit in self.edits:
            dist[edit.stage] = dist.get(edit.stage, 0) + 1
        return dist

    def to_json(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "normalized": self.normalized,
            "edits": [e.to_json() for e in self.edits],
            "stageDistribution": self.stage_distribution,
            "totalMs": round(self.total_ms, 2),
            "stages": [
                {
                    "stage": r.stage,
                    "name": r.name,
                    "edits": r.edits_emitted,
                    "ms": round(r.duration_ms, 2),
                    "skipped": r.skipped_reason,
                }
                for r in self.stage_reports
            ],
        }


@dataclass(frozen=True, slots=True)
class OutOfScopeSpan:
    """A run of text the active language pack does not cover.

    Deliberately NOT a 13th `ErrorClass`. Foreign text is not an error — the
    checker simply has no opinion about it, and saying so is different from
    saying it is wrong. Conflating the two would corrupt the eval: every English
    word in a mixed-script document would count against precision.

    The UI renders these differently from edits (a flat highlight, not a wavy
    underline) so "I cannot judge this" never looks like "this is incorrect".
    """

    start: int
    end: int
    text: str
    script: str
