"""Bengali lexicon: trie + morphological suffix stripping, with an optional
Hunspell backend.

Spec §8: "The false-positive rate on clean text is the single most important
number in this project." Everything here is arranged around that.

Bengali is agglutinative enough that a flat word list badly under-covers real
text. বই is in any dictionary; বইগুলোকেও is not, and it is perfectly correct.
So lookup is: exact hit, else strip a legal suffix chain and retry. Without that
step a 50k-word list produces a false positive on roughly every third inflected
token, and the product is dead on arrival.

`coverage_factor` is the second guard. It scales down NON_WORD confidence when
the loaded dictionary is small, so a thin dev lexicon produces *quiet*
suggestions rather than confident wrong ones. Ship a real Hunspell dictionary
(`make fetch-dicts`) and the confidence rises on its own.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from bhashasetu.core.distance import rank_candidates
from bhashasetu.language_packs.bn import chars as C
from bhashasetu.language_packs.bn.phonetic import soundex

_DATA = Path(__file__).parent / "data"

# Below this many surface forms, NON_WORD flags are damped hard - the dictionary,
# not the writer, is the likely problem.
CONFIDENT_LEXICON_SIZE = 150_000


def _compose(word: str) -> str:
    """NFC plus the three composition-exclusion cases NFC refuses.

    Same rule as Stage 0. See `normalizer.py` for why NFC alone is not enough.
    """
    out = unicodedata.normalize("NFC", word)
    for base, composed in C.NUKTA_COMPOSITIONS.items():
        out = out.replace(base + C.NUKTA, composed)
    return out


@dataclass(frozen=True, slots=True)
class Lookup:
    known: bool
    matched_form: str | None
    stripped_suffixes: tuple[str, ...] = ()


class BengaliLexicon:
    def __init__(
        self,
        words: Iterable[str],
        suffixes: list[str],
        frequency: dict[str, int] | None = None,
        prefixes: Iterable[str] = (),
    ) -> None:
        # Compose on ingest. Lookups arrive normalized (Stage 0 ran first), so a
        # decomposed entry in the word list would simply never match — silently,
        # because the two forms are visually identical. That matters most for the
        # user-supplied custom dictionary in Phase 4, where the words come from a
        # text box and whatever keyboard the user has.
        self._words: set[str] = {_compose(w) for w in words if w}
        # Longest first: -গুলোকেও must strip before -ও.
        self._suffixes = sorted({s for s in suffixes if s}, key=len, reverse=True)
        self._prefixes = sorted({p for p in prefixes if p}, key=len, reverse=True)
        self._freq = frequency or {}
        self._by_key: dict[str, list[str]] = {}
        for w in self._words:
            self._by_key.setdefault(soundex(w), []).append(w)
        self._by_len: dict[int, list[str]] = {}
        for w in self._words:
            self._by_len.setdefault(len(w), []).append(w)

    # -- protocol ------------------------------------------------------
    @property
    def size(self) -> int:
        return len(self._words)

    @property
    def coverage_factor(self) -> float:
        """0..1 multiplier applied to NON_WORD confidence."""
        return min(1.0, self.size / CONFIDENT_LEXICON_SIZE)

    def contains(self, word: str) -> bool:
        return self.lookup(word).known

    def lookup(self, word: str, _depth: int = 0) -> Lookup:
        if not word:
            return Lookup(True, word)
        if word in self._words:
            return Lookup(True, word)

        # Numerals, Latin, and anything without a Bengali letter are not ours to
        # judge. Silence beats a wrong flag.
        if not any(C.is_bengali_letter(ch) for ch in word):
            return Lookup(True, word)

        if _depth < 4:
            for suf in self._suffixes:
                if len(word) > len(suf) + 1 and word.endswith(suf):
                    stem = word[: -len(suf)]
                    inner = self.lookup(stem, _depth + 1)
                    if inner.known:
                        return Lookup(
                            True, inner.matched_form, (suf, *inner.stripped_suffixes)
                        )
                    # A stem ending in a bare consonant often lost its inherent
                    # vowel sign to the suffix: বইয়ের -> বই.
                    if stem and stem[-1] == C.HASANTA:
                        inner = self.lookup(stem[:-1], _depth + 1)
                        if inner.known:
                            return Lookup(
                                True,
                                inner.matched_form,
                                (suf, *inner.stripped_suffixes),
                            )

        # Compounds: এদেশের -> এ + দেশের, সবসময় -> সব + সময়. Only tried at the
        # outermost level, so this cannot recurse into nonsense.
        if _depth == 0:
            for pre in self._prefixes:
                if len(word) > len(pre) + 1 and word.startswith(pre):
                    inner = self.lookup(word[len(pre) :], _depth + 1)
                    if inner.known:
                        return Lookup(True, inner.matched_form, inner.stripped_suffixes)

        return Lookup(False, None)

    def suggest(self, word: str, limit: int = 5) -> list[str]:
        """Candidates from two pools, phonetic first.

        The phonetic pool is what catches the errors people actually make
        (দিন/দীন); the length-window pool catches typos. Merging them and letting
        `rank_candidates` sort by distance-then-phonetic-match gives the right
        order without a hand-tuned score.
        """
        pool: set[str] = set(self._by_key.get(soundex(word), []))
        for length in range(max(1, len(word) - 2), len(word) + 3):
            pool.update(self._by_len.get(length, []))
        pool.discard(word)
        return rank_candidates(
            word,
            list(pool),
            max_distance=2,
            phonetic_key=soundex,
            frequency=self._freq,
            limit=limit,
        )


class HunspellLexicon(BengaliLexicon):
    """Wraps `spylls` when a real bn_BD/bn_IN dictionary is installed.

    Optional on purpose: Phase 1 must run with zero network access and zero
    licence-encumbered data. `make fetch-dicts` installs the real thing.
    """

    def __init__(
        self,
        dic_path: Path,
        suffixes: list[str],
        supplement: Iterable[str] = (),
        prefixes: Iterable[str] = (),
    ) -> None:
        try:
            from spylls.hunspell import Dictionary
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "spylls is not installed; run `pip install -e '.[hunspell]'` "
                "or fall back to the bundled seed lexicon"
            ) from exc
        self._dict = Dictionary.from_files(str(dic_path.with_suffix("")))
        # Union, not replacement. The seed list and data/extra_words.txt carry
        # সাধু forms and চলিত future tenses that bn_BD lacks; loading the real
        # dictionary must not throw them away, or installing a better dictionary
        # would make the checker noisier.
        words = [w.stem for w in self._dict.dic.words]
        words.extend(supplement)
        super().__init__(words, suffixes, prefixes=prefixes)
        self._suggest_cache: dict[str, list[str]] = {}

    @property
    def coverage_factor(self) -> float:
        """No damping.

        The stem count understates a Hunspell dictionary badly - bn_BD ships
        ~88k stems but its affix table expands those into millions of legal
        surface forms, and `lookup()` applies the affix rules properly rather
        than guessing with our suffix list. Scaling confidence by stem count
        would hold NON_WORD below the surface gate forever on a dictionary that
        is, in fact, trustworthy.

        The damping in the base class exists for the opposite situation: a bare
        word list too thin to justify an opinion.
        """
        return 1.0

    def contains(self, word: str) -> bool:
        # Hunspell first (it knows the affix rules); our suffix-stripping
        # fallback only gets a say if Hunspell rejects, which keeps সাধু forms
        # and seed-list entries from being flagged.
        return bool(self._dict.lookup(word)) or super().contains(word)

    def suggest(self, word: str, limit: int = 5) -> list[str]:
        """Hunspell's suggester, re-ranked by our phonetic key.

        Hunspell already knows the affix machinery, so its candidate list is
        better than anything the seed pools produce. What it does not know is
        that Bengali readers confuse ষ/শ/স and ন/ণ far more often than they
        transpose letters - so the candidates get re-sorted through
        `rank_candidates`, which prefers a same-Soundex match at equal edit
        distance.
        """
        cached = self._suggest_cache.get(word)
        if cached is not None:
            return cached[:limit]
        try:
            candidates = list(self._dict.suggester.suggest(word))
        except Exception:  # pragma: no cover - suggester is best-effort
            candidates = []
        if not candidates:
            return super().suggest(word, limit)
        ranked = rank_candidates(
            word,
            candidates,
            max_distance=3,
            phonetic_key=soundex,
            limit=limit,
        )
        # Never drop everything on the floor: if nothing survives the distance
        # filter, Hunspell's own order beats an empty suggestion list.
        result = ranked or candidates[:limit]
        self._suggest_cache[word] = result
        return result


def load_default_lexicon() -> BengaliLexicon:
    words_path = _DATA / "lexicon.txt"
    suffix_path = _DATA / "suffixes.yaml"

    words = [
        line.strip()
        for line in words_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    suffix_cfg = yaml.safe_load(suffix_path.read_text(encoding="utf-8"))
    suffixes: list[str] = []
    for group in suffix_cfg.get("suffixes", {}).values():
        suffixes.extend(group)
    prefixes: list[str] = list(suffix_cfg.get("prefixes", []))

    # Frequency proxy: the seed list is ordered roughly by corpus frequency, so
    # earlier entries outrank later ones on ties. Replace with real counts when
    # a corpus lands in Phase 2.
    freq = {w: len(words) - i for i, w in enumerate(words)}

    extra_path = _DATA / "extra_words.txt"
    extra = (
        [
            line.strip()
            for line in extra_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if extra_path.exists()
        else []
    )

    hunspell_dic = _DATA / "hunspell" / "bn_BD.dic"
    if hunspell_dic.exists():
        try:
            lex = HunspellLexicon(
                hunspell_dic, suffixes, supplement=[*words, *extra], prefixes=prefixes
            )
        except RuntimeError:
            pass
        else:
            return lex
    return BengaliLexicon([*words, *extra], suffixes, freq, prefixes=prefixes)
