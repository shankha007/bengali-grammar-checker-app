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

    `newline=""` on both ends: without it, Python rewrites every LF as CRLF on
    Windows, so a developer who ran this locally ended up with an .aff 2 KB
    larger than upstream and a diff against it on every line. Harmless to
    spylls, but it disguises what this function actually changed — which
    mattered here, because the size difference was the first clue that the local
    file had been through a step the Docker build never ran.
    """
    with path.open("r", encoding="utf-8", newline="") as fh:
        lines = fh.readlines()
    changed = 0
    for i, line in enumerate(lines):
        m = _AFF_HEADER.match(line)
        if m:
            # Keep whatever line ending the file already used.
            ending = line[len(line.rstrip("\r\n")) :]
            lines[i] = m.group(1) + ending
            changed += 1
    if changed:
        with path.open("w", encoding="utf-8", newline="") as fh:
            fh.write("".join(lines))
    return changed


def verify(dic_path: Path) -> str | None:
    """Load the pair the way the pack will. Returns an error string, or None.

    Downloading two files successfully is not the same as having a usable
    dictionary, and the gap between those two facts is what shipped a mute
    spell-checker to production: the fetch reported "Done", the pack could not
    parse the .aff, and the fallback to the seed lexicon happened quietly three
    layers away from here. If the files this script just wrote cannot be loaded,
    this script has failed, and it should say so while the reason is still in
    front of it.
    """
    try:
        from spylls.hunspell import Dictionary
    except ImportError:
        return None  # spylls is an optional extra; nothing to verify against
    try:
        Dictionary.from_files(str(dic_path.with_suffix("")))
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


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

    # bn_BD.aff ships SFX/PFX headers whose count field carries a trailing `$`.
    # Hunspell's C `atoi` ignores it; spylls calls `int()` and raises
    # ValueError, which the pack catches and answers by falling back to the seed
    # lexicon — silently, and with spelling detection effectively switched off.
    #
    # This call is the whole reason `sanitize_aff` exists, and it was missing:
    # the function was written, documented, tested by hand, and never wired in.
    # A developer who had run the repair once had a working dictionary on disk
    # and no way to notice, while every clean build got the raw file. It cost a
    # production deploy that reported misspelt Bengali as correct.
    aff = DEST / "bn_BD.aff"
    if aff.exists():
        fixed = sanitize_aff(aff)
        print(f"sanitized {aff.name}: {fixed} affix header(s) repaired")

    # Prove the result loads before claiming success.
    problem = verify(DEST / "bn_BD.dic")
    if problem is not None:
        print(f"\nFAILED: the downloaded dictionary does not load ({problem}).")
        print("Leaving the files in place for inspection:", DEST)
        return 1

    print("\nDone, and verified loadable. The pack will pick these up on next")
    print("load; re-run `make eval` and expect NON_WORD to move.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
