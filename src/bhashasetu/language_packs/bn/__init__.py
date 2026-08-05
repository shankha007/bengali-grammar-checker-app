"""Bengali language pack.

Assembled here and nowhere else. `core/` never imports from this package - the
dependency runs one way, and `scripts/lint_core_language_purity.py` enforces it.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from bhashasetu.core.error_classes import load_error_classes
from bhashasetu.core.protocols import (
    Corrector,
    Detector,
    Lexicon,
    Normalizer,
    ReadabilityScorer,
    SentenceTokenizer,
)
from bhashasetu.core.types import ErrorClass, ErrorClassSpec, OutOfScopeSpan
from bhashasetu.language_packs.bn.lexicon import BengaliLexicon, load_default_lexicon
from bhashasetu.language_packs.bn.normalizer import BengaliNormalizer
from bhashasetu.language_packs.bn.readability import BengaliReadability
from bhashasetu.language_packs.bn.rules import BengaliRuleDetector
from bhashasetu.language_packs.bn.scope import find_out_of_scope
from bhashasetu.language_packs.bn.tokenizer import BengaliTokenizer

_ERROR_CLASSES = Path(__file__).parent / "error_classes.yaml"


class BengaliPack:
    code = "bn"
    name_en = "Bengali"
    name_native = "বাংলা"

    def __init__(self, lexicon: BengaliLexicon | None = None) -> None:
        # Concrete locals for wiring, protocol-typed attributes for the outside
        # world. `LanguagePack` matching is structural and attribute types are
        # invariant, so exposing BengaliLexicon here would make BengaliPack fail
        # to satisfy its own contract - and the Hindi pack in Phase 5 would
        # inherit the same trap.
        tokenizer = BengaliTokenizer()
        self._tokenizer = tokenizer  # concrete handle for pack-specific helpers
        lex = lexicon or load_default_lexicon()

        self.normalizer: Normalizer = BengaliNormalizer()
        self.tokenizer: SentenceTokenizer = tokenizer
        self.lexicon: Lexicon = lex
        self.readability: ReadabilityScorer = BengaliReadability(tokenizer)
        self._error_classes = load_error_classes(_ERROR_CLASSES)
        self.detectors: list[Detector] = [
            BengaliRuleDetector(lex, tokenizer, self._error_classes)
        ]
        # Stage 3 (BanglaT5) lands in Phase 2. Empty, not stubbed.
        self.correctors: list[Corrector] = []

    @property
    def error_classes(self) -> dict[ErrorClass, ErrorClassSpec]:
        return self._error_classes

    def out_of_scope(self, text: str) -> list[OutOfScopeSpan]:
        """Runs this pack cannot judge. Never errors — see scope.py."""
        return find_out_of_scope(text, self._tokenizer)


@lru_cache(maxsize=1)
def build_pack() -> BengaliPack:
    return BengaliPack()
