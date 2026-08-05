#!/usr/bin/env python
"""CI lint: every Bengali data file must be in canonical composed form.

This exists because of a bug that shipped and was invisible.

`ড + ়` (U+09A1 U+09BC) and `ড়` (U+09DC) render identically in every editor,
terminal, and diff. They are different strings. U+09DC/09DD/09DF are in Unicode's
composition-exclusion table, so NFC will not unify them for you.

The failure mode: `_NUKTA_COMPOSE` in the normalizer mapped decomposed input to a
replacement string that was itself decomposed - a no-op. Its unit test asserted
equality against another decomposed literal, so it passed. The bug only surfaced
when a real Hunspell dictionary (composed) started rejecting perfectly ordinary
words like পড়ছে, producing a 11% false-positive rate on clean text.

Nothing about that is catchable by reading the code. It needs a byte-level check,
which is this file.

Run `python scripts/normalize_data_files.py` to fix violations.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUKTA = "়"
# Code points, not literals - see the module docstring.
DECOMPOSED = {
    "ড" + NUKTA: "ড়",
    "ঢ" + NUKTA: "ঢ়",
    "য" + NUKTA: "য়",
}

TARGETS = [
    *(REPO / "src" / "bhashasetu" / "language_packs").rglob("*.yaml"),
    *(REPO / "src" / "bhashasetu" / "language_packs").rglob("*.txt"),
    *(REPO / "eval" / "gold").rglob("*.yaml"),
]

# chars.py and normalizer.py legitimately contain `base + NUKTA` as source
# material for the composition rule itself.
EXEMPT = {"chars.py", "normalizer.py", "lint_data_normalization.py",
          "normalize_data_files.py"}


def main() -> int:
    violations: list[str] = []
    for path in TARGETS:
        if path.name in EXEMPT:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for bad, good in DECOMPOSED.items():
                if bad in line:
                    rel = path.relative_to(REPO)
                    violations.append(
                        f"{rel}:{lineno}: decomposed "
                        f"U+{ord(bad[0]):04X}+U+09BC, should be U+{ord(good):04X}"
                    )
                    break

    if violations:
        print("Decomposed nukta sequences in data files:", file=sys.stderr)
        for v in violations[:40]:
            print(f"  {v}", file=sys.stderr)
        if len(violations) > 40:
            print(f"  ... and {len(violations) - 40} more", file=sys.stderr)
        print(
            "\nThese are byte-level differences that look identical on screen.\n"
            "Fix with: python scripts/normalize_data_files.py",
            file=sys.stderr,
        )
        return 1

    print(f"data normalization OK ({len(TARGETS)} files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
