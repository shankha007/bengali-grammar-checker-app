"""Bengali (U+0980-U+09FF) character inventory.

Every Bengali code point used anywhere in the pack is named here. Rules elsewhere
reference the names, so a rule reads like grammar rather than like a hex dump.
"""

from __future__ import annotations

# --- structural signs ------------------------------------------------------
CHANDRABINDU = "ঁ"  # ঁ
ANUSVARA = "ং"      # ং
VISARGA = "ঃ"       # ঃ
NUKTA = "়"         # ়
HASANTA = "্"       # ্  (virama / hôsôntô)
AVAGRAHA = "ঽ"      # ঽ
KHANDA_TA = "ৎ"     # ৎ

# --- vowels ----------------------------------------------------------------
INDEPENDENT_VOWELS = "অআইঈউঊঋঌএঐওঔ"
VOWEL_SIGNS = "ািীুূৃৄেৈোৌৗ"
# া  ি  ী  ু  ূ  ৃ  ৄ  ে  ৈ  ো  ৌ  ৗ

E_KAR = "ে"      # ে
AA_KAR = "া"     # া
AU_LENGTH = "ৗ"  # ৗ
O_KAR = "ো"      # ো  == E_KAR + AA_KAR
AU_KAR = "ৌ"     # ৌ  == E_KAR + AU_LENGTH

# --- consonants ------------------------------------------------------------
CONSONANTS = "কখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহ"
# Defined by code point, never as literals. These three are in Unicode's
# composition-exclusion table, so `ড + ়` and `ড়` look identical in every editor
# and compare unequal in every string operation. Writing them as literals means
# whichever form your keyboard or model emitted becomes law, silently.
RRA = "ড়"   # composed; == DDA + NUKTA
RHA = "ঢ়"   # composed; == DHA + NUKTA
YYA = "য়"   # composed; == YA  + NUKTA

# base letter -> composed form. Drives normalization and the data-file lint.
NUKTA_COMPOSITIONS: dict[str, str] = {
    "ড": RRA,
    "ঢ": RHA,
    "য": YYA,
}

NUKTA_CONSONANTS = RRA + RHA + YYA
ALL_CONSONANTS = CONSONANTS + NUKTA_CONSONANTS + KHANDA_TA

# ট-বর্গ - the retroflex series. Central to ণত্ব-বিধান.
RETROFLEX = "টঠডঢণ"
# ত-বর্গ - the dental series.
DENTAL = "তথদধন"

DIGITS = "০১২৩৪৫৬৭৮৯"
ASCII_DIGITS = "0123456789"

# --- punctuation -----------------------------------------------------------
DARI = "।"         # ।  sentence terminator; NOT a full stop
DOUBLE_DARI = "॥"  # ॥  verse terminator

# --- invisible characters that break everything downstream -----------------
ZWNJ = "‌"
ZWJ = "‍"
ZWSP = "​"
LRM = "‎"
RLM = "‏"
WORD_JOINER = "⁠"
BOM = "﻿"
SOFT_HYPHEN = "­"
INVISIBLES = (ZWSP, LRM, RLM, WORD_JOINER, BOM, SOFT_HYPHEN)

BENGALI_RANGE = (0x0980, 0x09FF)


def is_bengali(ch: str) -> bool:
    return BENGALI_RANGE[0] <= ord(ch) <= BENGALI_RANGE[1]


def is_bengali_letter(ch: str) -> bool:
    return ch in ALL_CONSONANTS or ch in INDEPENDENT_VOWELS


def is_dependent(ch: str) -> bool:
    """Marks that cannot begin a grapheme cluster."""
    return ch in VOWEL_SIGNS or ch in (CHANDRABINDU, ANUSVARA, VISARGA, HASANTA, NUKTA)


def graphemes(word: str) -> list[str]:
    """Split into perceived units.

    Edit distance over code points ranks candidates badly: `ক্ষ` is 3 code points
    but one thing a reader sees, and treating a missing hasanta as one edit while
    a missing conjunct is three makes the ranking incoherent. So: a base letter
    plus everything dependent that follows it, and a hasanta binds the next
    letter into the same cluster.
    """
    out: list[str] = []
    i = 0
    n = len(word)
    while i < n:
        ch = word[i]
        cluster = ch
        i += 1
        while i < n:
            nxt = word[i]
            if nxt == HASANTA:
                cluster += nxt
                i += 1
                if i < n:
                    cluster += word[i]
                    i += 1
                continue
            if is_dependent(nxt):
                cluster += nxt
                i += 1
                continue
            break
        out.append(cluster)
    return out
