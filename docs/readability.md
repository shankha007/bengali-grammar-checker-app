# Bangla-calibrated readability

Spec §6.2: *"do NOT port Flesch-Kincaid."* This documents what is computed
instead, and — more usefully — what is not yet trustworthy about it.

## Why not Flesch-Kincaid

F-K is `206.835 − 1.015·(words/sentence) − 84.6·(syllables/word)`. Both
coefficients were fitted against English reader comprehension data in 1948. Three
things break when it is pointed at Bengali:

1. **Word length measures agglutination, not difficulty.** বইগুলোকেও is one long
   word meaning "to the books, also". A child understands it. F-K reads it as
   hard.
2. **Syllable count is inflated by the inherent vowel.** Every consonant without
   a vowel sign or hasanta carries an unwritten অ. Syllable counters trained on
   Latin script routinely overcount Bengali by around 40%, and they overcount
   *unevenly* — conjunct-heavy Sanskritic words get the largest error, which is
   backwards.
3. **The real difficulty signal is missing entirely.** What makes Bengali prose
   hard is তৎসম (Sanskrit-derived) vocabulary density. It correlates weakly with
   both sentence length and syllable count, so no reweighting of F-K's two terms
   can recover it.

## The formula

Four components, per spec §6.2, each normalised to a 0–1 difficulty value and
combined by weight:

| Component | Weight | Normalisation |
|---|---|---|
| mean syllables per word | 0.30 | `(spw − 2.0) / 2.5`, clamped |
| তৎসম density | 0.35 | `density / 0.45`, clamped |
| mean dependency length | 0.20 | **not computed — see below** |
| sentence length variance | 0.15 | `variance / 90`, clamped |

```
difficulty = Σ(wᵢ · dᵢ) / Σ(wᵢ)        # over available components only
score      = (1 − difficulty) × 100     # 100 = easiest
```

The score is inverted at the end so that "higher is easier", matching what
readers expect from anything called a readability score, even though everything
upstream of that line is measuring difficulty.

### Syllable counting

`count_syllables` walks the word and counts vowel nuclei:

- an independent vowel (অ আ ই …) is one nucleus;
- a consonant followed by a vowel sign is one nucleus;
- a consonant followed by hasanta is **zero** — it is the first half of a
  conjunct and the following base carries the nucleus;
- a bare consonant is one nucleus, from the inherent vowel.

This is the rule a Latin-trained counter has no way to know.

### তৎসম density

Currently a marker heuristic: a word counts as তৎসম if it contains any of
ষ ণ ঋ ৃ ঃ ঞ ঢ়, or a conjunct from {্য ্র ্ব ক্ষ জ্ঞ}. Spot-checked precision is
roughly 0.8. It is cheap and it has no dictionary dependency, which is what makes
it usable in Phase 1.

**This is the weakest part of the formula.** It should be replaced by a
dictionary-backed origin tag (তৎসম / তদ্ভব / দেশি / বিদেশি) once the Hunspell
dictionaries land, because the same tag is needed by ণত্ব/ষত্ব detection anyway —
see `data/notva_shotva.yaml`, where the তৎসম-only scope of both বিধান is the
reason the generative rules are not run as detectors.

## What is missing, and why the number is provisional

**Mean dependency length is not computed.** It needs a dependency parse, which
arrives with the morphological analyser and POS tagger in Phase 4. Its 0.20
weight is redistributed proportionally across the other three rather than
silently treated as zero, and `BengaliReadability.components_missing` reports it
so the CLI can say so out loud.

**The normalisation anchors (2.0, 2.5, 0.45, 90) are not calibrated.** They are
plausible starting values chosen so that ordinary prose lands mid-scale. They
have not been fitted against human difficulty judgements, and until they are, the
score is useful for *relative* comparison — is this draft harder than my last
one — and not for any absolute claim such as "class 8 reading level".

Calibration is a Phase 5 task and needs: a corpus stratified by intended
audience (children's books, newspapers, academic prose, legal text), human
difficulty ratings, and a fit that reports its own confidence interval. Until
that exists, do not put a grade level on this number in the UI.
