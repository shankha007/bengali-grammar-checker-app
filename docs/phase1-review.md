# Phase 1 — review document

Spec §11 asks for three things before code, then a Phase 1 scaffold, then a stop.
This is those three things, written after the build so the claims are checkable
against what actually shipped.

---

## 1. Understanding

### The 5-stage pipeline

The load-bearing idea is that this is **not** `text → LLM → corrected text`. It is
a cascade in which each stage is independently testable and swappable, and every
stage emits `Edit` objects rather than rewritten prose. Rewritten prose is
unreviewable: the user cannot accept one change and reject another, and the eval
harness cannot score anything finer than "the whole sentence changed".

| Stage | Name | What it owns | Status |
|---|---|---|---|
| 0 | NORMALIZE | Unicode NFC + Bangla-specific repair, Bijoy detection, invisible-character cleanup, dari handling | **shipped** |
| 1 | LEXICAL | lexicon lookup with morphological suffix stripping, Damerau-Levenshtein + Bangla-Soundex candidate ranking, ণত্ব/ষত্ব violations, punctuation, register clash | **shipped** |
| 2 | DETECT | BanglaBERT token-classification head, per-token error probability + class | Phase 2 |
| 3 | CORRECT | BanglaT5, sentence-scoped, constrained to flagged spans, confidence-gated | Phase 2 |
| 4 | REASON | Sarvam-30B / Qwen3-14B behind `LLMProvider` — hard cases, teaching explanations, register rewriting | Phase 2 |

Escalation: ~85% of edits must resolve at stages 0–3. `CheckResult.stage_distribution`
is a first-class field, `make eval` prints it, and the gate warns if stage 4's
share exceeds 25%. Today it reads `stage 1: 188` and nothing else, which is
correct and unflattering: nothing has been escalated because nothing above
stage 1 exists yet.

Stages 2–4 are **absent, not stubbed**. `CheckResult.stage_reports` lists them
with `skipped_reason="not implemented until Phase 2"`. A stub that returns empty
results would let the eval harness silently credit work that did not happen.

### `LanguagePack`

```python
class LanguagePack(Protocol):
    code: str
    normalizer: Normalizer          # Stage 0, must be idempotent
    tokenizer: SentenceTokenizer    # dari (।) is not a period
    lexicon: Lexicon
    detectors: list[Detector]       # stage-tagged
    correctors: list[Corrector]
    readability: ReadabilityScorer
    error_classes: dict[ErrorClass, ErrorClassSpec]   # from YAML, never hard-coded
```

Enforcement is a CI lint, not a convention:
`scripts/lint_core_language_purity.py` fails the build if any code point in
U+0980–U+09FF appears under `src/bhashasetu/core/`. It has already caught one
real leak — a Bengali example inside a docstring in `core/distance.py` — which is
exactly the class of coupling that makes the Phase 5 Hindi pack quietly
impossible if nobody is checking.

---

## 2. Assumptions

Ordered by how much damage each one does if wrong.

**Datasets — the significant exposure.**

1. **Vaiyākaraṇa (567,422 sentences / 227,119 erroneous / 12 classes) is
   obtainable and its licence permits fine-tuning a model that is then served
   publicly.** The 12-class taxonomy in this repo is built to match it. Not
   verified. If the licence turns out to be research-only or the corpus is not
   released, Phase 2's supervised training set disappears and the fallback is
   targeted morphological corruption over IndicCorp-bn / Bangla Wikipedia —
   which changes the timeline materially, not marginally.
2. **The gold set can be human-verified.** Still the blocker; see §4.4. The set
   now holds 353 model-authored error cases and 104 clean sentences, and needs a
   Bengali-literate reviewer rather than more of me.
3. **Prothom Alo dumps are usable for the clean-text slice.** Newspaper archives
   are frequently not redistributable even when publicly readable.
4. **bn_BD can be shipped.** Now installed and in use (§4.1). The `.aff` carries
   "Copyright 2018 Jacob Thomas, Bengal Creative Media LTD" and **no explicit
   licence grant**, which is why it is gitignored rather than vendored.
   Resolving this is a prerequisite for distributing the app, not for developing
   it. bn_IN is still unfetched.

**Models.**

5. `csebuetnlp/banglabert` and `csebuetnlp/banglat5` remain available with
   permissive terms.
