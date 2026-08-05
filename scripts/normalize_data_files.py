#!/usr/bin/env python
"""Rewrite Bengali data files into canonical composed form.

The fixer for `lint_data_normalization.py`. Idempotent - safe to run repeatedly,
and safe to wire into a pre-commit hook.

Applies NFC plus the three composition-exclusion cases NFC refuses to handle
(U+09DC ড়, U+09DD ঢ়, U+09DF য়). Same normalization the Stage 0 pipeline applies
to user input, so lexicon lookups compare like with like.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUKTA = "়"
# Code points, not literals - see the module docstring. Writing `"ড়"` as a
# literal here would reintroduce exactly the bug this file exists to catch.
COMPOSE = {
    "ড" + NUKTA: "ড়",
    "ঢ" + NUKTA: "ঢ়",
    "য" + NUKTA: "য়",
}

TARGETS = [
    *(REPO / "src" / "bhashasetu" / "language_packs").rglob("*.yaml"),
    *(REPO / "src" / "bhashasetu" / "language_packs").rglob("*.txt"),
    *(REPO / "eval" / "gold").rglob("*.yaml"),
]
EXEMPT = {"bijoy_map.yaml"}  # legacy encoding table; leave its bytes alone


def normalize(text: str) -> str:
    out = unicodedata.normalize("NFC", text)
    for bad, good in COMPOSE.items():
        out = out.replace(bad, good)
    return out


def main() -> int:
    touched = 0
    for path in TARGETS:
        if path.name in EXEMPT:
            continue
        before = path.read_text(encoding="utf-8")
        after = normalize(before)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changes = sum(before.count(b) for b in COMPOSE)
            print(f"  {path.relative_to(REPO)}: {changes} sequence(s) composed")
            touched += 1
    print(f"normalized {touched} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
