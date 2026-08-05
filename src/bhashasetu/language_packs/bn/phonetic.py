"""Bangla Soundex - phonetic key for candidate ranking.

Bengali orthography preserves Sanskrit distinctions that modern pronunciation has
collapsed. A speaker hears one sound for each of these groups:

    শ  ষ  স        all realised /ʃ/ (or /s/ in some clusters)
    ন  ণ           both /n/
    জ  য           both /dʒ/
    ই  ঈ  /  ি  ী   both /i/
    উ  ঊ  /  ু  ূ   both /u/
    র  ড়  ঢ়        merge in many hands
    ব  ভ           distinct, but confused constantly in casual writing

So the overwhelming majority of real Bengali misspellings are *homophonous*:
দীন written as দিন, স্বাধীন as শাধিন. Pure edit distance ranks a random
one-character neighbour above the homophone the writer actually meant. Folding
each equivalence class to a single key and preferring same-key candidates fixes
that, and it is the single cheapest quality win available at Stage 1.

The key is deliberately lossy. It is a *ranking* signal, never a membership test.
"""

from __future__ import annotations

from functools import lru_cache

from bhashasetu.language_packs.bn import chars as C

# Each equivalence class maps to one representative symbol.
_FOLD: dict[str, str] = {}


def _add(symbol: str, members: str) -> None:
    for ch in members:
        _FOLD[ch] = symbol


# sibilants
_add("S", "শষস")
# nasals - dental/retroflex merge, plus anusvara and the velar nasal
_add("N", "নণ")
_add("M", "মং" + C.ANUSVARA)
_add("G", "ঙঞ")
# stops: aspiration is systematically dropped in casual spelling, so each
# varga's four stops fold to a voiced/voiceless pair rather than to one symbol -
# folding ক and গ together would over-merge and start ranking nonsense.
_add("K", "কখ")
_add("g", "গঘ")
_add("C", "চছ")
_add("J", "জঝয")
_add("T", "টঠতথৎ")
_add("D", "ডঢদধ" + C.RRA + C.RHA)
_add("P", "পফ")
_add("B", "বভ")
_add("R", "র")
_add("L", "ল")
_add("H", "হ")
_add("Y", C.YYA)
# vowels: length is not contrastive in modern Bengali
_add("i", "ইঈিী")
_add("u", "উঊুূ")
_add("e", "এেঐৈ")
_add("o", "ওোঔৌ")
_add("a", "অআা")
_add("r", "ঋৃ")

_DROP = frozenset({C.HASANTA, C.CHANDRABINDU, C.NUKTA, C.VISARGA, C.ZWJ, C.ZWNJ})


@lru_cache(maxsize=32768)
def soundex(word: str) -> str:
    """Fold a word to its phonetic key.

    Vowels after the first position are dropped, as in classic Soundex: Bengali's
    inherent-vowel orthography means the written vowels are the least reliable
    part of the string, and keeping them re-introduces the noise the key exists
    to remove.
    """
    out: list[str] = []
    for i, ch in enumerate(word):
        if ch in _DROP:
            continue
        sym = _FOLD.get(ch)
        if sym is None:
            if ch.isalnum():
                out.append(ch.lower())
            continue
        is_vowel = sym in "aiueor"
        if is_vowel and i > 0:
            continue
        if out and out[-1] == sym:
            continue  # collapse doubled consonants: ন্ন -> N
        out.append(sym)
    return "".join(out)


def rhymes(a: str, b: str) -> bool:
    return soundex(a) == soundex(b)
