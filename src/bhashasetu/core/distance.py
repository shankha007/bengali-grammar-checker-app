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
    limit: int = 5,
) -> list[str]:
    """Rank correction candidates.

    Score = edit distance, tie-broken by (a) phonetic-key match, then
    (b) corpus frequency, then (c) lexicographic order for determinism. A
    grammar checker that reorders its own suggestions between runs is
    untrustworthy, so the final sort key is always total.
    """
    freq = frequency or {}
    target_key = phonetic_key(word) if phonetic_key else None

    scored: list[tuple[int, int, int, str]] = []
    for cand in candidates:
        if cand == word:
            continue
        dist = damerau_levenshtein(word, cand, max_distance)
        if dist > max_distance:
            continue
        phon = 0
        if target_key is not None and phonetic_key is not None:
            phon = 0 if phonetic_key(cand) == target_key else 1
        scored.append((dist, phon, -freq.get(cand, 0), cand))

    scored.sort()
    return [c for *_, c in scored[:limit]]
