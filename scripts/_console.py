"""Make stdout/stderr safe for Bengali on a Windows console.

Every lint and validation script in here reports by printing the offending text,
and the offending text is Bengali. On Windows `sys.stdout` defaults to the
system ANSI codepage (cp1252 on an English install), which has no code point for
any Bengali letter — so the moment one of these scripts had something to say, it
died with `UnicodeEncodeError` instead of saying it.

That failure mode is worse than it looks. The traceback comes from inside the
`print`, so it reads as a broken script rather than a failed check, and the
exit code is 1 either way: `make check` on Windows could not tell "the gold set
has a problem" from "the validator crashed". The scripts are silent on a clean
run, which is precisely why this survived — it only fired when there was a
finding to report.

`errors="replace"` rather than `strict`: a console that genuinely cannot render
Bengali should print boxes and let the reader see the rest of the message. The
alternative is losing the whole report to one unencodable character.
"""

from __future__ import annotations

import sys


def use_utf8() -> None:
    """Reconfigure the standard streams to UTF-8. Safe to call more than once."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
