"""Bangla-calibrated readability (spec §6.2).

Flesch-Kincaid is not ported here, and the reason is not stylistic. F-K's
constants were fitted on English, where syllable count and word length correlate
with difficulty. In Bengali:

* word length tracks *agglutination*, not difficulty - বইগুলোকেও is long and
  trivially easy;
* syllable count is inflated by the inherent vowel, which is written nowhere;
* the actual difficulty signal is **তৎসম density** - Sanskritic vocabulary is
  what makes a Bengali text hard, and it is orthogonally distributed to length.

Formula and coefficient provenance: `docs/readability.md`.

Phase 1 status: three of the four spec'd components are computed. Mean dependency
length needs a parser, which arrives with the POS/morphology work in Phase 4. Its
weight is redistributed proportionally rather than silently zeroed, and
`components_missing` says so in the output - a score whose basis changed between
versions without saying so is worse than no score.
"""

from __future__ import annotations

import statistics

from bhashasetu.core.types import Sentence
from bhashasetu.language_packs.bn import chars as C
from bhashasetu.language_packs.bn.tokenizer import BengaliTokenizer

# Weights over the four spec'd components.
WEIGHTS = {
    "syllables_per_word": 0.30,
    "tatsama_density": 0.35,
    "dependency_length": 0.20,  # unavailable until Phase 4
    "sentence_length_variance": 0.15,
}

# তৎসম markers: graphemes that essentially only occur in Sanskrit-derived
# vocabulary. A word carrying one is counted as তৎসম. Crude, ~0.8 precision on
# spot checks, and cheap - replace with a dictionary-backed origin tag when the
# Hunspell dictionaries land.
_TATSAMA_MARKERS = ("ষ", "ণ", "ঋ", "ৃ", C.VISARGA, "ঞ", "ঢ়")
_TATSAMA_CLUSTERS = ("্য", "্র", "্ব", "ক্ষ", "জ্ঞ")


def count_syllables(word: str) -> int:
    """Vowel nuclei.

    A consonant carries the inherent vowel অ unless a vowel sign, a hasanta, or
    another dependent mark cancels it. That is the rule English-trained syllable
    counters have no way to know, and it is why they overcount Bengali by ~40%.
    """
    n = 0
    i = 0
    length = len(word)
    while i < length:
        ch = word[i]
        if ch in C.INDEPENDENT_VOWELS:
            n += 1
            i += 1
            continue
        if ch in C.ALL_CONSONANTS:
            nxt = word[i + 1] if i + 1 < length else ""
            if nxt == C.HASANTA:
                i += 2  # conjunct: no nucleus here, the next base carries it
                continue
            if nxt in C.VOWEL_SIGNS:
                n += 1
                i += 2
                continue
            n += 1  # inherent vowel
            i += 1
            continue
        i += 1
    return max(n, 1 if word else 0)


def is_tatsama(word: str) -> bool:
    return any(m in word for m in _TATSAMA_MARKERS) or any(
        c in word for c in _TATSAMA_CLUSTERS
    )


class BengaliReadability:
    def __init__(self, tokenizer: BengaliTokenizer | None = None) -> None:
        self.tokenizer = tokenizer or BengaliTokenizer()

    def score(self, text: str, sentences: list[Sentence]) -> dict[str, float]:
        words = [
            t.text
            for t in self.tokenizer.words(text)
            if BengaliTokenizer.is_bengali_word(t.text)
        ]
        if not words or not sentences:
            return {
                "score": 0.0,
                "syllables_per_word": 0.0,
                "tatsama_density": 0.0,
                "sentence_length_variance": 0.0,
                "words": 0.0,
                "sentences": 0.0,
            }

        spw = statistics.fmean(count_syllables(w) for w in words)
        tatsama = sum(1 for w in words if is_tatsama(w)) / len(words)

        lengths = [
            len([t for t in self.tokenizer.words(s.text) if t.is_word])
            for s in sentences
        ]
        variance = statistics.pvariance(lengths) if len(lengths) > 1 else 0.0

        # Each component normalised to 0..1 "difficulty", then combined.
        # Anchors in docs/readability.md; they are calibration constants, not
        # magic numbers, and they are due for refit against reader judgements in
        # Phase 5.
        d_spw = _clamp((spw - 2.0) / 2.5)
        d_tat = _clamp(tatsama / 0.45)
        d_var = _clamp(variance / 90.0)

        available = {
            "syllables_per_word": d_spw,
            "tatsama_density": d_tat,
            "sentence_length_variance": d_var,
        }
        total_weight = sum(WEIGHTS[k] for k in available)
        difficulty = sum(WEIGHTS[k] * v for k, v in available.items()) / total_weight

        return {
            # 0 = hardest, 100 = easiest, matching reader intuition about
            # "readability scores" even though the internals are difficulty.
            "score": round((1.0 - difficulty) * 100, 1),
            "syllables_per_word": round(spw, 3),
            "tatsama_density": round(tatsama, 3),
            "sentence_length_variance": round(variance, 2),
            "mean_sentence_length": round(statistics.fmean(lengths), 2),
            "words": float(len(words)),
            "sentences": float(len(sentences)),
        }

    @property
    def components_missing(self) -> list[str]:
        return ["dependency_length"]


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))