6. `sarvamai/sarvam-30b` exists at that identifier under Apache 2.0. Spec §2
   already flags deployment friction and mandates a head-to-head against
   Qwen3-14B — that instruction is retained verbatim and the `LLMProvider`
   abstraction is designed so the swap is one config line.
7. ONNX int8 quantisation keeps stages 2–3 CPU-viable within the latency budget.
   Plausible for a BERT-base-sized encoder, less certain for T5 generation.

**Product and environment.**

8. p95 < 800 ms for a 200-word document through stages 0–3 is achievable.
   Current stage 0–1 p95 is 582 ms on the gold set — almost entirely Hunspell's
   suggester on cold unknown words, and capped at 25 calls per request. This is
   the assumption most at risk now: the neural stages have far less headroom
   than the 12 ms measured before the dictionary landed. Caching suggestions
   across requests, or moving suggestion generation off the critical path, is
   likely needed in Phase 2.
9. Users tolerate no-login. The recovery-phrase design (§5) assumes people will
   copy 12 words when prompted; if they do not, cross-device continuity is lost
   even though nothing is broken.
10. Bengali means the Bangla Academy / West Bengal standard written register.
    Chittagonian, Sylheti, and other varieties will be flagged as errors by any
    prescriptive checker, which is a product decision worth making explicitly
    rather than by default.

**Environment note.** This machine has Python 3.13.7 and Node 22.20 but **no
Docker and no `make`**. `docker-compose.yml`, `docker/backend.Dockerfile`, and
the `Makefile` are written to spec and are unrun here; `make.ps1` mirrors the
Makefile targets so local development works. The two must be kept in sync.

---

## 3. Where I think the spec is wrong

Four items. Two are disagreements, two are scope corrections.

### 3.1 ণত্ব/ষত্ব cannot be applied as a generative rule — it needs word origin

Both বিধান apply to **তৎসম words only**. তদ্ভব, দেশি, and বিদেশি words keep ন and স.
So ভাণ্ডার (তৎসম) takes ণ, while ঠান্ডা (দেশি) correctly takes ন — despite both
matching the same "ন before ট-বর্গ" pattern.

A checker that applies the cluster rule generatively will "correct" ঠান্ডা into a
misspelling. Spec §3 lists `NOTVA_SHOTVA` as a first-class detector without
mentioning the তৎসম restriction, and that omission is a false-positive generator
aimed squarely at the metric §8 says matters most.

**What I did instead:** Phase 1 runs an explicit, hand-checked violation list
(~40 entries, each a word whose correct তৎসম spelling is not in dispute). The
generative rules are recorded in `data/notva_shotva.yaml` as documentation and as
Stage-2 feature extractors, to be applied by a model that knows word origin.
Ambiguous words are excluded with the reason written inline — ভাসা ("to float",
a real word), পুরান ("old", colloquial), ঠান্ডা (দেশি), করন, গুন. Those exclusions
are also in the clean slice, so any future change that starts flagging them fails
the eval.

Result: `NOTVA_SHOTVA` scores P 1.000 / R 0.600 / F0.5 0.882 across 50 gold
cases, with zero clean-text false positives. Recall was 1.000 when the slice held
8 cases; it fell to 0.600 as the slice grew, which is the honest shape of a
hand-curated list — perfect precision, recall bounded by its length. Closing that
gap needs the তৎসম origin tag, not more list entries.

### 3.2 Stage 1 as "LEXICAL only" wastes the cheapest stage

Spec §1 assigns Stage 1 to Hunspell + candidate ranking. But punctuation errors
and গুরুচণ্ডালী দোষ are pure pattern matching over the same token stream. Routing
them through a neural stage costs latency and buys nothing.

**What I did instead:** Stage 1 also emits `PUNCTUATION`,
`GURUCHANDALI_DOSHA`, and `REGISTER_INCONSISTENCY`. Stage 2 keeps its full remit;
it simply does not have to re-derive facts a regex already settled. This is
noted at the top of `rules.py` so it is not mistaken for drift.

Worth stating plainly: গুরুচণ্ডালী — the flagship feature — is **lexically
tractable**. The two registers differ in a closed, listable set of pronouns and
verb endings. It scores F0.5 0.952 today with no model at all.

