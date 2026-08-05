#!/usr/bin/env python
"""CI lint (spec §7): no Bengali-specific data outside `language_packs/bn/`.

Fails the build if any code point in U+0980-U+09FF appears under `src/.../core/`.
The rule exists because a single hard-coded Bengali regex in the core is enough
to make the Hindi pack in Phase 5 quietly impossible, and that kind of coupling
is invisible until the day you try to add the second language.

Scope note: this checks the Bengali block specifically, not "non-ASCII". Core
docstrings may contain any other script.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "src" / "bhashasetu" / "core"
LOW, HIGH = 0x0980, 0x09FF


def main() -> int:
    violations: list[str] = []
    for path in sorted(CORE.rglob("*.py")):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            hits = {ch for ch in line if LOW <= ord(ch) <= HIGH}
            if hits:
                rel = path.relative_to(REPO)
                chars = " ".join(f"U+{ord(c):04X} {c}" for c in sorted(hits))
                violations.append(f"{rel}:{lineno}: {chars}")

    if violations:
        print("Bengali code points found in the language-agnostic core:", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        print(
            "\nMove the rule into src/bhashasetu/language_packs/bn/ and reference it "
            "through the LanguagePack protocol.",
            file=sys.stderr,
        )
        return 1

    print(f"core language purity OK ({len(list(CORE.rglob('*.py')))} files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
