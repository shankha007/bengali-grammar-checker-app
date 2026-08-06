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

import os
import sys
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from bhashasetu.core.distance import rank_candidates
from bhashasetu.language_packs.bn import chars as C
from bhashasetu.language_packs.bn.phonetic import homophone_substitution, soundex

_DATA = Path(__file__).parent / "data"

# Sanity floor for a fetched Hunspell dictionary. bn_BD ships ~88k stems; a file
# holding fewer than this parsed but did not download properly. See
# HunspellLexicon.__init__ for why loading one anyway is dangerous.
MIN_HUNSPELL_STEMS = 1_000

# Below this many surface forms, NON_WORD flags are damped hard - the dictionary,
# not the writer, is the likely problem.
CONFIDENT_LEXICON_SIZE = 150_000

# How many suffix splits `_stem_reconstructions` will try on one word. See there:
# every split is another pool scan, and the payoff falls off fast after the
# longest few.
MAX_STEM_SPLITS = 4


def _compose(word: str) -> str:
    """NFC plus the three composition-exclusion cases NFC refuses.

    Same rule as Stage 0. See `normalizer.py` for why NFC alone is not enough.
    """
    out = unicodedata.normalize("NFC", word)
    for base, composed in C.NUKTA_COMPOSITIONS.items():
        out = out.replace(base + C.NUKTA, composed)
    return out


