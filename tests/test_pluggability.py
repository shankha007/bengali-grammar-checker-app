"""Language-pluggability guards (spec §7).

The CI lint is the real enforcement; these tests make the failure legible when
someone breaks the rule locally.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from bhashasetu.core.protocols import (
    Detector,
    Lexicon,
    Normalizer,
    ReadabilityScorer,
    SentenceTokenizer,
)
from bhashasetu.core.registry import available, get_pack
from bhashasetu.core.types import ErrorClass

REPO = Path(__file__).resolve().parents[1]


def test_bn_pack_satisfies_every_protocol() -> None:
    pack = get_pack("bn")
    assert isinstance(pack.normalizer, Normalizer)
    assert isinstance(pack.tokenizer, SentenceTokenizer)
    assert isinstance(pack.lexicon, Lexicon)
    assert isinstance(pack.readability, ReadabilityScorer)
    assert all(isinstance(d, Detector) for d in pack.detectors)


def test_all_twelve_error_classes_are_specified() -> None:
    pack = get_pack("bn")
    assert set(pack.error_classes) == set(ErrorClass)
    for spec in pack.error_classes.values():
        assert spec.label_native and spec.label_en
        assert spec.explanation_template_native and spec.explanation_template_en
        assert len(spec.gold_cases) >= 3


def test_registry_reports_available_packs() -> None:
    assert "bn" in available()


def test_core_contains_no_bengali_codepoints() -> None:
    """The lint that Phase 5's Hindi pack depends on. If this fails, some
    Bengali-specific rule has leaked into the language-agnostic layer."""
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "lint_core_language_purity.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO,
    )
    assert result.returncode == 0, result.stdout + result.stderr
