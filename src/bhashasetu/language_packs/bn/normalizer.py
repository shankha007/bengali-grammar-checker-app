"""Stage 0 - Bengali normalization.

Silent and meaning-preserving only. If a change is something a writer might
reasonably disagree with, it belongs in Stage 1 as an `Edit`, not here.

Why NFC alone is not enough: Unicode's composition-exclusion table contains
U+09DC ড়, U+09DD ঢ়, and U+09DF য়, so `unicodedata.normalize("NFC", ...)` leaves
`ড + ়` decomposed. Two spellings of the same word then hash differently, the
lexicon misses, and the user gets a false NON_WORD flag on correctly typed text.
That single detail is responsible for a large share of naive Bangla checkers'
false positives.

Every pass maintains `offset_map` so Stage 1+ spans can be mapped back onto the
text the user actually typed.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from bhashasetu.core.types import NormalizationResult
from bhashasetu.language_packs.bn import chars as C
from bhashasetu.language_packs.bn.bijoy import convert_bijoy, looks_like_bijoy


@dataclass(slots=True)
class _Buf:
    text: str
    omap: list[int]
    rules: list[str] = field(default_factory=list)

    def replace_all(self, pairs: list[tuple[str, str]], rule: str) -> None:
        """Apply literal substitutions, keeping offsets aligned.

        Longest source first so `ে + ৗ` never gets eaten by a shorter rule.
        """
        pairs = sorted(pairs, key=lambda p: -len(p[0]))
        out: list[str] = []
        omap: list[int] = []
        i = 0
        n = len(self.text)
        fired = False
        while i < n:
            for src, dst in pairs:
                if src and self.text.startswith(src, i):
                    origin = self.omap[i]
                    for ch in dst:
                        out.append(ch)
                        omap.append(origin)
                    i += len(src)
                    fired = True
                    break
            else:
                out.append(self.text[i])
                omap.append(self.omap[i])
                i += 1
        if fired:
            self.text = "".join(out)
            self.omap = omap
            self.rules.append(rule)


# ---------------------------------------------------------------------------
# Substitution tables

_INVISIBLES = [(ch, "") for ch in C.INVISIBLES]

# Built from code points, not literals: these are indistinguishable from a plain
# space in any editor, which is exactly why they survive into user input and
# then split one word into two for the tokenizer.
_SPACE_LIKE: list[tuple[str, str]] = [
    (chr(cp), " ")
    for cp in (
        0x00A0,  # no-break space - what Word and Google Docs paste
        0x1680,
        *range(0x2000, 0x200B),  # en/em quad, en/em space, thin, hair, ...
        0x202F,  # narrow no-break space
        0x205F,  # medium mathematical space
        0x3000,  # ideographic space
    )
] + [("	", " ")]

# Composition exclusions - NFC will not do these for us. Built from
# `NUKTA_COMPOSITIONS` rather than written out, because a literal replacement
# target here is indistinguishable on screen from its decomposed form: get it
# wrong and this pass becomes a silent no-op that no visual review will catch.
_NUKTA_COMPOSE = [
    (base + C.NUKTA, composed) for base, composed in C.NUKTA_COMPOSITIONS.items()
]

# Reversed / decomposed vowel signs. NFC handles the canonical order; it does not
# handle the reversed order that phonetic keyboards emit.
_VOWEL_COMPOSE = [
    (C.E_KAR + C.AA_KAR, C.O_KAR),
    (C.AA_KAR + C.E_KAR, C.O_KAR),
    (C.E_KAR + C.AU_LENGTH, C.AU_KAR),
    (C.AU_LENGTH + C.E_KAR, C.AU_KAR),
]

# ত + hasanta + ZWJ is the legacy way to force khanda-ta. U+09CE is the encoding
# the standard actually wants, and it is what the lexicon is keyed on.
_KHANDA_TA = [
    ("ত" + C.HASANTA + C.ZWJ, C.KHANDA_TA),
    ("ৎ" + C.HASANTA, C.KHANDA_TA),
]

# Stray joiners. A ZWNJ immediately after hasanta is meaningful (the writer is
# deliberately breaking a conjunct, e.g. অ‌ন্তঃ vs the ligated form) and is kept.
# Everywhere else it is keyboard debris.
_STRAY_ZWJ = [(C.ZWJ, "")]

_SMART_PUNCT_FOLD = [
    ("‘", "'"), ("’", "'"),
    ("“", '"'), ("”", '"'),
    ("–", "-"), ("—", "-"),
    ("…", "..."),
]


@dataclass(slots=True)
class BengaliNormalizerConfig:
    convert_bijoy: bool = True
    fold_bengali_digits: bool = False  # both forms are correct; off by default


class BengaliNormalizer:
    """Idempotent by construction: every pass either matches nothing on a second
    run, or maps its own output to itself. `tests/test_normalizer.py` asserts
    `normalize(normalize(x)) == normalize(x)` over a property-style corpus."""

    def __init__(self, config: BengaliNormalizerConfig | None = None) -> None:
        self.config = config or BengaliNormalizerConfig()

    def normalize(self, text: str) -> NormalizationResult:
        original = text
        buf = _Buf(text=text, omap=list(range(len(text))))

        if self.config.convert_bijoy and looks_like_bijoy(text):
            converted = convert_bijoy(text)
            # Bijoy is a byte-for-byte legacy encoding; the mapping is not
            # 1:1 in length, so offsets collapse to the start of the run. Users
            # pasting Bijoy get a converted document, not inline edits, which is
            # the right UX anyway.
            buf = _Buf(text=converted, omap=[0] * len(converted))
            buf.rules.append("bijoy_to_unicode")

        buf.replace_all(_INVISIBLES, "strip_invisibles")
        buf.replace_all(_SPACE_LIKE, "space_like_to_space")
        # Khanda-ta must run before ZWJ stripping: `ত ্ ZWJ` IS the legacy
        # khanda-ta, and stripping the joiner first destroys the evidence.
        buf.replace_all(_KHANDA_TA, "khanda_ta")
        buf.replace_all(_STRAY_ZWJ, "strip_zwj")
        self._strip_stray_zwnj(buf)
        self._nfc(buf)
        buf.replace_all(_NUKTA_COMPOSE, "compose_nukta")
        buf.replace_all(_VOWEL_COMPOSE, "compose_vowel_signs")
        buf.replace_all(_SMART_PUNCT_FOLD, "punct_fold")
        self._collapse_repeats(buf, C.HASANTA, "collapse_hasanta")
        # `।।` is deliberately NOT folded into `॥` here.
        #
        # It used to be, and the fold was silently swallowing a typo: a doubled
        # dari is the commonest punctuation slip there is, and rewriting it into
        # the verse terminator made it a legal character before Stage 1 ever saw
        # it — so the user got no underline, no row in the table, and no hint
        # that anything was wrong. Stage 0 is for changes the writer could not
        # disagree with; "you meant the verse mark" is not one of those.
        # `_REPEATED` in rules.py flags it now, with a suggestion.
        if self.config.fold_bengali_digits:
            buf.replace_all(
                list(zip(C.DIGITS, C.ASCII_DIGITS, strict=True)), "fold_digits"
            )

        omap = [*buf.omap, len(original)]
        return NormalizationResult(
            text=buf.text,
            original=original,
            offset_map=omap,
            applied_rules=buf.rules,
            edits=[],
        )

    # ------------------------------------------------------------------
    def _nfc(self, buf: _Buf) -> None:
        """NFC per grapheme cluster, so offsets survive.

        Whole-string NFC would be one call, but it destroys the offset map on any
        text where a composition actually happens - which is exactly the text we
        care about.
        """
        out: list[str] = []
        omap: list[int] = []
        changed = False
        for start, cluster in _clusters(buf.text):
            composed = unicodedata.normalize("NFC", cluster)
            if composed != cluster:
                changed = True
            if len(composed) == len(cluster):
                for k, ch in enumerate(composed):
                    out.append(ch)
                    omap.append(buf.omap[start + k])
            else:
                origin = buf.omap[start]
                for ch in composed:
                    out.append(ch)
                    omap.append(origin)
        if changed:
            buf.text = "".join(out)
            buf.omap = omap
            buf.rules.append("nfc")

    def _strip_stray_zwnj(self, buf: _Buf) -> None:
        """Remove ZWNJ except directly after a hasanta.

        There it is meaningful - the writer is deliberately refusing a ligature
        and wants the hasanta to show. Anywhere else it is keyboard debris that
        silently breaks lexicon lookup.
        """
        out: list[str] = []
        omap: list[int] = []
        changed = False
        for i, ch in enumerate(buf.text):
            if ch == C.ZWNJ and not (i > 0 and buf.text[i - 1] == C.HASANTA):
                changed = True
                continue
            out.append(ch)
            omap.append(buf.omap[i])
        if changed:
            buf.text = "".join(out)
            buf.omap = omap
            buf.rules.append("strip_stray_zwnj")

    def _collapse_repeats(self, buf: _Buf, ch: str, rule: str) -> None:
        out: list[str] = []
        omap: list[int] = []
        changed = False
        for i, c in enumerate(buf.text):
            if c == ch and out and out[-1] == ch:
                changed = True
                continue
            out.append(c)
            omap.append(buf.omap[i])
        if changed:
            buf.text = "".join(out)
            buf.omap = omap
            buf.rules.append(rule)


def _clusters(text: str) -> list[tuple[int, str]]:
    """(start_offset, cluster) pairs covering the whole string."""
    out: list[tuple[int, str]] = []
    i = 0
    n = len(text)
    while i < n:
        start = i
        cluster = text[i]
        i += 1
        while i < n:
            nxt = text[i]
            if nxt == C.HASANTA:
                cluster += nxt
                i += 1
                if i < n:
                    cluster += text[i]
                    i += 1
                continue
            if C.is_dependent(nxt):
                cluster += nxt
                i += 1
                continue
            break
        out.append((start, cluster))
    return out