def _vowel_final(stem: str) -> bool:
    """Does this stem end in a vowel, orthographically?

    A vowel sign or an independent vowel. Bengali's inherent vowel makes the
    phonological rule subtler — ছাত্র ends in a consonant letter but is
    pronounced with a final vowel — and this test calls that consonant-final.
    That is the right answer anyway: the genitive of ছাত্র is ছাত্রের, not
    ছাত্রর, so the two disagree only where the strict reading is also correct.
    """
    if not stem:
        return False
    last = stem[-1]
    return last in C.VOWEL_SIGNS or last in C.INDEPENDENT_VOWELS


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
        vowel_final_only: Iterable[str] = (),
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
        # See data/suffixes.yaml: these attach to a vowel-final stem only, and
        # stripping them off a consonant is how a misspelling gets whitewashed.
        self._vowel_final_only = frozenset(s for s in vowel_final_only if s)
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
                    if suf in self._vowel_final_only and not _vowel_final(stem):
                        # ঘর + র is not a word Bengali can build; the genitive
                        # there is ঘরের. Accepting it would let কাপর pass as
                        # কাপ + genitive and hide a real spelling error.
                        continue
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
        pool = self._pool_for(word)
        # Re-inflected stem corrections join the same pool rather than standing
        # in for it, and everything is ranked against the word the user typed.
        # Choosing between the two pools up front got this wrong twice: with the
        # stem path used only as a fallback, সিতকালে kept the direct pool's
        # সিটকাল and never saw শীতকালে; with the first workable suffix winning,
        # পূকুরপারে split as পূকুরপা + রে and produced পুকুরপাড়রে instead of
        # পুকুরপাড়ে. Ranking every reconstruction against the original settles
        # both, because the closest one is the answer by definition.
        pool.update(self._stem_reconstructions(word, limit))
        pool.discard(word)
        return rank_candidates(
            word,
            list(pool),
            max_distance=2,
            phonetic_key=soundex,
            frequency=self._freq,
            prefer=homophone_substitution,
            limit=limit,
        )

    def _pool_for(self, word: str) -> set[str]:
        pool: set[str] = set(self._by_key.get(soundex(word), []))
        for length in range(max(1, len(word) - 2), len(word) + 3):
            pool.update(self._by_len.get(length, []))
        return pool

    def _stem_reconstructions(self, word: str, limit: int) -> list[str]:
        """Correct the stem, then put the suffix back.

        A dictionary stores stems. Bengali writes inflected forms, and the two
        are routinely further apart than the distance filter allows: সিতকালে is
        three edits from শীতকাল — স→শ, ি→ী, and the ে that শীতকাল does not carry
        — so the correction was rejected as too distant and the writer was
        offered সিটকাল, which is neither the right word nor the right form.

        Peeling a suffix the lexicon already recognises brings the comparison
        back to stem against stem, where the real error is the only difference.
        সিতকাল → শীতকাল is one homophone swap plus one vowel-length swap, well
        inside the window, and re-attaching ে hands back শীতকালে — a form the
        writer can accept without editing it further.

        Every viable split contributes; the caller ranks them all against the
        original. Not a morphological generator — it re-attaches the exact
        suffix it removed and attempts no sandhi, which is Phase 4's job.
        """
        out: list[str] = []
        explored = 0
        for suf in self._suffixes:
            if len(word) <= len(suf) + 1 or not word.endswith(suf):
                continue
            stem = word[: len(word) - len(suf)]
            if suf in self._vowel_final_only and not _vowel_final(stem):
                continue
            if self.lookup(stem).known:
                # The stem is fine, so the suffix is the unusual part. Guessing
                # a different one would be a CASE_MARKER opinion, not a spelling
                # one, and this class does not hold those.
                continue
            # Each split costs a full pool scan, and a long agglutinated word
            # matches a dozen suffixes. Suffixes are sorted longest-first, and
            # the useful splits are the long ones — a one-character split leaves
            # a stem barely shorter than the word, which the direct pool already
            # covered. Capping here is what keeps p99 inside the spec §10 budget.
            explored += 1
            if explored > MAX_STEM_SPLITS:
                break
            # Phonetic bucket only, not the length window the direct pool uses.
            # The length window means scanning five buckets of an 80k lexicon,
            # and it is what pushed p99 past the budget once this ran on every
            # unknown word. It also buys nothing here: a stem worth correcting
            # is one the writer misheard rather than mistyped, so it shares the
            # misspelling's sound. Every case this pass was added for — the
            # ড়/র and ণ/ন swaps — is inside the bucket by construction.
            out.extend(
                cand + suf
                for cand in rank_candidates(
                    stem,
                    [c for c in self._by_key.get(soundex(stem), []) if c != stem],
                    max_distance=2,
                    phonetic_key=soundex,
                    frequency=self._freq,
                    prefer=homophone_substitution,
                    limit=limit,
                )
            )
        return out


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
        vowel_final_only: Iterable[str] = (),
    ) -> None:
        try:
            from spylls.hunspell import Dictionary
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "spylls is not installed; run `pip install -e '.[hunspell]'` "
                "or fall back to the bundled seed lexicon"
            ) from exc
        self._dict = Dictionary.from_files(str(dic_path.with_suffix("")))
        # A dictionary can parse cleanly and still be useless. A truncated
        # download leaves a valid-looking .dic with almost no stems, and that
        # does not fail — it produces a lexicon that rejects ordinary Bengali
        # and flags every word as NON_WORD, which is the single worst thing this
        # checker can do (spec §8). bn_BD ships ~88k stems; anything within an
        # order of magnitude of nothing is a broken file, not a small dictionary.
        stems = len(self._dict.dic.words)
        if stems < MIN_HUNSPELL_STEMS:
            raise ValueError(
                f"{dic_path.name} parsed but holds only {stems} stems "
                f"(expected >= {MIN_HUNSPELL_STEMS}); treating it as corrupt"
            )
        # Union, not replacement. The seed list and data/extra_words.txt carry
        # সাধু forms and চলিত future tenses that bn_BD lacks; loading the real
        # dictionary must not throw them away, or installing a better dictionary
        # would make the checker noisier.
        words = [w.stem for w in self._dict.dic.words]
        words.extend(supplement)
        super().__init__(
            words, suffixes, prefixes=prefixes, vowel_final_only=vowel_final_only
        )
        self._suggest_cache: dict[str, list[str]] = {}
        self._suggester_broken = False
        self._use_hunspell_suggester = (
            os.environ.get("BHASHASETU_HUNSPELL_SUGGEST", "") == "1"
        )

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
        """Candidates from the phonetic and length pools, re-ranked.

        WHY NOT SPYLLS' OWN SUGGESTER, which this class obviously ought to use:
        it is too slow to run while someone is typing. Measured on bn_BD, one
        cold unknown word:

            কাপর          3.5 s
            শিকর          5.6 s
            বিখ্যত       12.7 s
            সিতকালে      16.9 s
            পূকুরপারে    16.5 s

        against a spec §10 budget of p95 < 800 ms for a whole document. The
        editor re-checks 600 ms after each pause, so a five-word sentence with
        four unknown words took 38 seconds to come back. Taking the generator
        lazily does not help: the cost is in the affix and n-gram exploration
        that runs before the first yield.

        This is worth stating plainly because the call was already here and had
        never once executed — it read `self._dict.suggester.suggest(...)`, which
        does not exist (spylls names that method `suggestions`), inside a bare
        `except Exception`. So every suggestion this checker has ever made came
        from the pools below, and the measurements above are what it costs to
        "fix" that. Quality is genuinely better with spylls — it puts কাপড়
        second for কাপর — but not at 38 seconds.

        What closes most of the gap for free is ranking, not recall: the right
        word was usually in the pool already and sorted below a coincidence.
        See `homophone_substitution`, and `_FOLD` for the র/ড় class that had to
        be corrected before কাপড় was reachable at all.

        Set `BHASHASETU_HUNSPELL_SUGGEST=1` to use spylls anyway — reasonable
        for CLI or batch work, where latency is nobody's problem.
        """
        cached = self._suggest_cache.get(word)
        if cached is not None:
            return cached[:limit]
        if not self._use_hunspell_suggester:
            return super().suggest(word, limit)
        try:
            candidates = list(self._dict.suggest(word))
        except Exception as exc:  # pragma: no cover - suggester is best-effort
            # Still best-effort — a suggester that throws must not take the
            # request down — but never silent again. That silence is what let a
            # method that never ran look like a working one for this long.
            if not self._suggester_broken:
                self._suggester_broken = True
                print(
                    f"WARNING: Hunspell suggester failed ({type(exc).__name__}: "
                    f"{exc}); falling back to the phonetic and length pools. "
                    "Suggestion quality is degraded, not absent.",
                    file=sys.stderr,
                )
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
    vowel_final_only: list[str] = list(suffix_cfg.get("vowel_final_only", []))

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
    if not hunspell_dic.exists():
        # The quiet path, and the one that actually bit in production. A
        # dictionary that fails to LOAD already warned below; a dictionary that
        # was never fetched said nothing at all and returned a working-looking
        # pack. The consequence is not partial: `coverage_factor` scales
        # NON_WORD confidence by ~650/150000, so every spelling flag arrives at
        # 0.003 against a 0.55 display gate and the checker reports misspelt
        # Bengali as clean. Nothing downstream can tell that apart from "no
        # errors found", so this has to be said here.
        print(
            f"WARNING: no Bengali dictionary at {hunspell_dic.parent}. Running "
            f"on the {len(words) + len(extra)}-word seed lexicon, which damps "
            "unknown-word confidence below the display threshold — SPELLING "
            "ERRORS WILL NOT BE REPORTED. Grammar, register and punctuation "
            "still work. Fix with: python scripts/fetch_dictionaries.py --yes",
            file=sys.stderr,
        )
    if hunspell_dic.exists():
        try:
            lex = HunspellLexicon(
                hunspell_dic,
                suffixes,
                supplement=[*words, *extra],
                prefixes=prefixes,
                vowel_final_only=vowel_final_only,
            )
        except Exception as exc:
            # Broad on purpose. This used to catch RuntimeError only, which
            # covered a missing spylls and nothing else — so a *half-fetched*
            # dictionary took the whole pack down: .dic present, .aff missing,
            # spylls raises FileNotFoundError, and `get_pack("bn")` dies. In a
            # container build that is a failed deploy, and the message names
            # spylls' internals rather than the dictionary.
            #
            # A dictionary that will not load is a degraded checker, never a
            # dead one: the seed list below still runs, with unknown-word
            # confidence damped under the display threshold. Say so loudly and
            # carry on.
            print(
                f"WARNING: Hunspell dictionary at {hunspell_dic.parent} could not "
                f"be loaded ({type(exc).__name__}: {exc}); falling back to the "
                f"{len(words)}-word seed lexicon. Spelling errors will be "
                "detected but held below the display threshold. "
                "Re-run scripts/fetch_dictionaries.py --yes to repair it.",
                file=sys.stderr,
            )
        else:
            return lex
    return BengaliLexicon(
        [*words, *extra],
        suffixes,
        freq,
        prefixes=prefixes,
        vowel_final_only=vowel_final_only,
    )
