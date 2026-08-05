"""Language-pluggability guards (spec §7).

The CI lint is the real enforcement; these tests make the failure legible when
someone breaks the rule locally.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

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


def test_pack_survives_a_broken_dictionary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A dictionary that will not load must degrade the checker, not kill it.

    The fallback used to catch RuntimeError only, which covered a missing spylls
    and nothing else. A half-finished fetch — .dic written, .aff not — raised
    FileNotFoundError out of spylls and took `get_pack("bn")` down with it. In a
    container build that is a failed deploy whose log names spylls' internals
    rather than the dictionary.

    Parametrised over the ways a fetch can leave the directory wrong.
    """
    import bhashasetu.language_packs.bn.lexicon as lexicon_module

    for name, files in (
        ("aff missing", {"bn_BD.dic": "3\nfoo\nbar\n"}),
        ("dic truncated", {"bn_BD.dic": "", "bn_BD.aff": "SET UTF-8\n"}),
        ("both unreadable", {"bn_BD.dic": "\x00\x00", "bn_BD.aff": "\x00"}),
    ):
        data = tmp_path / name.replace(" ", "_")
        (data / "hunspell").mkdir(parents=True)
        for filename, body in files.items():
            (data / "hunspell" / filename).write_text(body, encoding="utf-8")
        for shared in ("lexicon.txt", "suffixes.yaml", "extra_words.txt"):
            source = lexicon_module._DATA / shared
            if source.exists():
                (data / shared).write_bytes(source.read_bytes())

        monkeypatch.setattr(lexicon_module, "_DATA", data)
        lex = lexicon_module.load_default_lexicon()

        assert lex.size > 0, f"{name}: no lexicon at all"
        # Degraded, and said so — silence here would ship a checker that finds
        # no spelling errors and looks healthy doing it.
        assert "WARNING" in capsys.readouterr().err, f"{name}: fell back silently"