One subtlety that took real care: করিলাম is সাধু, দিলাম is চলিত, and they end in
the same four characters. They separate only by stem length — a one-character
stem means the ি belongs to the stem, not the ending. Without that guard, every
ordinary চলিত sentence containing দিলাম / নিলাম becomes a false গুরুচণ্ডালী flag.
The guard is in `register.yaml` with the reasoning, and pinned by a test.

### 3.3 `HOMONYM` at Stage 1 is near-impossible, and the spec's own research says so

Stage 1 sees a word that is spelt correctly and is in the dictionary. It has no
basis to object. Spec §1 itself cites sub-20% LLM performance on homonym errors
and assigns detection to a fine-tuned encoder.

**What I did instead:** shipped the confusion inventory as data (training/eval
material for Phase 2) plus three collocation rules where context is
unambiguous — আশা করি vs আসা করি, দীন-দুঃখী. Across 24 gold cases that is recall
0.042 at precision 1.000: it catches the one case its rules cover and never
guesses at the rest. That is the honest ceiling for a rule at this stage, not a
bug to be tuned away.

### 3.4 Bijoy conversion belongs in Phase 4, not Stage 0

Spec §1 puts Bijoy→Unicode in Stage 0; spec §6.2 schedules the converter as a
Phase 4 tool. The Phase 4 placement is right. Bijoy is a *glyph* encoding, not a
character encoding: pre-base vowel signs are stored before their consonant in
visual order, reph after its cluster, and several conjuncts have dedicated glyph
codes with no compositional structure.

A half-complete mapping table does not produce half-correct Bengali. It produces
convincing garbage, which is worse than a clear "paste this as Unicode" message.

**What I did instead:** shipped detection (complete, tested — it keys on
high-range Windows-1252 characters that saturate Bijoy text and essentially never
appear in English) and a table-driven converter that **refuses to convert** below
95% table coverage. The table currently holds only entries verified against known
word pairs, so conversion is inert by construction. Completing it is a Phase 4
task requiring paired Bijoy/Unicode documents and a round-trip gold set.

---

## 4. Where this stands after the dictionary and gold-set work

### 4.1 The dictionary is installed

`scripts/fetch_dictionaries.py --yes` pulled bn_BD from the LibreOffice
dictionaries repository: 87,640 stems plus a substantial affix table that
expands them into millions of legal surface forms and correctly handles
বইগুলোকেও and friends. Copyright line: "2018 Jacob Thomas, Bengal Creative
Media LTD". **The licence still needs review before distribution** — the `.aff`
carries a copyright notice but no explicit licence grant, and the file is
gitignored rather than vendored for that reason.

One fix was needed on the way in: bn_BD writes six affix headers as
`SFX	L	Y	12$`. Hunspell parses the count with `atoi`, which stops at the `$`;
spylls calls `int()` and raises. The file is not wrong so much as relying on C
parsing slack, and every strict-parser toolchain will hit it, so
`sanitize_aff()` strips the trailing `$` at fetch time and reports how many lines
it touched.

### 4.2 A real bug the dictionary exposed

Installing it took the clean-text false-positive rate from 0% to **11.1%**, and
the cause was worth the trouble of finding.

`ড + ়` (U+09A1 U+09BC) and `ড়` (U+09DC) render identically in every editor,
terminal and diff, and are different strings. `_NUKTA_COMPOSE` in the normalizer
mapped the decomposed form to a replacement that was *itself* decomposed — a
no-op. Its unit test asserted equality against another decomposed literal, so it
passed. Every Bengali literal in the repo, written by the same process, was
decomposed too; the dictionary was composed. Nothing about this is visible to
code review.

Three changes, in order of how much they matter:

1. `scripts/lint_data_normalization.py` — a byte-level CI check that fails if any
   data file contains a decomposed nukta, with `normalize_data_files.py` as the
   fixer. This is the fix; the rest is cleanup.
2. `chars.py` now defines `RRA`/`RHA`/`YYA` by code point, and the normalizer
   builds its table from `NUKTA_COMPOSITIONS` rather than from literals.
3. The test was rewritten to assert on code points. Anything that can be true of
   both forms is not a test of this behaviour.

`BengaliLexicon` also composes on ingest now, so the Phase 4 custom-dictionary
feature cannot be broken by whatever keyboard a user has.

### 4.3 What moved

