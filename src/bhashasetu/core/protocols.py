"""The `LanguagePack` contract.

Adding a language means implementing these protocols in a new
`language_packs/<code>/` directory and registering it. It must never mean
editing anything under `core/`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from bhashasetu.core.types import (
    Edit,
    ErrorClass,
    ErrorClassSpec,
    NormalizationResult,
    OutOfScopeSpan,
    Sentence,
    Stage,
    Token,
)


@runtime_checkable
class Normalizer(Protocol):
    """Stage 0. Must be idempotent: normalize(normalize(x)) == normalize(x).

    A property test enforces that for every pack; see
    `tests/test_normalizer_contract.py`.
    """

    def normalize(self, text: str) -> NormalizationResult: ...


@runtime_checkable
class SentenceTokenizer(Protocol):
    """Sentence terminators are language-specific. Bengali's dari is not a period."""

    def sentences(self, text: str) -> list[Sentence]: ...

    def tokens(self, text: str, offset: int = 0) -> list[Token]: ...


@runtime_checkable
class Lexicon(Protocol):
    def contains(self, word: str) -> bool: ...

    def suggest(self, word: str, limit: int = 5) -> list[str]: ...

    @property
    def size(self) -> int:
        """Number of surface forms known. The lexical stage scales its
        confidence by this - a thin dictionary must not produce confident
        NON_WORD flags."""
        ...


@runtime_checkable
class Detector(Protocol):
    """Stage 1 and Stage 2 both satisfy this. Stage 2 (BanglaBERT) arrives in
    Phase 2; in Phase 1 only the lexical detector is registered."""

    stage: Stage

    def detect(
        self, text: str, sentences: list[Sentence]
    ) -> list[Edit]: ...


@runtime_checkable
class Corrector(Protocol):
    """Stage 3. Rewrites only within already-flagged spans."""

    stage: Stage

    def correct(self, text: str, edits: list[Edit]) -> list[Edit]: ...


@runtime_checkable
class ReadabilityScorer(Protocol):
    def score(self, text: str, sentences: list[Sentence]) -> dict[str, float]: ...


@runtime_checkable
class LanguagePack(Protocol):
    code: str
    name_en: str
    name_native: str

    normalizer: Normalizer
    tokenizer: SentenceTokenizer
    lexicon: Lexicon
    detectors: list[Detector]
    correctors: list[Corrector]
    readability: ReadabilityScorer

    @property
    def error_classes(self) -> dict[ErrorClass, ErrorClassSpec]: ...

    def out_of_scope(self, text: str) -> list[OutOfScopeSpan]:
        """Runs of text this pack cannot judge, e.g. another script.

        Part of the contract, not a Bengali extra: every pack is silent on text
        outside its language, and silence is indistinguishable from approval
        unless the pack says which parts it skipped. A pack that genuinely
        covers everything returns an empty list.

        These are never `Edit`s. Foreign text is not an error, and counting it
        as one would make every mixed-script document drag down precision.
        """
        ...
