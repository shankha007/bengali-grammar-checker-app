#!/usr/bin/env python
"""Download bn_BD / bn_IN Hunspell dictionaries.

Not run automatically and not vendored. Two reasons:

1. Phase 1 must build and evaluate with no network access.
2. These dictionaries carry their own licences (GPL/LGPL/MPL depending on
   source). Vendoring them into this repo without a licence review would be a
   compliance problem, and it is not one to settle silently in a scaffold.

Until this runs, the pack uses `data/lexicon.txt`, and NON_WORD confidence is
damped by `BengaliLexicon.coverage_factor` so the thin dictionary cannot produce
confident wrong flags.

Review `SOURCES` before running: confirm each licence is compatible with how this
project is distributed.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import use_utf8

use_utf8()

DEST = (
    Path(__file__).resolve().parents[1]
    / "src" / "bhashasetu" / "language_packs" / "bn" / "data" / "hunspell"
)

# Verify these URLs and their licences before use - they are recorded here as the
# intended sources, not as vetted ones.
SOURCES: dict[str, str] = {
    "bn_BD.dic": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bn_BD/bn_BD.dic",
    "bn_BD.aff": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bn_BD/bn_BD.aff",
}


_AFF_HEADER = re.compile(r"^((?:SFX|PFX)\t[^\t]+\t[YN]\t\d+)\$\s*$")


def sanitize_aff(path: Path) -> int:
    """Strip trailing `$` from SFX/PFX header count fields.

    bn_BD.aff carries lines like `SFX\tL\tY\t12$`. Hunspell reads the count with
    `atoi`, which stops at the `$` and moves on; spylls calls `int()` and raises.
    The file is not wrong so much as relying on C parsing slack, and every
    strict-parser toolchain will hit this.

    Returns the number of lines changed. Idempotent.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = 0
    for i, line in enumerate(lines):
        m = _AFF_HEADER.match(line)
        if m:
            lines[i] = m.group(1) + "\n"
            changed += 1
    if changed:
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def main() -> int:
    print("This downloads third-party dictionary files with their own licences.")
    print("Destination:", DEST)
    for name, url in SOURCES.items():
        print(f"  {name}  <-  {url}")
    if "--yes" not in sys.argv:
        print("\nRe-run with --yes once you have reviewed the sources and licences.")
        return 1

    DEST.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        target = DEST / name
        print(f"fetching {name} ...", end=" ", flush=True)
        with urllib.request.urlopen(url) as resp:  # noqa: S310 - reviewed above
            target.write_bytes(resp.read())
        print(f"{target.stat().st_size:,} bytes")

    print("\nDone. The pack will pick these up on next load; re-run `make eval`")
    print("and expect NON_WORD precision/recall to move for the first time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
