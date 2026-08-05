"""Detect text the Bengali pack cannot judge.

Every rule in this pack — the lexicon, ণত্ব/ষত্ব, the register tables — assumes
Bengali. On a Latin word they are all silent, which is correct behaviour but
indistinguishable, from the user's side, from "checked and fine". A writer
mixing English into Bengali prose has no way to tell whether the checker read
the English and approved it, or skipped it.

So the pack reports what it skipped. This is an *absence of opinion*, not a
finding: it never becomes an `Edit`, never enters the eval, and the UI renders it
as a flat highlight rather than an error underline.

What counts as out of scope: a run of letters containing no Bengali. Digits,
punctuation, and whitespace are script-neutral and never marked on their own —
`২০২৪` and `৳৩৫০` are ordinary Bengali text, and marking every full stop would
make the feature useless noise.
"""

from __future__ import annotations

import unicodedata

from bhashasetu.core.types import OutOfScopeSpan
from bhashasetu.language_packs.bn import chars as C
from bhashasetu.language_packs.bn.tokenizer import BengaliTokenizer

# Runs shorter than this are usually not another language: a stray "a" or an
# initial in "A. K. Sen" is noise, not English prose.
MIN_RUN_CHARS = 2


def _script_of(word: str) -> str:
    """Best-effort script name from the first letter's Unicode name.

    `unicodedata.name` gives "LATIN SMALL LETTER A", "DEVANAGARI LETTER KA" and
    so on; the first word is the script. Crude, but it needs no table and it is
    only ever shown as a label.
    """
    for ch in word:
        if ch.isalpha():
            try:
                return unicodedata.name(ch).split()[0].lower()
            except ValueError:
                return "unknown"
    return "unknown"


def find_out_of_scope(text: str, tokenizer: BengaliTokenizer) -> list[OutOfScopeSpan]:
    """Adjacent foreign words merge into one span.

    Merging matters for readability: "the quick brown fox" should be one
    highlight, not four, and `Ph.D.` should not come out as a highlighted "Ph"
    next to an unhighlighted "D".

    So the walk considers word tokens only and bridges whatever sits between
    them — whitespace, dots, hyphens, slashes — as long as no Bengali letter
    intervenes. That keeps `www.example.com` in one piece while ensuring a
    Bengali word always closes the run. Trailing sentence punctuation stays
    outside, because the span ends at the last foreign word.
    """
    words = [t for t in tokenizer.tokens(text) if t.is_word]
    spans: list[OutOfScopeSpan] = []
    run_start: int | None = None
    run_end = 0

    def flush() -> None:
        nonlocal run_start
        if run_start is None:
            return
        body = text[run_start:run_end]
        if len(body.strip()) >= MIN_RUN_CHARS:
            spans.append(
                OutOfScopeSpan(
                    start=run_start,
                    end=run_end,
                    text=body,
                    script=_script_of(body),
                )
            )
        run_start = None

    for token in words:
        foreign = any(ch.isalpha() for ch in token.text) and not any(
            C.is_bengali_letter(ch) for ch in token.text
        )
        if not foreign:
            flush()
            continue
        if run_start is None:
            run_start = token.start
        elif any(C.is_bengali_letter(ch) for ch in text[run_end : token.start]):
            flush()
            run_start = token.start
        run_end = token.end

    flush()
    return spans
