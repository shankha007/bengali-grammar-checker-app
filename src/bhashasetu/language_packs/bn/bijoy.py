"""Bijoy / ANSI (SutonnyMJ family) legacy encoding.

Scope note: spec §1 lists Bijoy→Unicode under Stage 0, but spec §6.2 schedules
the *converter* as a Phase 4 linguist tool. Phase 1 therefore ships:

* `looks_like_bijoy()`  - detection, complete and tested
* `convert_bijoy()`     - table-driven conversion, table deliberately partial

Conversion is **gated on coverage**. Bijoy is not a character encoding, it is a
glyph encoding: pre-base vowel signs (ি ে ৈ) are stored before their consonant in
visual order, reph is stored after its cluster, and several conjuncts have
dedicated glyph codes with no compositional structure. A half-complete table
does not produce half-correct Bengali, it produces convincing garbage - which is
worse than a clear "paste this as Unicode" message.

So: if fewer than `MIN_COVERAGE` of the mappable characters in a run are known,
the text is returned unchanged and the caller keeps the original. Completing
`data/bijoy_map.yaml` against a real SutonnyMJ keymap is a Phase 4 task with its
own gold set.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from bhashasetu.language_packs.bn import chars as C

_DATA = Path(__file__).parent / "data" / "bijoy_map.yaml"

MIN_COVERAGE = 0.95

# Vowel signs that Bijoy stores to the LEFT of their consonant.
_PRE_BASE = (C.E_KAR, "ি", "ৈ")


@lru_cache(maxsize=1)
def _tables() -> tuple[dict[str, str], set[str]]:
    raw = yaml.safe_load(_DATA.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {str(k): str(v) for k, v in (raw.get("map") or {}).items()}
    signature: set[str] = set(raw.get("signature") or [])
    return mapping, signature


# Density floor. Deliberately low: the signature characters are high-range
# Windows-1252 code points that essentially never occur in English prose, so
# `min_hits` is the load-bearing guard and this only rejects a stray paste of
# one or two of them into otherwise-Latin text. It was 0.15, which rejected
# short but unambiguous Bijoy passages — a real recall bug, since a paragraph
# of Bijoy runs about 10% signature characters.
_SIGNATURE_DENSITY = 0.08


def looks_like_bijoy(text: str, *, min_hits: int = 4) -> bool:
    """Heuristic: Bijoy text is ASCII-looking but hits characters that never
    cluster like this in real English.

    Three requirements, all necessary to keep English prose out:
      1. no Bengali code points present at all
      2. at least `min_hits` signature characters
      3. those hits above a (low) density floor
    """
    if any(C.is_bengali(ch) for ch in text):
        return False
    _, signature = _tables()
    letters = [ch for ch in text if not ch.isspace()]
    if len(letters) < min_hits:
        return False
    hits = sum(1 for ch in letters if ch in signature)
    return hits >= min_hits and hits / len(letters) >= _SIGNATURE_DENSITY


def coverage(text: str) -> float:
    mapping, _ = _tables()
    candidates = [ch for ch in text if not ch.isspace() and not ch.isdigit()]
    if not candidates:
        return 1.0
    return sum(1 for ch in candidates if ch in mapping) / len(candidates)


def convert_bijoy(text: str) -> str:
    """Return Unicode Bengali, or `text` unchanged if the table cannot cover it."""
    if coverage(text) < MIN_COVERAGE:
        return text
    mapping, _ = _tables()
    mapped = "".join(mapping.get(ch, ch) for ch in text)
    return _reorder_pre_base(mapped)


def _reorder_pre_base(text: str) -> str:
    """Move pre-base vowel signs after the consonant cluster they belong to.

    Bijoy stores ি ে ৈ in visual order (left of the cluster); Unicode stores them
    in logical order (right of it). Without this pass every word containing an
    i-kar comes out wrong.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in _PRE_BASE:
            j = i + 1
            cluster: list[str] = []
            while j < n and (text[j] in C.ALL_CONSONANTS or text[j] == C.HASANTA):
                cluster.append(text[j])
                j += 1
                # A hasanta binds the next consonant into the same cluster.
                if cluster and cluster[-1] == C.HASANTA:
                    continue
                if j < n and text[j] == C.HASANTA:
                    continue
                break
            if cluster:
                out.extend(cluster)
                out.append(ch)
                i = j
                continue
        out.append(ch)
        i += 1
    return "".join(out)
