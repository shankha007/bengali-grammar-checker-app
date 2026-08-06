"""Stage 1 - lexical and rule-based detection.

Deviation from the spec, stated up front: spec §1 labels Stage 1 "LEXICAL"
(Hunspell + candidate ranking). This implementation also runs the punctuation
and register rules here, because they are pure pattern matching over the same
token stream - routing them through a neural stage would cost latency and buy
nothing. Stage 2 keeps its full remit; it just does not have to re-derive facts a
regex already settled.

Classes emitted at Stage 1:
    NON_WORD             lexicon miss after suffix stripping
    NOTVA_SHOTVA         explicit তৎসম violation list
    HOMONYM              collocation rules only (recall is near zero by design)
    GURUCHANDALI_DOSHA   সাধু/চলিত mixing inside one sentence
    REGISTER_INCONSISTENCY  document-level register drift
    PUNCTUATION          dari spacing, Latin period as terminator, repeats
    VERB_INFLECTION      পুরুষ/সম্ভ্রম agreement, pronoun subjects only

VERB_INFLECTION is the one partial entry in that list, and the partiality is the
point. The general class needs a parser - the subject can be any noun phrase.
The case that actually occurs in writing is a pronoun subject and a finite verb,
both closed sets, and that is a table lookup: see data/verb_person.yaml, which
also documents what is left to Phase 2 rather than guessed.

Not emitted at Stage 1, and not faked: CASE_MARKER, CLASSIFIER, WORD_ORDER,
POS_ERROR, AGREEMENT. These need the token classifier from Phase 2. `make eval`
reports 0.0 recall on those slices rather than hiding them.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from bhashasetu.core.pipeline import new_edit_id
from bhashasetu.core.types import (
    Edit,
    ErrorClass,
    ErrorClassSpec,
    Sentence,
    Stage,
    Token,
)
from bhashasetu.language_packs.bn import chars as C
from bhashasetu.language_packs.bn.lexicon import BengaliLexicon
from bhashasetu.language_packs.bn.tokenizer import BengaliTokenizer

_DATA = Path(__file__).parent / "data"


def _load(name: str) -> dict[str, Any]:
    return yaml.safe_load((_DATA / name).read_text(encoding="utf-8")) or {}


@dataclass(slots=True)
class _PersonTables:
    """Subject/verb পুরুষ agreement. See data/verb_person.yaml for the rules and
    for the four precision devices this implements."""

    subjects: dict[str, str]
    # Pronouns that are also something commoner (ও "and", এ "this"). They block
    # the rule when they co-occur with a real subject, but are never used as the
    # subject themselves. See data/verb_person.yaml.
    ambiguous_subjects: frozenset[str]
    classifier_suffixes: tuple[str, ...]
    classifier_min_stem: int
    clause_breaks: frozenset[str]
    clause_break_punctuation: frozenset[str]
    final_particles: frozenset[str]
    not_verbs: frozenset[str]
    phrase_heads_before_verb: frozenset[str]
    clause_final_only_endings: frozenset[str]
    animal_nouns: frozenset[str]
    # (ending, paradigm name, the persons that ending is correct for). Sorted
    # longest-first so েছি wins over ছি.
    endings: tuple[tuple[str, str, frozenset[str]], ...]
    paradigms: dict[str, dict[str, str]]
    roots: frozenset[str]
    confidence: float

    def subject_person(self, word: str) -> str | None:
        return self.subjects.get(word)

    def classifier_subject(
        self, word: str, stripped: Callable[[str], tuple[str, ...]]
    ) -> bool:
        """A noun carrying a classifier: ছেলেটি, কুকুরটি, বইগুলো.

        Ending in টি is not enough - বৃষ্টি and সৃষ্টি do too, and reading them
        as "rain"/"creation" plus a classifier invented both a subject and an
        agreement error on correct sentences.

        `stripped` is the lexicon's own account of how it recognised the word:
        the suffixes it peeled off to get there, empty for a word it knows
        outright. That is exactly the distinction needed. ছেলেটি is known only
        after peeling টি; বৃষ্টি is known as itself.
        """
        if not any(word.endswith(s) for s in self.classifier_suffixes):
            return False
        return any(s in self.classifier_suffixes for s in stripped(word))

    def analyse(
        self, word: str, *, clause_final: bool = True
    ) -> tuple[str, str, frozenset[str]] | None:
        """(stem, paradigm, persons) for the longest ending on a known root.

        `clause_final` says whether this word ends its clause. Some endings are
        only a finite verb in that position - see clause_final_only_endings.
        """
        if word in self.not_verbs:
            return None
        for ending, paradigm, persons in self.endings:
            if not word.endswith(ending):
                continue
            if ending in self.clause_final_only_endings and not clause_final:
                continue
            stem = word[: len(word) - len(ending)]
            if stem in self.roots:
                return stem, paradigm, persons
        return None

    def correct_form(self, stem: str, paradigm: str, person: str) -> str | None:
        ending = self.paradigms.get(paradigm, {}).get(person)
        return stem + ending if ending is not None else None


@dataclass(slots=True)
class _ClassifierTables:
    """পদাশ্রিত নির্দেশক ও বচন. See data/classifier.yaml."""

    plural_quantifiers: frozenset[str]
    plural_suffixes: tuple[str, ...]
    quantifier_window: int
    thing_to_person: dict[str, str]
    person_to_thing: dict[str, str]
    classifier_window: int
    person_nouns: frozenset[str]
    thing_nouns: frozenset[str]
    absorbed_after_numeral: frozenset[str]
    person_noun_case_suffixes: tuple[str, ...]
    inanimate_plural: str
    possessive_for_plural_subject: dict[str, dict[str, str]]
    plural_noun_possessive: dict[str, str]
    confidence: float
    double_plural_confidence: float
    inanimate_plural_confidence: float
    possessive_confidence: float

    def is_person_noun(self, word: str) -> bool:
        if word in self.person_nouns:
            return True
        return any(
            word.endswith(suffix)
            and word[: len(word) - len(suffix)] in self.person_nouns
            for suffix in self.person_noun_case_suffixes
        )

    def singular_of(self, word: str) -> str | None:
        """ছাত্ররা → ছাত্র. Longest suffix first, so েরা beats রা."""
        for suffix in sorted(self.plural_suffixes, key=len, reverse=True):
            if word.endswith(suffix) and len(word) - len(suffix) >= 2:
                return word[: len(word) - len(suffix)]
        return None


@dataclass(slots=True)
class _RegisterTables:
    sadhu_to_cholito: dict[str, str]
    cholito_to_sadhu: dict[str, str]
    sadhu_endings: tuple[str, ...]
    sadhu_endings_guarded: tuple[str, ...]
    sadhu_guard_min_stem: int
    verb_stems: frozenset[str]
    cholito_endings_priority: tuple[str, ...]
    cholito_endings: tuple[str, ...]
    # word -> (সাধু equivalent, words it must follow to count as চলিত)
    contextual_cholito: dict[str, tuple[str, frozenset[str]]]
    # সাধু ending -> চলিত ending, longest first
    derivation: tuple[tuple[str, str], ...]
    derivation_min_stem: int
    config: dict[str, Any]

    def to_cholito(self, word: str) -> str | None:
        """The চলিত form of a সাধু word: the pairs table, else the regular
        derivation. See register.yaml - `pairs` wins because the regular rule is
        wrong for precisely the irregular verbs listed there.
        """
        listed = self.sadhu_to_cholito.get(word)
        if listed:
            return listed

        # Derive from the LONGEST সাধু ending the word carries, not the first
        # one in the derivation table that happens to match. খাইতেছিলেন ends in
        # ইতেছিলেন and also, incidentally, in িলেন - and swapping the short one
        # produced খাইতেছলেন, which is not a word in any register. An ending
        # that has no derivation is left alone: no suggestion beats a wrong one.
        ending = max(
            (e for e in self._sadhu_endings_all if word.endswith(e)),
            key=len,
            default=None,
        )
        if ending is None:
            return None
        cholito_end = dict(self.derivation).get(ending)
        if cholito_end is None:
            return None
        stem = word[: len(word) - len(ending)]
        if len(stem) < self.derivation_min_stem:
            return None
        return stem + cholito_end

    @property
    def _sadhu_endings_all(self) -> tuple[str, ...]:
        return self.sadhu_endings + self.sadhu_endings_guarded

    def contextual_label(self, word: str, previous: str | None) -> str | None:
        """চলিত, but only in the right company. See register.yaml: পরে is the
        participle after a garment and the postposition "after" everywhere
        else, and only the first is register evidence."""
        entry = self.contextual_cholito.get(word)
        if entry is None or previous is None:
            return None
        return "cholito" if previous in entry[1] else None

    def contextual_sadhu_form(self, word: str) -> str | None:
        entry = self.contextual_cholito.get(word)
        return entry[0] if entry else None

    def label(self, word: str) -> str | None:
        """সাধু / চলিত / unmarked. Order matters - see register.yaml."""
        if word in self.sadhu_to_cholito:
            return "sadhu"
        if any(word.endswith(e) for e in self.sadhu_endings):
            return "sadhu"
        # Before the guarded সাধু endings, not after: the guard measures stem
        # length, and চলিত past continuous (বলছিলে, করছিলাম) has a long enough
        # stem to pass it while being unambiguously চলিত.
        if any(word.endswith(e) for e in self.cholito_endings_priority):
            return "cholito"
        for end in self.sadhu_endings_guarded:
            if not word.endswith(end):
                continue
            stem = word[: len(word) - len(end)]
            if len(stem) < self.sadhu_guard_min_stem:
                # Too short to be this ending's stem: the ি belongs to the word
                # itself (দিলাম, নিলাম). Keep looking - these are চলিত, and the
                # চলিত tests below are the ones that should decide.
                continue
            if stem in self.verb_stems:
                return "sadhu"
            # Long enough, but not a verb: unmarked, and stop looking. Falling
            # through to the চলিত tests would be worse than saying nothing -
            # কিনিলেন ends in "লেন" and would come back চলিত, turning a correct
            # সাধু sentence into a clash.
            return None
        if word in self.cholito_to_sadhu:
            return "cholito"
        if any(word.endswith(e) for e in self.cholito_endings):
            return "cholito"
        return None


class BengaliRuleDetector:
    stage: Stage = 1

    # Hunspell's suggester costs ~400 ms on a cold unknown word - it explores the
    # affix machinery, and no amount of caching helps the first occurrence.
    # Spec §10 budgets p95 < 800 ms for a 200-word document through stages 0-3,
    # so an unbounded one-call-per-unknown-word policy blows the budget on any
    # document with a handful of proper nouns.
    #
    # Past this many suggester calls in a single request, edits are still emitted
    # - the user still sees the word flagged, with its explanation - just without
    # ranked alternatives. Losing suggestions on the 26th unknown word in one
    # document is a far smaller harm than a checker that stalls.
    max_suggest_calls: int = 25

    def __init__(
        self,
        lexicon: BengaliLexicon,
        tokenizer: BengaliTokenizer,
        error_classes: dict[ErrorClass, ErrorClassSpec],
    ) -> None:
        self.lexicon = lexicon
        self.tokenizer = tokenizer
        self.specs = error_classes

        ns = _load("notva_shotva.yaml")
        self._violations: dict[str, tuple[str, str]] = {
            v["wrong"]: (v["right"], v.get("rule", "ণত্ব/ষত্ব-বিধান"))
            for v in ns.get("violations", [])
        }

        conf = _load("confusions.yaml")
        self._collocations = conf.get("collocations", [])

        reg = _load("register.yaml")
        pairs = reg.get("pairs", [])
        self._register = _RegisterTables(
            sadhu_to_cholito={p["sadhu"]: p["cholito"] for p in pairs},
            cholito_to_sadhu={p["cholito"]: p["sadhu"] for p in pairs},
            sadhu_endings=tuple(reg.get("sadhu_endings", [])),
            sadhu_endings_guarded=tuple(reg.get("sadhu_endings_guarded", [])),
            sadhu_guard_min_stem=int(reg.get("sadhu_guard_min_stem", 2)),
            verb_stems=frozenset(reg.get("verb_stems", [])),
            cholito_endings_priority=tuple(reg.get("cholito_endings_priority", [])),
            cholito_endings=tuple(reg.get("cholito_endings", [])),
            contextual_cholito={
                entry["word"]: (entry.get("sadhu", ""), frozenset(entry.get("after", [])))
                for entry in reg.get("cholito_markers_in_context", [])
            },
            derivation=tuple(
                sorted(
                    reg.get("cholito_derivation", {}).get("endings", {}).items(),
                    key=lambda item: -len(item[0]),
                )
            ),
            derivation_min_stem=int(
                reg.get("cholito_derivation", {}).get("min_stem", 2)
            ),
            config=reg.get("detection", {}),
        )

        vp = _load("verb_person.yaml")
        paradigms: dict[str, dict[str, str]] = vp.get("paradigms", {})
        # Collapse the paradigm tables into one ending list. An ending can be
        # correct for several persons (বে is both second_familiar and
        # third_familiar), and within one paradigm the honorific columns are
        # identical, so the value is a set rather than a single person.
        ambiguous = set(vp.get("ambiguous_endings", []))
        by_ending: dict[tuple[str, str], set[str]] = {}
        for name, table in paradigms.items():
            for person, ending in table.items():
                if ending in ambiguous:
                    # Recognition only. The cell stays in `paradigms` because a
                    # correction may still need to generate it.
                    continue
                by_ending.setdefault((ending, name), set()).add(person)
        self._person = _PersonTables(
            subjects=dict(vp.get("subjects", {})),
            ambiguous_subjects=frozenset(vp.get("ambiguous_subjects", [])),
            classifier_suffixes=tuple(vp.get("classifier_suffixes", [])),
            classifier_min_stem=int(vp.get("classifier_min_stem", 2)),
            clause_breaks=frozenset(vp.get("clause_breaks", [])),
            clause_break_punctuation=frozenset(vp.get("clause_break_punctuation", [])),
            final_particles=frozenset(vp.get("final_particles", [])),
            not_verbs=frozenset(vp.get("not_verbs", [])),
            phrase_heads_before_verb=frozenset(vp.get("phrase_heads_before_verb", [])),
            clause_final_only_endings=frozenset(vp.get("clause_final_only_endings", [])),
            animal_nouns=frozenset(vp.get("animal_nouns", [])),
            endings=tuple(
                sorted(
                    ((e, n, frozenset(p)) for (e, n), p in by_ending.items()),
                    key=lambda item: -len(item[0]),
                )
            ),
            paradigms=paradigms,
            roots=frozenset(vp.get("roots", [])),
            confidence=float(vp.get("detection", {}).get("confidence", 0.86)),
        )

        cl = _load("classifier.yaml")
        cl_conf = cl.get("detection", {})
        self._classifier = _ClassifierTables(
            plural_quantifiers=frozenset(cl.get("plural_quantifiers", [])),
            plural_suffixes=tuple(cl.get("plural_suffixes", [])),
            quantifier_window=int(cl.get("quantifier_window", 2)),
            thing_to_person=dict(cl.get("thing_to_person", {})),
            person_to_thing=dict(cl.get("person_to_thing", {})),
            classifier_window=int(cl.get("classifier_window", 3)),
            person_nouns=frozenset(cl.get("person_nouns", [])),
            thing_nouns=frozenset(cl.get("thing_nouns", [])),
            absorbed_after_numeral=frozenset(cl.get("absorbed_after_numeral", [])),
            person_noun_case_suffixes=tuple(cl.get("person_noun_case_suffixes", [])),
            inanimate_plural=str(cl.get("inanimate_plural", "গুলো")),
            possessive_for_plural_subject=dict(cl.get("possessive_for_plural_subject", {})),
            plural_noun_possessive=dict(cl.get("plural_noun_possessive", {})),
            confidence=float(cl_conf.get("confidence", 0.8)),
            double_plural_confidence=float(cl_conf.get("double_plural_confidence", 0.84)),
            inanimate_plural_confidence=float(
                cl_conf.get("inanimate_plural_confidence", 0.82)
            ),
            possessive_confidence=float(cl_conf.get("possessive_confidence", 0.82)),
        )

        sf = _load("standard_forms.yaml")
        self._standard: dict[str, tuple[str, str]] = {
            f["wrong"]: (f["right"], f.get("note", ""))
            for f in sf.get("forms", [])
        }
        # The wording lives in the language pack, not here: core logic must never
        # carry a language-specific message (see core/error_classes.py).
        self._standard_templates: tuple[str, str] = (
            sf.get("explanation_native", ""),
            sf.get("explanation_en", ""),
        )
        self._standard_rule: str = sf.get("rule_reference", "")
        self._standard_confidence: float = float(
            sf.get("detection", {}).get("confidence", 0.62)
        )

    # ------------------------------------------------------------------
    def detect(self, text: str, sentences: list[Sentence]) -> list[Edit]:
        edits: list[Edit] = []
        per_sentence_register: list[str | None] = []
        budget = [self.max_suggest_calls]

        for sent in sentences:
            words = self.tokenizer.words(sent.text, offset=sent.start)
            edits.extend(self._spelling(words, budget))
            edits.extend(self._collocation(words))
            edits.extend(self._verb_person(text, words))
            edits.extend(self._classifier_agreement(words))
            edits.extend(self._standard_forms(words))
            reg_edits, dominant = self._register_clash(sent, words)
            edits.extend(reg_edits)
            per_sentence_register.append(dominant)

        edits.extend(self._punctuation(text))
        edits.extend(self._register_drift(sentences, per_sentence_register))
        return edits

    # ------------------------------------------------------------------
    def _spelling(self, words: list[Token], budget: list[int]) -> list[Edit]:
        out: list[Edit] = []
        damp = self.lexicon.coverage_factor
        for tok in words:
            word = tok.text
            if not BengaliTokenizer.is_bengali_word(word):
                continue

            fix = self._violations.get(word)
            if fix is not None:
                right, rule = fix
                out.append(
                    self._edit(
                        ErrorClass.NOTVA_SHOTVA,
                        tok,
                        [right],
                        # Explicit, hand-checked list. High confidence is earned
                        # here in a way it is not for the generative rule.
                        confidence=0.93,
                        rule_reference=rule,
                        wrong=word,
                        right=right,
                        # The NOTVA_SHOTVA template cites the specific বিধান
                        # clause inline; without this the user reads a literal
                        # "{rule}" in the middle of the explanation.
                        rule=rule,
                    )
                )
                continue

            if word in self._standard:
                # Handled by _standard_forms, which knows *why* it is wrong.
                # Same precedence as the ণত্ব list above: a specific
                # explanation beats "not in the dictionary".
                continue

            if self.lexicon.contains(word):
                continue

            # সাধু forms are archaic, not misspelt. bn_BD's coverage of them is
            # patchy (কিনিলেন, দিয়াছে, আমাদিগের are all absent), and flagging
            # correct literary Bengali as a spelling error is a systematic
            # failure, not an occasional one. If the register labeller - which
            # models সাধু morphology directly - recognises the form, defer to it.
            # A genuine সাধু misspelling escapes; that trade favours precision,
            # which is what F0.5 asks for.
            if self._register.label(word) == "sadhu":
                continue

            if budget[0] > 0:
                budget[0] -= 1
                suggestions = self.lexicon.suggest(word, limit=5)
            else:
                suggestions = []
            # An unknown word with no near neighbour is much more likely to be a
            # proper noun, a loanword, or a gap in our dictionary than a typo.
            base = 0.72 if suggestions else 0.35
            out.append(
                self._edit(
                    ErrorClass.NON_WORD,
                    tok,
                    suggestions,
                    confidence=base * damp,
                    wrong=word,
                    right=suggestions[0] if suggestions else "",
                    debug={
                        "lexicon_size": self.lexicon.size,
                        "coverage_factor": round(damp, 3),
                    },
                )
            )
        return out

    def _collocation(self, words: list[Token]) -> list[Edit]:
        out: list[Edit] = []
        forms = [w.text for w in words]
        for i, tok in enumerate(words):
            for rule in self._collocations:
                if tok.text != rule["wrong"]:
                    continue
                nxt = forms[i + 1] if i + 1 < len(forms) else None
                prv = forms[i - 1] if i > 0 else None
                before_ok = bool(rule.get("before")) and nxt in rule["before"]
                after_ok = bool(rule.get("after")) and prv in rule["after"]
                if not (before_ok or after_ok):
                    continue
                out.append(
                    self._edit(
                        ErrorClass.HOMONYM,
                        tok,
                        [rule["right"]],
                        confidence=float(rule.get("confidence", 0.6)),
                        wrong=rule["wrong"],
                        right=rule["right"],
                        debug={"note": rule.get("note", "")},
                    )
                )
        return out

    def _verb_person(self, text: str, words: list[Token]) -> list[Edit]:
        """পুরুষ ও সম্ভ্রম agreement: আমি ভাত খাইবেন → খাইব.

        Reads as four filters, each one a way this rule could otherwise invent
        an error. They are described in full in data/verb_person.yaml.
        """
        p = self._person

        # 1. Exactly one subject. Two pronouns means two clauses at least one of
        #    which we cannot attribute, and no subject at all means the rule has
        #    nothing to agree against.
        #
        #    Ambiguous pronouns (ও, এ) count toward that census but cannot be
        #    the subject: they are far commoner as "and" and "this". Counting
        #    them keeps "সে ও আমি যাব।" bailing out; not electing them keeps
        #    "রাম ও শ্যাম বাজারে গেলেন।" — correct prose — unflagged.
        candidates = [
            (i, t)
            for i, t in enumerate(words)
            if p.subject_person(t.text) or t.text in p.ambiguous_subjects
        ]
        if len(candidates) > 1:
            return []
        subjects = [(i, t) for i, t in candidates if p.subject_person(t.text)]
        # A noun subject licenses one narrow judgement only - see below.
        noun_subject = not subjects
        if subjects:
            index, subject_tok = subjects[0]
            person = p.subject_person(subject_tok.text)
        else:
            def stripped(word: str) -> tuple[str, ...]:
                found = self.lexicon.lookup(word)
                return found.stripped_suffixes if found.known else ()

            nouns = [
                (i, t) for i, t in enumerate(words) if p.classifier_subject(t.text, stripped)
            ]
            if len(nouns) != 1:
                return []
            index, subject_tok = nouns[0]
            person = "third_familiar"
        if person is None:  # pragma: no cover - subjects table guarantees this
            return []

        # 2. The subject's clause, and no further. A clause ends at one of the
        #    conjunctions in `clause_breaks`, or at punctuation — and the
        #    punctuation has to be read out of the gap between two word tokens,
        #    because the tokenizer does not emit it as a word of its own.
        end = len(words)
        for i in range(index + 1, len(words)):
            gap = text[words[i - 1].end : words[i].start]
            if any(ch in p.clause_break_punctuation for ch in gap):
                end = i
                break
            if words[i].text in p.clause_breaks:
                end = i
                break
        clause = words[index + 1 : end]

        # 3. The last recognised verb form in that clause, skipping the
        #    particles that trail it. Earlier matches are participles.
        verb: Token | None = None
        analysis: tuple[str, str, frozenset[str]] | None = None
        seen_content_word = False
        for position in range(len(clause) - 1, -1, -1):
            tok = clause[position]
            if tok.text in p.final_particles:
                continue
            if position and clause[position - 1].text in p.phrase_heads_before_verb:
                seen_content_word = True
                continue  # দয়া করে — a fixed phrase, not this clause's verb
            found = p.analyse(tok.text, clause_final=not seen_content_word)
            seen_content_word = True
            if found is not None:
                verb, analysis = tok, found
                break
        if verb is None or analysis is None:
            return []

        stem, paradigm, ok_for = analysis
        if person in ok_for:
            return []

        # A noun subject is not a parse. All it supports is the one judgement
        # that needs no parse: a non-human subject cannot take the honorific
        # verb. Anything else - "বইটি পড়ে শেষ করেছি।", where বইটি is the object
        # and the subject is an unwritten আমি - is Phase 2's problem, and
        # guessing it produced exactly that false positive.
        honorific_only = ok_for <= {"second_honorific", "third_honorific"}
        if noun_subject and not honorific_only:
            return []

        right = p.correct_form(stem, paradigm, person)
        if right is None:
            # The paradigm has no cell for this person - সাধু tables omit the
            # intimate column. Better to say nothing than to name a form that
            # does not exist.
            return []

        # Which class this is depends on what the subject is, and the gold set's
        # own boundary rule decides it: person/honorific is VERB_INFLECTION,
        # number/animacy is AGREEMENT. ছেলেটি খেলছেন and কুকুরটি ডাকছেন are the
        # honorific form used of an animate thing - a পুরুষ error. নদীটি গেছেন
        # is a river taking an honorific, which is animacy.
        klass = ErrorClass.VERB_INFLECTION
        if noun_subject:
            head = subject_tok.text
            animate = any(
                head.startswith(n)
                for n in (*self._classifier.person_nouns, *p.animal_nouns)
            )
            klass = ErrorClass.VERB_INFLECTION if animate else ErrorClass.AGREEMENT

        return [
            self._edit(
                klass,
                verb,
                [right],
                confidence=p.confidence,
                wrong=verb.text,
                right=right,
                debug={
                    "subject": subject_tok.text,
                    "person": person,
                    "paradigm": paradigm,
                    "verb_persons": sorted(ok_for),
                },
            )
        ]

    def _classifier_agreement(self, words: list[Token]) -> list[Edit]:
        """সব ছাত্ররা → সব ছাত্র, and একটি নারী → একজন নারী.

        Both halves work forward from a closed trigger - a plural quantifier or
        a numeral+classifier - and both refuse to fire unless the noun they
        reach is in one of the two hand-written lists. Animacy is never guessed.
        """
        c = self._classifier
        out: list[Edit] = []

        for i, tok in enumerate(words):
            # 1. Double plural: the quantifier already says "many".
            if tok.text in c.plural_quantifiers:
                for nxt in words[i + 1 : i + 1 + c.quantifier_window]:
                    singular = c.singular_of(nxt.text)
                    if singular is None or not self.lexicon.contains(singular):
                        continue
                    out.append(
                        self._edit(
                            ErrorClass.CLASSIFIER,
                            nxt,
                            [singular],
                            confidence=c.double_plural_confidence,
                            wrong=nxt.text,
                            right=singular,
                            debug={"quantifier": tok.text},
                        )
                    )
                    break

            # 2 & 3. Animacy. -টি counts things, -জন counts people.
            for table, matches, wrong_kind in (
                (c.thing_to_person, c.is_person_noun, "thing-classifier on a person"),
                (c.person_to_thing, c.thing_nouns.__contains__, "person-classifier on a thing"),
            ):
                right_form = table.get(tok.text)
                if right_form is None:
                    continue
                window = words[i + 1 : i + 1 + c.classifier_window]
                head = next((w for w in window if matches(w.text)), None)
                if head is None:
                    continue
                # "দশটি জন শ্রমিক" is one error spelt across two words; replacing
                # only দশটি would leave "দশজন জন" behind.
                span_end = tok.end
                original = tok.text
                if window and window[0].text in c.absorbed_after_numeral:
                    span_end = window[0].end
                    original = f"{tok.text} {window[0].text}"
                out.append(
                    self._span_edit(
                        ErrorClass.CLASSIFIER,
                        tok.start,
                        span_end,
                        original,
                        [right_form],
                        confidence=c.confidence,
                        wrong=original,
                        right=right_form,
                        debug={"head_noun": head.text, "note": wrong_kind},
                    )
                )
                break

            # 4. Animate plural on an inanimate noun: বইরা → বইগুলো.
            #
            # The pronoun guard is not decoration. আমরা ends in রা and strips to
            # আম, which is in the thing list, so without it the checker told
            # people writing "আমরা" that they meant "আমগুলো" - on six sentences
            # of the clean set.
            base = c.singular_of(tok.text)
            if (
                base is not None
                and base in c.thing_nouns
                and tok.text.endswith("রা")
                and tok.text not in self._person.subjects
            ):
                out.append(
                    self._edit(
                        ErrorClass.AGREEMENT,
                        tok,
                        [base + c.inanimate_plural],
                        confidence=c.inanimate_plural_confidence,
                        wrong=tok.text,
                        right=base + c.inanimate_plural,
                        debug={"note": "-রা is the animate plural"},
                    )
                )

            # 5. Possessive that disagrees with a plural subject.
            table_for_subject = c.possessive_for_plural_subject.get(tok.text)
            if table_for_subject is None and c.singular_of(tok.text) is not None:
                # A plural NOUN subject (ছেলেরা, শ্রমিকেরা) governs the same
                # third-person correction.
                table_for_subject = c.plural_noun_possessive
            if table_for_subject:
                for nxt in words[i + 1 :]:
                    fixed = table_for_subject.get(nxt.text)
                    if fixed is None:
                        continue
                    out.append(
                        self._edit(
                            ErrorClass.AGREEMENT,
                            nxt,
                            [fixed],
                            confidence=c.possessive_confidence,
                            wrong=nxt.text,
                            right=fixed,
                            debug={"subject": tok.text},
                        )
                    )
                    break

        return out

    def _standard_forms(self, words: list[Token]) -> list[Edit]:
        """কালকে → কাল, যাবো → যাব.

        Filed under NON_WORD with an explanation carried by the data file, since
        neither word is missing from the lexicon and the class's usual wording
        would be a lie. data/standard_forms.yaml explains the taxonomy squeeze.
        """
        out: list[Edit] = []
        bn_tpl, en_tpl = self._standard_templates
        for tok in words:
            found = self._standard.get(tok.text)
            if found is None:
                continue
            right, note = found
            out.append(
                Edit(
                    id=new_edit_id(
                        ErrorClass.NON_WORD.value, tok.start, tok.end, tok.text, [right]
                    ),
                    start=tok.start,
                    end=tok.end,
                    original=tok.text,
                    suggestions=[right],
                    error_class=ErrorClass.NON_WORD,
                    confidence=self._standard_confidence,
                    stage=1,
                    explanation_bn=bn_tpl.format(wrong=tok.text, right=right),
                    explanation_en=en_tpl.format(wrong=tok.text, right=right),
                    rule_reference=self._standard_rule,
                    debug={"standard_form": True, "note": note},
                )
            )
        return out

    def _register_clash(
        self, sent: Sentence, words: list[Token]
    ) -> tuple[list[Edit], str | None]:
        """গুরুচণ্ডালী দোষ: both registers inside one sentence."""
        sadhu: list[Token] = []
        cholito: list[Token] = []
        for position, tok in enumerate(words):
            previous = words[position - 1].text if position else None
            label = self._register.label(tok.text)
            if label is None:
                label = self._register.contextual_label(tok.text, previous)
            if label == "sadhu":
                sadhu.append(tok)
            elif label == "cholito":
                cholito.append(tok)

        cfg = self._register.config
        need = int(cfg.get("min_markers_each", 1))
        dominant = (
            "sadhu"
            if len(sadhu) > len(cholito)
            else "cholito"
            if cholito
            else None
        )
        if len(sadhu) < need or len(cholito) < need:
            return [], dominant

        # Flag the minority forms - those are what the writer should change, and
        # flagging the majority would ask them to rewrite the whole sentence.
        minority = sadhu if len(sadhu) <= len(cholito) else cholito
        target_register = "চলিত" if minority is sadhu else "সাধু"
        out: list[Edit] = []
        for tok in minority:
            if minority is sadhu:
                # `pairs` first, then the regular ending swap - বসিয়া → বসে.
                # Before this, every সাধু form the endings caught but the pairs
                # table did not list came back with no suggestion at all.
                suggestion = self._register.to_cholito(tok.text)
            else:
                suggestion = self._register.cholito_to_sadhu.get(tok.text)
                if suggestion is None:
                    # Contextual markers carry their own সাধু counterpart.
                    suggestion = self._register.contextual_sadhu_form(tok.text)
            out.append(
                self._edit(
                    ErrorClass.GURUCHANDALI_DOSHA,
                    tok,
                    [suggestion] if suggestion else [],
                    confidence=float(cfg.get("confidence", 0.74)),
                    rule_reference="গুরুচণ্ডালী দোষ",
                    wrong=tok.text,
                    right=suggestion or "",
                    register=target_register,
                    debug={
                        "sadhu_markers": [t.text for t in sadhu],
                        "cholito_markers": [t.text for t in cholito],
                        "sentence": sent.index,
                    },
                )
            )
        return out, dominant

    def _register_drift(
        self, sentences: list[Sentence], registers: list[str | None]
    ) -> list[Edit]:
        """Document-level drift. Distinct from a within-sentence clash: a novel
        that quotes an archaic letter is not making an error."""
        cfg = self._register.config
        labelled = [r for r in registers if r]
        if len(labelled) < int(cfg.get("drift_min_sentences", 4)):
            return []
        sadhu = labelled.count("sadhu")
        cholito = labelled.count("cholito")
        total = sadhu + cholito
        minority = min(sadhu, cholito)
        ratio = minority / total if total else 0.0
        if ratio < float(cfg.get("drift_minority_ratio", 0.15)):
            return []

        # Anchor the flag on the first sentence written in the minority register -
        # that is where the reader first notices the seam.
        minority_label = "sadhu" if sadhu < cholito else "cholito"
        target = "সাধু" if minority_label == "cholito" else "চলিত"
        idx = next((i for i, r in enumerate(registers) if r == minority_label), 0)
        sent = sentences[idx] if idx < len(sentences) else sentences[0]
        spec = self.specs[ErrorClass.REGISTER_INCONSISTENCY]
        bn, en = spec.render(
            wrong="", right="", register=target, ratio=f"{ratio:.0%}"
        )
        return [
            Edit(
                id=new_edit_id(
                    ErrorClass.REGISTER_INCONSISTENCY.value,
                    sent.start,
                    min(sent.end, sent.start + 1),
                    # This edit has no `original` — it points at a whole
                    # sentence — so the minority register stands in as the
                    # content that identifies it.
                    minority_label,
                    [],
                ),
                start=sent.start,
                end=min(sent.end, sent.start + 1),
                original="",
                suggestions=[],
                error_class=ErrorClass.REGISTER_INCONSISTENCY,
                confidence=float(cfg.get("drift_confidence", 0.58)),
                stage=1,
                explanation_bn=bn,
                explanation_en=en,
                rule_reference=spec.rule_reference,
                debug={"sadhu_sentences": sadhu, "cholito_sentences": cholito},
            )
        ]

    # ------------------------------------------------------------------
    _SPACE_BEFORE_DARI = re.compile(r"[ \t]+([" + C.DARI + C.DOUBLE_DARI + r",;:?!])")
    # Every terminator and separator, not just the dari. "রহিম,আমি" is the same
    # error as "রহিম।আমি" and was going unreported because this class listed
    # only the two dandas.
    _MISSING_SPACE_AFTER = re.compile(
        r"([" + C.DARI + C.DOUBLE_DARI + r",;:?!])(?=[ঀ-৿])"
    )
    # The dari belongs here too. A doubled one is a typo in prose exactly the
    # way "??" is; Stage 0 used to fold ।। into ॥ and hide it.
    _REPEATED = re.compile(r"([,;:!?" + C.DARI + C.DOUBLE_DARI + r"])\1+")
    # Runs of spaces inside a line. Confined to spaces and tabs so it never
    # touches a newline, and anchored to require a non-space on the left so it
    # leaves indentation alone.
    _MULTI_SPACE = re.compile(r"(?<=\S)([ \t]{2,})(?=\S)")
    # A Latin period ending a Bengali sentence. Guarded so it never touches
    # numbers, abbreviations, URLs, or embedded English.
    _LATIN_PERIOD = re.compile(r"(?<=[ঀ-৿])\s*(\.)(?=\s|$)")

    def _punctuation(self, text: str) -> list[Edit]:
        out: list[Edit] = []

        for m in self._SPACE_BEFORE_DARI.finditer(text):
            out.append(
                self._span_edit(
                    ErrorClass.PUNCTUATION,
                    m.start(),
                    m.end(),
                    m.group(0),
                    [m.group(1)],
                    confidence=0.88,
                    rule_reference="যতিচিহ্নের পূর্বে ফাঁকা স্থান নয়",
                    wrong=m.group(0),
                    right=m.group(1),
                )
            )

        for m in self._MISSING_SPACE_AFTER.finditer(text):
            out.append(
                self._span_edit(
                    ErrorClass.PUNCTUATION,
                    m.start(1),
                    m.end(1),
                    m.group(1),
                    [m.group(1) + " "],
                    confidence=0.82,
                    rule_reference="দাঁড়ির পরে ফাঁকা স্থান",
                    wrong=m.group(1),
                    right=m.group(1) + " ",
                )
            )

        for m in self._REPEATED.finditer(text):
            out.append(
                self._span_edit(
                    ErrorClass.PUNCTUATION,
                    m.start(),
                    m.end(),
                    m.group(0),
                    [m.group(1)],
                    confidence=0.8,
                    wrong=m.group(0),
                    right=m.group(1),
                )
            )

        for m in self._MULTI_SPACE.finditer(text):
            out.append(
                self._span_edit(
                    ErrorClass.PUNCTUATION,
                    m.start(1),
                    m.end(1),
                    m.group(1),
                    [" "],
                    confidence=0.85,
                    rule_reference="শব্দের মাঝে একটিমাত্র ফাঁকা স্থান",
                    wrong=m.group(1),
                    right=" ",
                )
            )

        for m in self._LATIN_PERIOD.finditer(text):
            out.append(
                self._span_edit(
                    ErrorClass.PUNCTUATION,
                    m.start(1),
                    m.end(1),
                    ".",
                    [C.DARI],
                    confidence=0.79,
                    rule_reference="বাংলা বাক্যের শেষে দাঁড়ি (।)",
                    wrong=".",
                    right=C.DARI,
                )
            )
        return out

    # ------------------------------------------------------------------
    def _edit(
        self,
        klass: ErrorClass,
        tok: Token,
        suggestions: list[str],
        *,
        confidence: float,
        rule_reference: str | None = None,
        debug: dict[str, Any] | None = None,
        **fields: str,
    ) -> Edit:
        return self._span_edit(
            klass,
            tok.start,
            tok.end,
            tok.text,
            suggestions,
            confidence=confidence,
            rule_reference=rule_reference,
            debug=debug,
            **fields,
        )

    def _span_edit(
        self,
        klass: ErrorClass,
        start: int,
        end: int,
        original: str,
        suggestions: list[str],
        *,
        confidence: float,
        rule_reference: str | None = None,
        debug: dict[str, Any] | None = None,
        **fields: str,
    ) -> Edit:
        spec = self.specs[klass]
        bn, en = spec.render(**fields)
        kept = [s for s in suggestions if s]
        return Edit(
            id=new_edit_id(klass.value, start, end, original, kept),
            start=start,
            end=end,
            original=original,
            suggestions=kept,
            error_class=klass,
            confidence=max(0.0, min(1.0, confidence)),
            stage=1,
            explanation_bn=bn,
            explanation_en=en,
            rule_reference=rule_reference or spec.rule_reference,
            debug=debug or {},
        )
