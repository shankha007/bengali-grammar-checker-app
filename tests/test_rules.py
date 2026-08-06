"""Stage 1 detector tests.

Half of these assert that nothing fires. That ratio is deliberate: spec §8 makes
the false-positive rate the governing metric, so the negative cases are the ones
that protect the product.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from bhashasetu.core.pipeline import Pipeline, PipelineConfig
from bhashasetu.core.registry import get_pack
from bhashasetu.core.types import CheckResult, ErrorClass


@pytest.fixture(scope="module")
def pipeline() -> Pipeline:
    return Pipeline(get_pack("bn"))


def classes(result: CheckResult) -> set[ErrorClass]:
    return {e.error_class for e in result.edits}


@pytest.fixture(scope="module")
def norm() -> Callable[[str], str]:
    """Normalise a literal the way the pipeline normalises its input.

    Bengali য় has two encodings that look identical on screen — য + nukta, and
    the precomposed U+09DF. The pipeline composes everything it is given, and
    the data files are composed by scripts/normalize_data_files.py, so an edit's
    `original` is always composed. A test literal typed by hand may not be.

    Comparing raw literals therefore fails on exactly the words most likely to
    be interesting (যায়, নির্ণয়, হয়েছে) with a diff that renders as two
    identical strings. Every expected span goes through here instead.
    """
    pack = get_pack("bn")
    return lambda text: pack.normalizer.normalize(text).text


# --- ণত্ব / ষত্ব ------------------------------------------------------------

@pytest.mark.parametrize(
    ("text", "wrong", "right"),
    [
        ("এর কারন কী?", "কারন", "কারণ"),
        ("সে ঘন্টা খানেক অপেক্ষা করল।", "ঘন্টা", "ঘণ্টা"),
        ("বৃস্টি নামল।", "বৃস্টি", "বৃষ্টি"),
        ("মানুস সমাজবদ্ধ জীব।", "মানুস", "মানুষ"),
        # Second pass. Each of these was already being corrected, but as
        # NON_WORD — "not a word" — which drops the one thing this feature
        # exists to say: which বিধান was broken and why.
        ("এটি একটি উদাহরন মাত্র।", "উদাহরন", "উদাহরণ"),
        ("এটি একটি সাধারন ভুল।", "সাধারন", "সাধারণ"),
        ("তিনি বিশেষন ব্যবহার করেন।", "বিশেষন", "বিশেষণ"),
        ("সে প্রসংসা করেছে।", "প্রসংসা", "প্রশংসা"),
        ("কাজটি সম্পূর্ন হয়েছে।", "সম্পূর্ন", "সম্পূর্ণ"),
        ("সরকার একটি ঘোষনা দিয়েছে।", "ঘোষনা", "ঘোষণা"),
        ("তার কন্ঠ খুব মিষ্টি।", "কন্ঠ", "কণ্ঠ"),
        ("তার ভাষন সবাই শুনেছে।", "ভাষন", "ভাষণ"),
    ],
)
def test_notva_shotva_fires(
    pipeline: Pipeline, norm: Callable[[str], str], text: str, wrong: str, right: str
) -> None:
    edits = [e for e in pipeline.check(text).edits if e.error_class is ErrorClass.NOTVA_SHOTVA]
    assert len(edits) == 1
    assert edits[0].original == norm(wrong)
    assert edits[0].suggestions == [norm(right)]
    assert edits[0].explanation_bn  # never surface an edit we cannot explain
    assert edits[0].rule_reference


@pytest.mark.parametrize(
    "text",
    [
        "শীতকালে ঠান্ডা বাতাস বয়।",   # দেশি: the ট-বর্গ rule does not reach it
        "নৌকাটি জলে ভাসা শুরু করল।",  # ভাসা is a real word, not a typo for ভাষা
        "এই বাড়িটি অনেক পুরান।",       # পুরান = old, not always পুরাণ
    ],
)
def test_notva_shotva_stays_silent_on_near_misses(pipeline: Pipeline, text: str) -> None:
    assert ErrorClass.NOTVA_SHOTVA not in classes(pipeline.check(text))


# --- গুরুচণ্ডালী -------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "সে তাহার বইটা পড়ছে।",
        "আমরা করিয়াছি এবং এখন বাড়ি যাচ্ছি।",
        "ইহা আমার বই এবং ওটা তোমার।",
        # --- shapes the detector used to miss entirely.
        #
        # সাধু honorific: গিয়াছেন / করিয়াছেন end in "ছেন", so the চলিত ending
        # matched them first and the sentence read as consistent চলিত prose.
        "তিনি বাড়ি গিয়াছেন এবং এখন খাচ্ছেন।",
        "তিনি আসিয়াছেন, আমরা তাকে দেখছি।",
        # চলিত future was not a marker at all, so a সাধু verb alongside it had
        # nothing to clash with.
        "লোকটি কহিল সে যাবে।",
        "তিনি বলিলেন যে তিনি কাল আসবেন।",
        "যাহা বলিবার তাহা বলেছি।",
        # Vowel-final root: খাইতেছিলেন takes a full ই where করিতেছিলেন takes ি,
        # and used to fall through to the চলিত "ছিলেন".
        "তিনি খাইতেছিলেন যখন আমি এলাম।",
    ],
)
def test_guruchandali_fires_on_mixed_register(pipeline: Pipeline, text: str) -> None:
    assert ErrorClass.GURUCHANDALI_DOSHA in classes(pipeline.check(text))


@pytest.mark.parametrize(
    "text",
    [
        "তিনি বাজারে গিয়া দুইটি আম কিনিলেন।",       # consistent সাধু
        "আমরা বসিয়া রহিলাম এবং তাহাকে দেখিলাম।",   # consistent সাধু
        "সে তার বইটা পড়ছে।",                        # consistent চলিত
        "আমরা বসে রইলাম এবং তাকে দেখলাম।",          # consistent চলিত
        "আমি তাকে বইটি দিলাম।",                      # দিলাম is চলিত, not সাধু
        # A locative noun is not a সাধু verb. টেবিলে ends in "িলে" and বইটিতে in
        # "িতে" with stems long enough to clear the length guard, so both were
        # read as সাধু and any চলিত sentence mentioning a table was flagged.
        "বইটি টেবিলে রাখা আছে।",
        "এই বইটিতে অনেক তথ্য রয়েছে।",
        "আমাদের বাড়িতে দাদু থাকে।",
        # চলিত past continuous ends in the same letters as a সাধু past.
        "আমি তখন বলছিলে শুনিনি।",
        "আমরা কাজটা করছিলাম সারাদিন।",
        # Pure সাধু in the honorific and future columns — the forms added to fix
        # the misses above must not turn correct সাধু prose into a clash.
        "তিনি আসিয়াছিলেন এবং বসিয়াছিলেন।",
        "তিনি কহিলেন যে তিনি কাল আসিবেন।",
        "সে তাহার পুস্তক পাঠ করিতেছে।",
    ],
)
def test_guruchandali_silent_on_consistent_register(pipeline: Pipeline, text: str) -> None:
    assert ErrorClass.GURUCHANDALI_DOSHA not in classes(pipeline.check(text))


# --- পুরুষ / সম্ভ্রম agreement ------------------------------------------------
#
# Every case below names the (subject person, verb person) pair it exercises,
# because that grid — not the sentence — is what the rule implements. A table
# with a hole in it is how "আমি ভাত খাইবেন।" went unflagged: first person is not
# an unusual thing to write, it just had no row.

@pytest.mark.parametrize(
    ("text", "wrong", "right"),
    [
        # first person subject, honorific verb — the reported bug
        ("আমি ভাত খাইবেন।", "খাইবেন", "খাইব"),
        ("আমি এই কাজটি করেছেন।", "করেছেন", "করেছি"),
        ("আমরা কাল সেখানে যাবেন।", "যাবেন", "যাব"),
        # honorific subject, familiar verb
        ("আপনি কোথায় যাচ্ছ?", "যাচ্ছ", "যাচ্ছেন"),
        ("তিনি গতকাল বাড়ি গেল।", "গেল", "গেলেন"),
        ("তিনি সকালে অফিসে যায়।", "যায়", "যান"),
        # familiar subject, honorific verb
        ("সে গতকাল বাড়ি গেলেন।", "গেলেন", "গেল"),
        ("তুমি কোথায় যাচ্ছেন?", "যাচ্ছেন", "যাচ্ছ"),
        # intimate subject
        ("তুই কোথায় যাচ্ছেন?", "যাচ্ছেন", "যাচ্ছিস"),
        ("তুই কাল আসবেন তো?", "আসবেন", "আসবি"),
        # noun subject carrying a classifier
        ("ছেলেটি মাঠে খেলছেন।", "খেলছেন", "খেলছে"),
        # সাধু stays সাধু: fixing the পুরুষ error must not also modernise the
        # prose. Two edits, one asked for.
        ("তিনি ভাত খাইব।", "খাইব", "খাইবেন"),
    ],
)
def test_verb_person_agreement(
    pipeline: Pipeline, norm: Callable[[str], str], text: str, wrong: str, right: str
) -> None:
    edits = [
        e
        for e in pipeline.check(text).edits
        if e.error_class in (ErrorClass.VERB_INFLECTION, ErrorClass.AGREEMENT)
    ]
    assert len(edits) == 1, f"expected exactly one flag, got {[e.original for e in edits]}"
    assert edits[0].original == norm(wrong)
    assert edits[0].suggestions == [norm(right)]


@pytest.mark.parametrize(
    "text",
    [
        # Agreeing sentences, one per person.
        "আমি ভাত খাইব।",
        "আমি ভাত খাব।",
        "আমরা কাজটি শেষ করেছি।",
        "তুমি কোথায় যাচ্ছ?",
        "তুই কাল আসবি তো?",
        "আপনি কোথায় যাচ্ছেন?",
        "সে গতকাল বাড়ি গেল।",
        "তিনি গতকাল বাড়ি গেলেন।",
        # A participle is not the clause's finite verb. করে/ফিরে/ধরে all end in
        # ে, which is also the third-person present.
        "আমি কাজ করে এসেছি।",
        "আমি সন্ধ্যায় বাড়ি ফিরে এলাম।",
        "আপনি দয়া করে এখানে বসুন।",
        # Two subjects means two clauses; the rule must not read one against the
        # other.
        "আমি বললাম, তিনি আসবেন।",
        "আমি জানি যে তুমি আসবে।",
        # Words that merely look conjugated. ট্রেন ends in েন, গাছ in ছ,
        # নিলাম is a noun, and বৃষ্টি/সৃষ্টি end in টি without being ছেলে+টি.
        "আমি ট্রেন ধরব।",
        "সে গাছ কেটেছে।",
        "সে বাজার থেকে ফল নিলাম বলে জানাল।",
        "বৃষ্টি নামলে মাটির গন্ধ ভালো লাগে।",
        "ঈশ্বর এই জগৎ সৃষ্টি করেছেন।",
        "সে গান গাইতে খুব ভালোবাসে।",
        # A noun subject licenses the animacy judgement only. Here বইটি is the
        # object and the subject is an unwritten আমি.
        "বইটি পড়ে শেষ করেছি।",
        # ও is the conjunction "and" far more often than the pronoun "he", and
        # reading it as a third-person-familiar subject made every coordinated
        # subject with an honorific verb — which is most formal Bengali — come
        # back as a পুরুষ error. See ambiguous_subjects in verb_person.yaml.
        "রাম ও শ্যাম বাজারে গেলেন।",
        "মা ও বাবা আজ বাড়ি ফিরবেন।",
        "শিক্ষক ও ছাত্ররা সভায় উপস্থিত ছিলেন।",
        # এ is the demonstrative determiner here, not a bare pronoun.
        "এ কথা সবাই জানেন।",
        "এ বিষয়ে তিনি কিছু বলেননি।",
        # A comma ends a clause as firmly as a conjunction does. Without that,
        # তিনি was carried across into a clause whose subject is সবাই.
        "তিনি খুব ভালো মানুষ, সবাই জানে।",
        "আমি বাড়ি গেলাম, সে অফিসে গেল।",
        # দিন is the noun "day" far more often than দি + ন, the honorific
        # imperative — the same trap as নিলাম, and commoner. See not_verbs.
        "আমি সেখানে তিন দিন ছিলাম।",
        "ছেলেটি অনেক দিন পরে এল।",
        "আমি তিন দিন ধরে অসুস্থ।",
    ],
)
def test_verb_person_silent_on_correct_sentences(pipeline: Pipeline, text: str) -> None:
    found = classes(pipeline.check(text))
    assert ErrorClass.VERB_INFLECTION not in found
    assert ErrorClass.AGREEMENT not in found


# --- classifier and number ---------------------------------------------------

@pytest.mark.parametrize(
    ("text", "wrong", "right", "klass"),
    [
        # double plural: the quantifier already means "many"
        ("সব ছাত্ররা মাঠে খেলছে।", "ছাত্ররা", "ছাত্র", ErrorClass.CLASSIFIER),
        ("অনেক ছাত্ররা পরীক্ষায় অংশ নিয়েছে।", "ছাত্ররা", "ছাত্র", ErrorClass.CLASSIFIER),
        ("সব বইগুলো টেবিলে রাখা আছে।", "বইগুলো", "বই", ErrorClass.CLASSIFIER),
        # animacy: টি counts things, জন counts people
        ("সে একটি বিদুষী নারী।", "একটি", "একজন", ErrorClass.CLASSIFIER),
        ("দুটি ছাত্র ক্লাসে এসেছে।", "দুটি", "দুজন", ErrorClass.CLASSIFIER),
        ("রাস্তায় দুটি লোক দাঁড়িয়ে আছে।", "দুটি", "দুজন", ErrorClass.CLASSIFIER),
        ("তিনজন বই টেবিলের উপর রাখা আছে।", "তিনজন", "তিনটি", ErrorClass.CLASSIFIER),
        ("আমি দুজন কলম কিনেছি।", "দুজন", "দুটি", ErrorClass.CLASSIFIER),
        # -রা is the animate plural; things take -গুলো
        ("বইরা টেবিলে রাখা আছে।", "বইরা", "বইগুলো", ErrorClass.AGREEMENT),
        ("গাছরা বাতাসে দুলছে।", "গাছরা", "গাছগুলো", ErrorClass.AGREEMENT),
        # possessive must match a plural subject, same person only
        ("আমরা আমার কাজ শেষ করেছি।", "আমার", "আমাদের", ErrorClass.AGREEMENT),
        ("তারা তার দায়িত্ব পালন করেনি।", "তার", "তাদের", ErrorClass.AGREEMENT),
    ],
)
def test_classifier_and_number_agreement(
    pipeline: Pipeline,
    norm: Callable[[str], str],
    text: str,
    wrong: str,
    right: str,
    klass: ErrorClass,
) -> None:
    edits = [e for e in pipeline.check(text).edits if e.error_class is klass]
    assert [e.original for e in edits] == [norm(wrong)]
    assert edits[0].suggestions == [norm(right)]


@pytest.mark.parametrize(
    "text",
    [
        # Both repairs of the double plural are correct Bengali on their own.
        "সব ছাত্র মাঠে খেলছে।",
        "ছাত্ররা মাঠে খেলছে।",
        "তিনি একজন বিদুষী নারী।",
        "আমি তিনটি বই কিনেছি।",
        "সভায় তিনজন শিক্ষক উপস্থিত ছিলেন।",
        # A different person's possessive is not a disagreement.
        "আমরা তোমার বই এনেছি।",
        "তারা আমার কথা শুনেছে।",
        # -দের is genitive as well as plural, so it must survive intact.
        "সব ছাত্রদের বই এসেছে।",
        # The head noun here is কলেজ, a thing, so একটি is right.
        "এটি একটি মেয়েদের কলেজ।",
    ],
)
def test_classifier_silent_on_correct_sentences(pipeline: Pipeline, text: str) -> None:
    found = classes(pipeline.check(text))
    assert ErrorClass.CLASSIFIER not in found
    assert ErrorClass.AGREEMENT not in found


# --- প্রমিত লেখ্য রূপ ---------------------------------------------------------

@pytest.mark.parametrize(
    ("text", "wrong", "right"),
    [
        ("আমি কালকে বাজারে যাবো না।", "কালকে", "কাল"),
        ("আমি কালকে বাজারে যাবো না।", "যাবো", "যাব"),
        ("আজকে আমি অফিসে যাব না।", "আজকে", "আজ"),
        ("আমি কাজটা করবো।", "করবো", "করব"),
    ],
)
def test_standard_written_forms(
    pipeline: Pipeline, norm: Callable[[str], str], text: str, wrong: str, right: str
) -> None:
    edits = [e for e in pipeline.check(text).edits if e.original == norm(wrong)]
    assert edits, f"{wrong} was not flagged"
    assert edits[0].suggestions == [norm(right)]
    # The explanation must not claim the word is missing from the lexicon —
    # both of these are in it. See data/standard_forms.yaml.
    assert "প্রমিত" in edits[0].explanation_bn
    assert edits[0].rule_reference


def test_standard_forms_leave_the_standard_spelling_alone(pipeline: Pipeline) -> None:
    assert not pipeline.check("আমি কাল বাজারে যাব না।").edits


# --- পড়া / পরা, and the dictionary itself -----------------------------------

@pytest.mark.parametrize(
    ("text", "wrong", "right"),
    [
        # পড়া = to read/fall, পরা = to wear. Decidable only from what is worn.
        ("সে শাড়ি পড়ে অনুষ্ঠানে গেল।", "পড়ে", "পরে"),
        ("মেয়েটি নতুন জামা পড়ে স্কুলে এসেছে।", "পড়ে", "পরে"),
        # শারি is a real word (a row, a myna), so this needs the bigram too.
        ("আমি শারি পরে বিদ্যালয়ে যাব।", "শারি", "শাড়ি"),
    ],
)
def test_wearing_versus_reading(
    pipeline: Pipeline, norm: Callable[[str], str], text: str, wrong: str, right: str
) -> None:
    edits = [e for e in pipeline.check(text).edits if e.original == norm(wrong)]
    assert edits, f"{wrong} was not flagged in {text!r}"
    assert edits[0].suggestions[:1] == [norm(right)]


@pytest.mark.parametrize(
    "text",
    [
        "সে বই পড়ে ঘুমিয়ে পড়ল।",   # reading a book, and falling asleep
        "আমি প্রতিদিন খবরের কাগজ পড়ি।",
        "ছেলেটি সিঁড়ি থেকে পড়ে গেছে।",
    ],
)
def test_reading_and_falling_are_left_alone(pipeline: Pipeline, text: str) -> None:
    assert ErrorClass.HOMONYM not in classes(pipeline.check(text))


def test_the_whole_reported_sentence(pipeline: Pipeline, norm: Callable[[str], str]) -> None:
    """আমি শারি পড়ে বিদ্যালয়ে যাইব → আমি শাড়ি পরে বিদ্যালয়ে যাব।

    Three unrelated errors in seven words, which is why it is here as one test:
    each rule has to fire in the presence of the other two. The checker used to
    return this sentence completely clean.
    """
    edits = pipeline.check("আমি শারি পড়ে বিদ্যালয়ে যাইব").edits
    found = {e.original: e.suggestions[0] for e in edits if e.suggestions}
    assert found.get(norm("শারি")) == norm("শাড়ি")
    assert found.get(norm("পড়ে")) == norm("পরে")
    assert found.get(norm("যাইব")) == norm("যাব")


def test_corrected_sentence_is_clean(pipeline: Pipeline) -> None:
    assert not pipeline.check("আমি শাড়ি পরে বিদ্যালয়ে যাব।").edits


@pytest.mark.parametrize(
    "word",
    [
        # শাড়ি was absent while শারি was present, so the checker preferred the
        # wrong spelling. Ordinary চলিত futures were missing too: "আমি বই পড়ব।"
        # was flagged NON_WORD and offered ওড়ব.
        "শাড়ি",
        "ওড়না",
        "পড়ব",
        "রাখব",
        "উঠব",
        "পরব",
        "পরেছি",
    ],
)
def test_lexicon_knows_ordinary_words(norm: Callable[[str], str], word: str) -> None:
    """A dictionary gap is not a quiet loss of recall — it makes the checker
    correct correct writing, which is the worst thing it can do."""
    assert get_pack("bn").lexicon.contains(norm(word))


def test_dilam_is_not_mislabelled_sadhu() -> None:
    """The stem-length guard. করিলাম is সাধু, দিলাম is চলিত, and they end in the
    same four characters - see register.yaml.

    Inputs go through the normalizer first, because that is what the pipeline
    does and because a literal typed here may carry a decomposed nukta that the
    composed data tables will never match.
    """
    from bhashasetu.language_packs.bn.rules import BengaliRuleDetector

    pack = get_pack("bn")
    det = pack.detectors[0]
    assert isinstance(det, BengaliRuleDetector)

    def label(word: str) -> str | None:
        return det._register.label(pack.normalizer.normalize(word).text)

    assert label("করিলাম") == "sadhu"
    assert label("দিলাম") == "cholito"
    assert label("কিনিলেন") == "sadhu"
    assert label("কিনলেন") == "cholito"
    assert label("করিয়া") == "sadhu"
    assert label("হইলেন") == "sadhu"
    assert label("বই") is None


def test_register_labels_the_columns_the_detector_used_to_get_wrong() -> None:
    """One assertion per bug class, at the labeller rather than the pipeline.

    A mislabel is upstream of everything: it silences real clashes AND invents
    false ones, and which of the two you notice is an accident of the sentence.
    """
    from bhashasetu.language_packs.bn.rules import BengaliRuleDetector

    pack = get_pack("bn")
    det = pack.detectors[0]
    assert isinstance(det, BengaliRuleDetector)

    def label(word: str) -> str | None:
        return det._register.label(pack.normalizer.normalize(word).text)

    # সাধু honorific. These end in "ছেন" and were being claimed by চলিত.
    assert label("গিয়াছেন") == "sadhu"
    assert label("করিয়াছেন") == "sadhu"
    assert label("আসিয়াছিলেন") == "sadhu"
    assert label("করিতেছিলেন") == "sadhu"
    # Vowel-final roots take a full ই, not a ি-কার.
    assert label("খাইতেছিলেন") == "sadhu"
    assert label("যাইতেছেন") == "sadhu"
    # সাধু future, and its চলিত counterpart — neither was a marker before.
    assert label("করিবেন") == "sadhu"
    assert label("আসিবে") == "sadhu"
    assert label("করবেন") == "cholito"
    assert label("যাবে") == "cholito"
    # চলিত past continuous, which passes the সাধু stem-length guard.
    assert label("বলছিলে") == "cholito"
    assert label("করছিলাম") == "cholito"
    # Locative nouns. Verb morphology on a noun is not register evidence.
    assert label("টেবিলে") is None
    assert label("বইটিতে") is None
    assert label("বাড়িতে") is None
    # An unlisted verb root goes unmarked rather than falling through to চলিত:
    # silence is a miss, and a wrong label is a false positive.
    assert label("জিতিলেন") is None


# --- punctuation ------------------------------------------------------------

def test_space_before_dari(pipeline: Pipeline) -> None:
    edits = [e for e in pipeline.check("আমি বাড়ি যাচ্ছি ।").edits
             if e.error_class is ErrorClass.PUNCTUATION]
    assert edits and edits[0].suggestions == ["।"]


def test_latin_period_after_bengali(pipeline: Pipeline) -> None:
    edits = [e for e in pipeline.check("সে এসেছে.").edits
             if e.error_class is ErrorClass.PUNCTUATION]
    assert edits and edits[0].suggestions == ["।"]


@pytest.mark.parametrize(
    "text",
    [
        "তিনি ২০২৪ সালে Ph.D. সম্পন্ন করেছেন।",
        "আমাদের ওয়েবসাইট www.example.com দেখুন।",
        "বইটির দাম ৳৩৫০ টাকা।",
    ],
)
def test_period_rule_does_not_touch_abbreviations_or_urls(
    pipeline: Pipeline, text: str
) -> None:
    assert ErrorClass.PUNCTUATION not in classes(pipeline.check(text))


@pytest.mark.parametrize(
    ("text", "wrong", "right"),
    [
        # A doubled dari. Stage 0 used to fold this into ॥ before the rule ran,
        # so the commonest punctuation typo there is produced no flag at all.
        ("আমি স্কুলে যাই।।", "।।", "।"),
        # A separator needs a space after it, not just a dari. This class listed
        # only the two dandas, so "রহিম,আমি" went unreported.
        ("আমার নাম রহিম,আমি ছাত্র।", ",", ", "),
        ("তুমি কি আসবে?আমি জানি না।", "?", "? "),
        # Runs of spaces between words.
        ("সে   অনেক ভালো ছেলে।", "   ", " "),
    ],
)
def test_punctuation_catches(
    pipeline: Pipeline, text: str, wrong: str, right: str
) -> None:
    edits = [
        e
        for e in pipeline.check(text).edits
        if e.error_class is ErrorClass.PUNCTUATION and e.original == wrong
    ]
    assert edits, f"nothing flagged {wrong!r} in {text!r}"
    assert edits[0].suggestions == [right]


@pytest.mark.parametrize(
    "text",
    [
        # A newline is not a stray space before the dari: deleting it would
        # merge two paragraphs, so the space rules are confined to spaces/tabs.
        "প্রথম লাইন\n।",
        "প্রথম অনুচ্ছেদ।\n\nদ্বিতীয় অনুচ্ছেদ।",
        # Indentation is not a run of spaces between two words.
        "    আমি বাড়ি যাব।",
        # A single space after every separator is what correct text looks like.
        "আমার নাম রহিম, আমি ছাত্র।",
    ],
)
def test_punctuation_silent_on_correct_spacing(pipeline: Pipeline, text: str) -> None:
    assert ErrorClass.PUNCTUATION not in classes(pipeline.check(text))


# --- non-word damping -------------------------------------------------------

def _pack_with_lexicon(size: int) -> object:
    """A pack whose lexicon holds exactly `size` surface forms."""
    from bhashasetu.language_packs.bn import BengaliPack
    from bhashasetu.language_packs.bn.lexicon import BengaliLexicon

    real = ["আমি", "বাংলা", "ভাষায়", "কথা", "বলি"]
    padding = [f"শব্দ{i}" for i in range(max(0, size - len(real)))]
    return BengaliPack(lexicon=BengaliLexicon([*real, *padding], ["ে", "য়"]))


def test_non_word_confidence_is_damped_by_a_thin_lexicon() -> None:
    """A dictionary too small to justify an opinion must not produce one.

    This is the guard against the failure mode where a thin dictionary turns the
    product into a machine that underlines correct Bengali. The detection still
    happens - it just lands in `suppressed` instead of in front of a user.
    """
    from bhashasetu.language_packs.bn import BengaliPack

    pack = _pack_with_lexicon(500)
    assert isinstance(pack, BengaliPack)
    result = Pipeline(pack).check("আমি বাংলা ভাসায় কথা বলি।")

    assert ErrorClass.NON_WORD not in classes(result)
    suppressed = [e for e in result.suppressed if e.error_class is ErrorClass.NON_WORD]
    assert suppressed, "the detection should still exist, just below the gate"
    assert suppressed[0].confidence < 0.1


def test_non_word_surfaces_with_a_large_lexicon() -> None:
    """Same input, dictionary large enough to be trusted -> the flag surfaces."""
    from bhashasetu.language_packs.bn import BengaliPack
    from bhashasetu.language_packs.bn.lexicon import CONFIDENT_LEXICON_SIZE

    pack = _pack_with_lexicon(CONFIDENT_LEXICON_SIZE)
    assert isinstance(pack, BengaliPack)
    result = Pipeline(pack).check("আমি বাংলা ভাসায় কথা বলি।")
    assert ErrorClass.NON_WORD in classes(result)


def test_hunspell_lexicon_is_trusted_without_damping() -> None:
    """A real Hunspell dictionary sets coverage_factor to 1.0.

    Its stem count understates it badly - the affix table expands ~88k stems into
    millions of legal forms - so scaling confidence by stem count would hold
    NON_WORD below the gate forever on a dictionary that is in fact reliable.
    """
    from bhashasetu.language_packs.bn.lexicon import HunspellLexicon

    lexicon = get_pack("bn").lexicon
    if not isinstance(lexicon, HunspellLexicon):
        pytest.skip("bn_BD dictionary not installed; run `make fetch-dicts`")
    assert lexicon.coverage_factor == 1.0


# --- pipeline plumbing ------------------------------------------------------

def test_stages_2_to_4_report_as_skipped_not_silent(pipeline: Pipeline) -> None:
    reports = {r.stage: r for r in pipeline.check("আমি বাড়ি যাচ্ছি।").stage_reports}
    for stage in (2, 3, 4):
        assert reports[stage].skipped_reason is not None


def test_overlapping_edits_deduplicated() -> None:
    pipe = Pipeline(get_pack("bn"), PipelineConfig(min_confidence=0.0))
    result = pipe.check("এর কারন কী?")
    spans = [(e.start, e.end) for e in result.edits]
    for i, a in enumerate(spans):
        for b in spans[i + 1 :]:
            assert not (a[0] < b[1] and b[0] < a[1]), "overlapping edits surfaced"


def test_edits_are_serialisable(pipeline: Pipeline) -> None:
    import json

    payload = pipeline.check("এর কারন কী?").to_json()
    json.dumps(payload, ensure_ascii=False)
    assert payload["edits"][0]["errorClass"] == "NOTVA_SHOTVA"
    assert "explanation_bn" in payload["edits"][0]


def test_no_explanation_leaks_an_unsubstituted_placeholder() -> None:
    """Every `{token}` in an explanation template must get filled.

    Spec §10: "Every correction the app makes must be explainable. If the system
    cannot say *why* in Bengali, it must not surface the edit." An explanation
    reading "- {rule} অনুসারে।" is not an explanation, and it is exactly the kind
    of defect that ships: it renders fine, and only looks wrong to someone who
    reads Bengali.

    Sampled at three cases per class rather than over the whole gold set. Every
    class has its own template, so three exercises each one, and the full sweep
    costs 90 s — almost all of it Hunspell suggesting corrections for the
    deliberate misspellings, which tells us nothing about templates.
    """
    import re
    from collections import defaultdict

    from bhashasetu.eval.harness import load_gold

    pipeline = Pipeline(get_pack("bn"))
    cases, clean = load_gold("bn")

    per_class: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        key = case.error_class.value if case.error_class else "none"
        if len(per_class[key]) < 3:
            per_class[key].append(case.text)

    corpus = [t for texts in per_class.values() for t in texts] + list(clean)[:20]
    placeholder = re.compile(r"\{[a-z_]+\}")

    offenders: list[str] = []
    for text in corpus:
        for edit in pipeline.check(text).edits:
            for label, explanation in (
                ("bn", edit.explanation_bn),
                ("en", edit.explanation_en),
            ):
                if placeholder.search(explanation):
                    offenders.append(
                        f"{edit.error_class.value}/{label}: {explanation!r}"
                    )
    assert not offenders, "unsubstituted placeholders: " + "; ".join(
        sorted(set(offenders))[:5]
    )


def test_no_explanation_quotes_an_empty_suggestion() -> None:
    """A filled template can still be broken.

    `চলিত রীতিতে “” লিখুন।` passes the placeholder check above — `{right}` was
    substituted, with the empty string — and reads to a user as a bug in the
    product. A detector is allowed to have no suggestion; it has to say so in
    words instead of quoting nothing. See ErrorClassSpec.render and the
    explanation_*_no_fix templates in error_classes.yaml.

    Swept over the whole gold set including the clean slice, and over words the
    suggester cannot help with, because the failure appears only when an edit
    happens to have no suggestion — which is rare, and never where you look.
    """
    from bhashasetu.eval.harness import load_gold

    pipeline = Pipeline(get_pack("bn"))
    cases, clean = load_gold("bn")
    corpus = [c.text for c in cases] + list(clean)
    # Unpronounceable strings: the suggester returns nothing, forcing the
    # no-fix path that this test exists to cover.
    corpus += ["তিনি জ়্ক়প় নামে পরিচিত।", "ক্ষ্ম্যৎ শব্দটি লিখলাম।"]

    offenders: list[str] = []
    for text in corpus:
        result = pipeline.check(text)
        for edit in result.edits + result.suppressed:
            for label, explanation in (
                ("bn", edit.explanation_bn),
                ("en", edit.explanation_en),
            ):
                if "“”" in explanation or '""' in explanation:
                    offenders.append(
                        f"{edit.error_class.value}/{label}: {explanation!r}"
                    )
    assert not offenders, "explanations quoting nothing: " + "; ".join(
        sorted(set(offenders))[:5]
    )


def test_sadhu_forms_outside_the_pairs_table_still_get_a_correction() -> None:
    """বসিয়া → বসে without anyone listing বসিয়া.

    The endings are productive and `pairs` is a fixed list, so most সাধু forms
    the detector caught had no correction to offer. The regular derivation
    covers the ি-কার paradigms; `pairs` still wins where it has an entry,
    because the regular rule is wrong for exactly those verbs.
    """
    from bhashasetu.language_packs.bn.rules import BengaliRuleDetector

    pack = get_pack("bn")
    detector = pack.detectors[0]
    assert isinstance(detector, BengaliRuleDetector)

    def cholito(word: str) -> str | None:
        return detector._register.to_cholito(pack.normalizer.normalize(word).text)

    def norm(word: str) -> str:
        return pack.normalizer.normalize(word).text

    # Derived, not listed.
    assert cholito("বসিয়া") == norm("বসে")
    assert cholito("উঠিয়া") == norm("উঠে")
    assert cholito("ফিরিয়াছেন") == norm("ফিরেছেন")
    assert cholito("খুঁজিতেছিলাম") == norm("খুঁজছিলাম")
    # Listed, because the regular rule would be wrong: হ-final stems take -য়ে.
    assert cholito("চাহিয়া") == norm("চেয়ে")
    assert cholito("করিয়া") == norm("করে")
    # Derived from the LONGEST সাধু ending. খাইতেছিলেন also ends in িলেন, and
    # swapping that one produced খাইতেছলেন — a word in no register at all.
    assert cholito("খাইতেছিলেন") != norm("খাইতেছলেন")
    # Not derivable, and honest about it rather than inventive.
    assert cholito("বই") is None


# --- out-of-scope detection -------------------------------------------------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("আমি Python দিয়ে কাজ করি।", ["Python"]),
        ("আমি Python ও Java শিখছি।", ["Python", "Java"]),
        ("আমি the quick brown fox পড়েছি।", ["the quick brown fox"]),
        # Bridged across punctuation so an abbreviation is not split in half.
        ("তিনি ২০২৪ সালে Ph.D. সম্পন্ন করেছেন।", ["Ph.D"]),
        ("আমাদের ওয়েবসাইট www.example.com দেখুন।", ["www.example.com"]),
    ],
)
def test_foreign_runs_are_reported(text: str, expected: list[str]) -> None:
    pack = get_pack("bn")
    assert [s.text for s in pack.out_of_scope(text)] == expected


@pytest.mark.parametrize(
    "text",
    [
        "সম্পূর্ণ বাংলা বাক্য এখানে আছে।",
        "বইটির দাম ৳৩৫০ টাকা।",          # digits and currency are script-neutral
        "সভাটি সকাল ১০.৩০ মিনিটে শুরু হবে।",
        "তিনি ২০২৪ সালে জন্মেছেন।",
    ],
)
def test_pure_bengali_and_numerals_are_never_out_of_scope(text: str) -> None:
    assert get_pack("bn").out_of_scope(text) == []


def test_out_of_scope_is_not_an_error(pipeline: Pipeline) -> None:
    """Foreign text must produce no Edit of any class.

    This is the invariant that keeps the eval honest: if English words became
    errors, every mixed-script document would count against precision, and the
    number spec §8 calls the most important in the project would be measuring
    the wrong thing.
    """
    result = pipeline.check("আমি Python দিয়ে কাজ করি।")
    assert result.edits == []
    assert [s.text for s in get_pack("bn").out_of_scope(result.original)] == ["Python"]


def test_out_of_scope_spans_slice_the_original_text() -> None:
    pack = get_pack("bn")
    text = "আমি the quick brown fox পড়েছি এবং Python লিখেছি।"
    for span in pack.out_of_scope(text):
        assert text[span.start : span.end] == span.text
