"""Language-agnostic string distance used for candidate generation.

Deliberately operates on whatever units the caller supplies rather than assuming
code points are the right granularity. In Indic scripts a single perceived
character is routinely three or four code points, so code-point distance
mis-ranks candidates badly; packs pass in grapheme clusters instead. See
`language_packs/bn/chars.py::graphemes` for the Bengali clustering rule.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache


def damerau_levenshtein(a: str, b: str, max_distance: int | None = None) -> int:
    """Unrestricted Damerau-Levenshtein (allows adjacent transposition).

    Returns `max_distance + 1` early if the distance provably exceeds it, which
    is what makes bulk candidate filtering affordable.
    """
    if a == b:
        return 0
    if max_distance is not None and abs(len(a) - len(b)) > max_distance:
        return max_distance + 1

    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la

    prev2: list[int] = []
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        row_min = cur[0]
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            val = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                val = min(val, prev2[j - 2] + 1)
            cur[j] = val
            row_min = min(row_min, val)
        if max_distance is not None and row_min > max_distance:
            return max_distance + 1
        prev2, prev = prev, cur
    return prev[lb]


@lru_cache(maxsize=8192)
def _cached(a: str, b: str, max_distance: int) -> int:
    return damerau_levenshtein(a, b, max_distance)


def within(a: str, b: str, max_distance: int) -> bool:
    return _cached(a, b, max_distance) <= max_distance


def rank_candidates(
    word: str,
    candidates: list[str],
    *,
    max_distance: int = 2,
    phonetic_key: Callable[[str], str] | None = None,
    frequency: dict[str, int] | None = None,
    prefer: Callable[[str, str], bool] | None = None,
    limit: int = 5,
) -> list[str]:
    """Rank correction candidates.

    Score = edit distance, tie-broken by (a) `prefer`, (b) phonetic-key match,
    (c) corpus frequency, then (d) lexicographic order for determinism. A
    grammar checker that reorders its own suggestions between runs is
    untrustworthy, so the final sort key is always total.

    `prefer(word, candidate)` is the pack's own opinion about which of two
    equally-distant candidates is the likelier correction — the one piece of
    this that cannot be language-agnostic. Bengali passes a test for "differs by
    one letter within a sound class", which is what most real misspellings are;
    without it, equal-distance candidates were separated by nothing but sort
    order. It ranks strictly below distance, so it reorders ties rather than
    promoting a worse match.
    """
    freq = frequency or {}
    target_key = phonetic_key(word) if phonetic_key else None

    scored: list[tuple[int, int, int, int, int, str]] = []
    for cand in candidates:
        if cand == word:
            continue
        dist = damerau_levenshtein(word, cand, max_distance)
        if dist > max_distance:
            continue
        phon = 0
        if target_key is not None and phonetic_key is not None:
            phon = 0 if phonetic_key(cand) == target_key else 1
        preferred = 0 if prefer is not None and prefer(word, cand) else 1
        # At equal distance, a candidate the same length as the input got there
        # by substitution; a longer or shorter one needed an insertion or a
        # deletion. The substitution is the likelier correction, because it is
        # the likelier mistake — someone reached for the wrong letter rather
        # than dropping one. Without this tier, a misspelt inflected form ranked
        # a reconstruction carrying a doubled suffix above the clean one: both
        # two edits away, separated by nothing but sort order.
        length_gap = abs(len(cand) - len(word))
        scored.append((dist, preferred, length_gap, phon, -freq.get(cand, 0), cand))

    scored.sort()
    return [c for *_, c in scored[:limit]]
