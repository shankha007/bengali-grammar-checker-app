"""Sentence and word segmentation for Bengali.

The dari (।) is the sentence terminator. A period is not - it appears in
abbreviations, numerals, URLs, and embedded English, and treating it as a
terminator shreds ordinary mixed-script prose. Bengali text in the wild does use
`?` and `!` as terminators, so those are honoured.
"""

from __future__ import annotations

import re

from bhashasetu.core.types import Sentence, Token
from bhashasetu.language_packs.bn import chars as C

_TERMINATORS = C.DARI + C.DOUBLE_DARI + "?!"

# A word is a run of Bengali letters/marks, or a run of Latin letters, or a
# number. Hyphens and the hasanta never end a word.
_WORD_RE = re.compile(
    r"[ঀ-৿‌‍]+"       # Bengali incl. deliberate joiners
    r"|[A-Za-z]+(?:['’][A-Za-z]+)*"  # Latin, with apostrophes
    r"|[0-9০-৯]+(?:[.,][0-9০-৯]+)*"  # numbers, either digit set
)

# `.` only terminates when it is not part of an abbreviation or a number.
_LATIN_SENTENCE_END = re.compile(r"(?<![A-Za-z0-9])\.(?=\s|$)")


class BengaliTokenizer:
    def sentences(self, text: str) -> list[Sentence]:
        spans: list[tuple[int, int]] = []
        start = 0
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch in _TERMINATORS:
                # Absorb a run of terminators plus trailing quotes/brackets.
                j = i + 1
                while j < n and (text[j] in _TERMINATORS or text[j] in '"\')]'):
                    j += 1
                spans.append((start, j))
                while j < n and text[j] in " \t":
                    j += 1
                start = j
                i = j
                continue
            if ch == "\n" and i + 1 < n and text[i + 1] == "\n":
                # Blank line ends a sentence even without punctuation - otherwise
                # a bulleted list becomes one 400-word "sentence" and the
                # sentence-scoped re-check in Phase 3 loses all its value.
                spans.append((start, i))
                j = i
                while j < n and text[j] == "\n":
                    j += 1
                start = j
                i = j
                continue
            i += 1
        if start < n:
            spans.append((start, n))

        out: list[Sentence] = []
        for s, e in spans:
            body = text[s:e]
            if not body.strip():
                continue
            out.append(Sentence(index=len(out), start=s, end=e, text=body))
        return out

    def tokens(self, text: str, offset: int = 0) -> list[Token]:
        out: list[Token] = []
        pos = 0
        for m in _WORD_RE.finditer(text):
            if m.start() > pos:
                gap = text[pos : m.start()]
                if gap.strip():
                    out.append(
                        Token(offset + pos, offset + m.start(), gap, is_word=False)
                    )
            out.append(
                Token(offset + m.start(), offset + m.end(), m.group(), is_word=True)
            )
            pos = m.end()
        if pos < len(text) and text[pos:].strip():
            out.append(Token(offset + pos, offset + len(text), text[pos:], is_word=False))
        return out

    def words(self, text: str, offset: int = 0) -> list[Token]:
        return [t for t in self.tokens(text, offset) if t.is_word]

    @staticmethod
    def is_bengali_word(token: str) -> bool:
        return any(C.is_bengali_letter(ch) for ch in token)


def looks_like_sentence_final_period(text: str, index: int) -> bool:
    m = _LATIN_SENTENCE_END.search(text, index, index + 1)
    return m is not None
