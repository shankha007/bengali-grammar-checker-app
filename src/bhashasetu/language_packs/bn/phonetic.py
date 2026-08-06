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
_add("D", "ডঢদধ")
_add("P", "পফ")
_add("B", "বভ")
# ড় ঢ় belong with র, not with ড ঢ.
#
# The docstring above has always said so — "র ড় ঢ় merge in many hands" — but
# they were folded into D with the dental and retroflex stops, so র and ড়
# hashed apart and the equivalence class the file documents did not exist. The
# effect was on suggestions, which is where it does the most damage: কাপর got
# কপার and কাপুর, শিকর got শকর, and কাপড় and শিকড় — the words the writer
# actually meant — were not in the pool to be ranked at all. A checker that
# flags the right word and then names the wrong fix is worse than one that says
# nothing, because the user acts on it.
#
# ড় is a flap [ɽ], articulated far closer to র than to the stop it is written
# from; the historical derivation from ড is spelling, not sound. The cost is
# that ড় no longer rhymes with ড, which is the rarer confusion by a distance.
_add("R", "র" + C.RRA + C.RHA)
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


def homophone_substitution(word: str, candidate: str) -> bool:
    """Do these differ by exactly one swap WITHIN a sound class?

    This is the shape of the overwhelming majority of real Bengali misspellings:
    not a slip of the finger, but the writer choosing the wrong letter for a
    sound that has several spellings — কাপর for কাপড়, কারন for কারণ, ভাসা for
    ভাষা. `soundex` already knows which letters share a sound; this asks the
    narrower question of whether ONE such letter is all that separates two
    strings.

    It exists because equal edit distance was leaving the ranking to chance.
    কাপর is one edit from both কাপড় (র→ড়, the same sound) and কপার (a
    transposition, unrelated sounds), and with nothing to separate them the
    order fell to whichever sorted first — which put কপার, "copper", at the top
    of the list for someone who had typed "cloth". Preferring the homophone is
    the difference between a suggestion the writer accepts and one that makes
    them distrust the whole column.

    Compared per code point rather than per grapheme cluster on purpose: the
    letters that carry these confusions are single code points, and clustering
    would hide a nukta swap (র vs ড়) inside a larger unit.
    """
    if len(word) != len(candidate) or word == candidate:
        return False
    diff = [(a, b) for a, b in zip(word, candidate, strict=True) if a != b]
    if len(diff) != 1:
        return False
    a, b = diff[0]
    folded = _FOLD.get(a)
    return folded is not None and folded == _FOLD.get(b)