| | before dictionary | now |
|---|---|---|
| clean-text false positives | 0.00% (45 sentences) | **0.00%** (104 sentences) |
| macro F0.5 | 0.763 | **0.771** |
| NON_WORD F0.5 | 0.000 (suppressed) | **0.692**, recall 0.980 |
| gold error cases | 49 | **353** |
| latency p95 | 12.6 ms | 558 ms |

Latency regressed because Hunspell's suggester costs ~400 ms on a cold unknown
word. It is capped at 25 suggester calls per request: past that, edits still
surface with their explanations, just without ranked alternatives. Losing
suggestions on the 26th unknown word in one document is a much smaller harm than
a checker that stalls, and it keeps the §10 budget (p95 < 800 ms) intact.

Three lexicon changes were needed to hold the false-positive rate at zero, and
each was chosen to generalise rather than to patch the failing case:

* **Productive prefix stripping** (এ, সব, প্রতি, উপ, নি …) so compounds such as
  এদেশের and সবসময় resolve. Real morphology, closed list — a
  "split anywhere" rule would accept almost any string.
* **সাধু deferral in the spelling check.** bn_BD's সাধু coverage is patchy
  (কিনিলেন, দিয়াছে, আমাদিগের all absent), and flagging correct literary Bengali
  as misspelt is a systematic failure. If the register labeller recognises the
  form, the spelling check defers to it.
* **হওয়া's সাধু paradigm listed explicitly.** One-character stems (হ-, ল-) cannot
  be reached by the stem-length guard, so হইলেন fell through to the চলিত ending
  "লেন" and turned correct সাধু prose into a গুরুচণ্ডালী false positive.

This has a cost, and it is visible: প্রতিরোদে is now accepted (প্রতি + রোদে), so
that gold case can never be caught at Stage 1. It is kept, with a note, and
`validate-gold` reports it as a standing warning. Trading a false negative for a
false positive is the right direction under F0.5.

### 4.4 The blocker has not moved

**The gold set is model-authored. Zero cases carry human sign-off.**

353 error cases across all 12 classes and 104 clean sentences, every one written
by me. Spec §8 requires 600 *human-verified*. `review` is three-valued
(`none`/`model`/`human`) precisely so this cannot be quietly rounded up.

The clean slice is where it bites hardest. The false-positive rate is the single
most important number in the project, and it is measured against sentences this
project wrote — a checker agreeing with its own author is not evidence.
Replacing that file with a sample of real published Bengali is the highest-value
next action, and it does not need me.

`make eval` passes with a warning. `make eval-strict` blocks and exits 1.
[eval/gold/README.md](../eval/gold/README.md) carries the reviewer's checklist,
the class-boundary rules that need the most care, and an honest list of the weak
spots — HOMONYM stopped at 24 cases and WORD_ORDER at 20 because the good cases
ran out, and padding them with weak ones was tried and reverted.

Current numbers, with that caveat applying to every one:

```
false positives on clean text     0.00% (0/104)
macro F0.5 (implemented classes)  0.771
latency p50 / p95 / p99 (ms)      5.3 / 582 / 640
gold: human-verified / total      0 / 353   (need 600 human-verified)
```

Per class: `REGISTER_INCONSISTENCY` 0.982 · `PUNCTUATION` 0.974 ·
`GURUCHANDALI_DOSHA` 0.916 · `NOTVA_SHOTVA` 0.882 · `NON_WORD` 0.692 ·
`HOMONYM` 0.179. The six morphology/syntax classes report 0.000 — no detector
until Phase 2, reported rather than omitted.

`NOTVA_SHOTVA` recall fell from 1.000 to 0.600 when the slice grew from 8 cases
to 50. That is the explicit violation list meeting words it does not contain,
and it is the honest shape of a hand-curated list: perfect precision, recall
bounded by its length.

## 5. What Phase 2 should not inherit

- The তৎসম origin tag is needed by **both** ণত্ব/ষত্ব detection and the readability
  score's তৎসম-density term. Build it once, as a dictionary field, not twice as
  two heuristics.
- The normalizer's offset map is what makes Phase 3's incremental sentence-scoped
  re-check possible. Any stage that rewrites text without maintaining it will
  make editor decorations drift on the second keystroke, and that bug is
  extremely hard to diagnose from the UI.
- `docs/readability.md` records four normalisation constants that are plausible
  guesses, not calibrated values. Do not put a grade level on that score in the
  UI until they are fitted.
