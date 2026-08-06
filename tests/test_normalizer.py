"""Stage 0 contract tests.

The idempotency test is the important one. A non-idempotent normalizer breaks
the incremental sentence-scoped re-check in Phase 3 in a way that is very hard to
debug from the UI: the same paragraph produces different offsets on the second
keystroke and decorations drift.
"""

from __future__ import annotations

import pytest

from bhashasetu.language_packs.bn import chars as C
from bhashasetu.language_packs.bn.normalizer import BengaliNormalizer

CORPUS = [
    "আমি বাংলা ভাষায় কথা বলি।",
    "সে গতকাল ঢাকা থেকে এসেছে।",
    "ড" + C.NUKTA + "াকা",
    "য" + C.NUKTA + "ে",
    "ত" + C.HASANTA + C.ZWJ,
    "ক" + C.E_KAR + C.AA_KAR + "ন",
    "ক" + C.AA_KAR + C.E_KAR + "ন",
    "বই" + C.ZWSP + "টি",
    "শব্দ" + C.BOM,
    "রা" + C.HASANTA + C.HASANTA + "ম",
    "আমি বাড়ি যাচ্ছি।",
    "",
    "   ",
    "English text with no Bengali at all.",
    "১২৩ ৪৫৬",
    "তুমি কি আসবে?? আমি জানি না।।",
]


@pytest.fixture(scope="module")
def norm() -> BengaliNormalizer:
    return BengaliNormalizer()


@pytest.mark.parametrize("text", CORPUS)
def test_idempotent(norm: BengaliNormalizer, text: str) -> None:
    once = norm.normalize(text).text
    twice = norm.normalize(once).text
    assert once == twice


@pytest.mark.parametrize("text", CORPUS)
def test_offset_map_is_well_formed(norm: BengaliNormalizer, text: str) -> None:
    result = norm.normalize(text)
    assert len(result.offset_map) == len(result.text) + 1
    assert all(0 <= o <= len(text) for o in result.offset_map)
    # Monotonic: normalization never reorders characters.
    assert result.offset_map == sorted(result.offset_map)


def test_nukta_composes_where_nfc_refuses(norm: BengaliNormalizer) -> None:
    """The composition-exclusion case, asserted on CODE POINTS.

    Written with `C.RRA` rather than a literal `ড়` on purpose. An earlier version
    of this test compared against a literal, that literal was itself decomposed,
    and the assertion passed while the normalizer did nothing at all. The bug
    surfaced only when a real Hunspell dictionary started rejecting পড়ছে and the
    clean-text false-positive rate jumped to 11%.

    Anything that can be true of both the decomposed and composed forms is not a
    test of this behaviour.
    """
    import unicodedata

    decomposed = "ড" + C.NUKTA + "াকা"
    assert unicodedata.normalize("NFC", decomposed) == decomposed  # NFC won't

    result = norm.normalize(decomposed).text
    assert result[0] == C.RRA
    assert ord(result[0]) == 0x09DC
    assert C.NUKTA not in result

    assert norm.normalize("য" + C.NUKTA + "ে").text[0] == C.YYA
    assert norm.normalize("ঢ" + C.NUKTA).text == C.RHA


def test_decomposed_o_kar(norm: BengaliNormalizer) -> None:
    assert norm.normalize("ক" + C.E_KAR + C.AA_KAR + "ন").text == "কোন"
    # Reversed order, which NFC does not repair.
    assert norm.normalize("ক" + C.AA_KAR + C.E_KAR + "ন").text == "কোন"


def test_khanda_ta_before_zwj_stripping(norm: BengaliNormalizer) -> None:
    """Order-dependent: strip the joiner first and the khanda-ta is unrecoverable."""
    assert norm.normalize("ত" + C.HASANTA + C.ZWJ).text == C.KHANDA_TA


def test_zwnj_kept_after_hasanta_stripped_elsewhere(norm: BengaliNormalizer) -> None:
    kept = norm.normalize("ক" + C.HASANTA + C.ZWNJ + "ষ").text
    assert C.ZWNJ in kept
    stripped = norm.normalize("ক" + C.ZWNJ + "ষ").text
    assert C.ZWNJ not in stripped


def test_invisibles_removed(norm: BengaliNormalizer) -> None:
    result = norm.normalize("বই" + C.ZWSP + "টি" + C.BOM)
    assert result.text == "বইটি"
    assert "strip_invisibles" in result.applied_rules


def test_nbsp_becomes_space(norm: BengaliNormalizer) -> None:
    # chr(0xA0), not a literal: a no-break space is indistinguishable from a
    # plain one in the source file, so a literal here would test nothing.
    result = norm.normalize("আমি" + chr(0x00A0) + "বই").text
    assert result == "আমি বই"
    assert chr(0x00A0) not in result


def test_repeated_hasanta_collapsed(norm: BengaliNormalizer) -> None:
    assert norm.normalize("রা" + C.HASANTA * 3 + "ম").text == "রা" + C.HASANTA + "ম"


def test_double_dari_is_left_for_stage_1(norm: BengaliNormalizer) -> None:
    """Stage 0 must not fold ।। into ॥.

    It used to, and that quietly destroyed the evidence: the fold turned the
    commonest punctuation typo there is into a legal verse terminator before
    Stage 1 ran, so the user got no flag at all. Stage 0 is for changes the
    writer could not disagree with. `tests/test_rules.py` asserts the flag.
    """
    text = "শেষ" + C.DARI * 2
    assert norm.normalize(text).text == text


def test_non_bengali_text_untouched(norm: BengaliNormalizer) -> None:
    text = "The quick brown fox. 42 items."
    assert norm.normalize(text).text == text
