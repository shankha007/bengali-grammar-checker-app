# ভাষাসেতু · BhashaSetu

A Bengali grammar and writing assistant that explains itself. Every correction
arrives with an explanation in Bengali and the grammar rule behind it — and if
the system cannot say *why*, it does not surface the edit at all.

No login, no email, no signup. Every feature free. Your text is never stored.

Architecturally it is a **language-pluggable** checker: Bengali is the first
language pack, not the only one, and nothing Bengali-specific lives outside
`language_packs/bn/` — a CI lint fails the build if it does.

---

## Contents

- [Quick start](#quick-start)
- [Deploying](#deploying)
- [Commands](#commands)
- [A user's first five minutes](#a-users-first-five-minutes)
- [What it can do, with examples](#what-it-can-do-with-examples)
- [Where it stands](#where-it-stands)
- [Roadmap by phase](#roadmap-by-phase)
- [Architecture](#architecture)
- [Design decisions worth knowing](#design-decisions-worth-knowing)
- [Repository layout](#repository-layout)
- [Licence](#licence)

---

## Quick start

**Prerequisites:** Python ≥ 3.12 and Node ≥ 20. Docker is optional — nothing in
the current build requires it.

### 1. Install

```bash
pip install -e ".[dev,api,hunspell]"
```

```bash
cd frontend && npm install
```

### 2. Install the Bengali dictionary

```bash
python scripts/fetch_dictionaries.py --yes
```

Pulls bn_BD (~88k stems plus a full affix table) from the LibreOffice
dictionaries repository. It refuses to run without `--yes` and prints its sources
first, because the file carries a third-party copyright — see
[Licence](#licence).

Without it the pack falls back to a 580-word seed list and damps unknown-word
confidence below the display threshold, so spelling errors are detected but not
shown. Everything else works.

### 3. Run it

Two processes, two shells:

```bash
make api
```

```bash
make web
```

Then open **http://localhost:3000**.

On Windows without `make`, `.\make.ps1 <target>` mirrors every target one for
one — `.\make.ps1 api`, `.\make.ps1 web`, `.\make.ps1 check`.

### Or use it from the terminal

No servers needed:

```bash
python -m bhashasetu.cli check "এর কারন কী কেউ জানে না।"
```

```
┏━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━┳━━━┓
┃ Span ┃ Orig  ┃ Suggestions ┃ Class        ┃ Conf ┃ S ┃
┡━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━╇━━━┩
│ 3-7  │ কারন  │ কারণ        │ NOTVA_SHOTVA │ 0.93 │ 1 │
└──────┴───────┴─────────────┴──────────────┴──────┴───┘
```

---

## Deploying

One container: the frontend is exported to static HTML at build time and served
by the FastAPI process, so a host only has to run one thing on one port.

```bash
docker build -t bhashasetu .
docker run -p 8000:8000 -e PORT=8000 bhashasetu
```

[`render.yaml`](render.yaml) defines a free Render service pointing at the same
Dockerfile. Step-by-step instructions, the environment variables, and what the
free tier's sleep behaviour means for a shared link are in
**[DEPLOY.md](DEPLOY.md)**.

Local development is unaffected — `make api` + `make web` still run the two
servers separately, and the static export only happens when the Docker build
sets `BHASHASETU_STATIC_EXPORT=1`.

---

## Commands

### Running the app

| Command | What it does |
|---|---|
| `make api` | FastAPI backend on `:8000`, with `--reload` |
| `make web` | Next.js UI on `:3000` (proxies `/api/*` to the backend) |
| `make web-install` | `npm install` in `frontend/` |

The proxy is not cosmetic: it keeps the browser on one origin so the anonymous
device cookie stays first-party. Cross-origin it would be silently dropped.

### CLI

| Command | What it does |
|---|---|
| `bhashasetu check "<text>"` | Check text, a file path, or `-` for stdin |
| `bhashasetu check --json FILE` | Same, as JSON |
| `bhashasetu check --show-suppressed` | Also show edits below the confidence gate |
| `bhashasetu check --min-confidence 0.8` | Raise the surface threshold |
| `bhashasetu classes` | The 12 error classes and which stage implements each |
| `bhashasetu readability "<text>"` | Readability breakdown |
| `bhashasetu languages` | Registered language packs |
| `bhashasetu identity new` | Mint a device id and recovery phrase |
| `bhashasetu eval` | Run the evaluation harness |

Installed as `bhashasetu`; without installing, use
`python -m bhashasetu.cli …` with `PYTHONPATH=src`.

### Quality gates

| Command | What it does |
|---|---|
| `make check` | Everything CI runs — lint, typecheck, tests, gold validation, eval |
| `make test` | pytest |
| `make typecheck` | mypy, strict |
| `make lint` | ruff + core language purity + data normalization |
| `make eval` | Per-class P/R/F0.5, clean-text false-positive rate, regression gate |
| `make eval-strict` | Additionally enforces the 600-sentence gold-set requirement |
| `make eval-baseline` | Commit current numbers as the regression baseline |
| `make validate-gold` | Structural checks on the gold set |
| `make web-check` | Frontend typecheck |
| `make screenshot` | Capture page screenshots (needs both servers up) |
| `make e2e` | Type Bengali into the real editor and assert on the flags (needs both servers up) |
| `make samples` | Regenerate the Sample button's corpus from the gold set |
| `make samples-check` | Fail if that corpus has drifted (part of `make check`) |

`make e2e` is the only check that crosses the browser boundary. `make test`
proves the detector is right and `make eval` scores it against the gold set, but
both call Python directly; neither notices a fix that never reaches the screen.

### Data maintenance

| Command | What it does |
|---|---|
| `make fetch-dicts` | Download the Hunspell dictionaries |
| `make normalize-data` | Rewrite Bengali data files into canonical composed form |
| `make seed` | Create a local SQLite database with one anonymous device |

---

## A user's first five minutes

1. **Open the app.** You land on the home page. No account, no dialog, nothing
   to dismiss. Click **লেখা শুরু করুন / Start writing**.

2. **Type or paste Bengali** into the editor on the left. Checking is automatic,
   600 ms after you stop typing. Nothing is kept — the text is discarded once the
   response is sent.

3. **Read the underlines.** Errors get a wavy underline coloured by category
   (spelling, morphology, syntax, register, punctuation). Text in another script
   gets a **flat yellow highlight** instead — that means "not Bengali, so the
   engine did not read it", which is deliberately *not* the same signal as
   "wrong".

4. **Scan the table** in the middle column. One row per issue: the word, the
   suggested fix, the class, and a confidence score. It stays dense on purpose,
   so you can see the shape of the whole document at once.

5. **Click a row** to see why. The pane underneath gives the explanation in
   Bengali, the English gloss, and the grammar rule cited by name — e.g.
   `ণত্ব-বিধান §2`.

6. **Accept or ignore.** `✓` applies the fix, `✕` dismisses it. **Accept all N**
   applies every suggestion of the same class at once. `Ctrl+Z` reverses any of
   it — corrections go through the normal edit history, like typing.

7. **Adjust the workspace.** Drag any of the three dividers to resize panes
   (arrow keys work too, `Home` resets). Pick one of five themes. Switch the
   interface between বাংলা and English. All of it persists.

8. **Check your progress** on the Analytics page: words written, issues found,
   and acceptance rate for today, this week and this month. Stored in your own
   browser — see [Privacy](#privacy).

**If unsure about a suggestion, ignore it.** The confidence slider in the header
raises or lowers the display threshold, and "low-conf" reveals what is being held
back below it.

---

## What it can do, with examples

Every example below was run through the checker while writing this file.

### ণত্ব ও ষত্ব বিধান — the ণ/ষ rules

```
এর কারন কী কেউ জানে না।     →  কারন → কারণ    (NOTVA_SHOTVA, ণত্ব-বিধান §2)
শীতকালে ঠান্ডা বাতাস বয়।     →  no edits
```

Both বিধান apply to **তৎসম** vocabulary only. `ঠান্ডা` is দেশি, so `ন` is already
correct and the rule is not applied — which is exactly what a pattern-matching
checker gets wrong.

### গুরুচণ্ডালী দোষ — সাধু/চলিত mixing

```
সে তাহার বইটা পড়ছে।           →  তাহার → তার   (GURUCHANDALI_DOSHA)
সে তাহার পুস্তক পাঠ করিতেছে।   →  no edits
```

The second sentence is consistently সাধু. That is correct prose, not an error,
so it is left alone.

### Spelling, with affix awareness

```
তিনি একজন বিখ্যত লেখক।   →  বিখ্যত → বিখ্যাত   (NON_WORD)
বইগুলোকেও আমি পড়েছি।     →  no edits
```

`বইগুলোকেও` is in no dictionary and is perfectly correct — affixes are stripped
and the stem re-checked. Suggestions are ranked by *sound*, not just edit
distance, because শ/ষ/স and ন/ণ are homophonous in modern Bengali.

### Punctuation

```
আমি বাড়ি যাচ্ছি ।                     →  " ।" → "।"   (PUNCTUATION)
তিনি ২০২৪ সালে Ph.D. সম্পন্ন করেছেন।   →  no edits
```

The dari (।) ends a Bengali sentence; a period does not. But a period inside an
abbreviation, a decimal, or a URL is correct and is never flagged.

### Other scripts — marked, not judged

```
আমি Python দিয়ে কাজ করি।              →  "Python" highlighted (latin)
তিনি ২০২৪ সালে Ph.D. সম্পন্ন করেছেন।   →  "Ph.D" highlighted (latin)
```

Reported as out-of-scope spans, never as errors. Silence would be
indistinguishable from approval; this says plainly which parts were skipped.
Bengali and ASCII digits, currency and punctuation are script-neutral and never
marked.

### Readability

```bash
python -m bhashasetu.cli readability "বাংলা ভাষার ইতিহাস অত্যন্ত সমৃদ্ধ।"
```

A score built for Bengali, not a ported Flesch-Kincaid, with every component
shown. In English, word length signals difficulty; in Bengali it mostly measures
agglutination. The real signal is তৎসম density. Formula and its limits:
[`docs/readability.md`](docs/readability.md).

### JSON, for scripting

```bash
python -m bhashasetu.cli check --json "এর কারন কী?"
```

Each edit carries `start`, `end`, `original`, ranked `suggestions`, `errorClass`,
`confidence`, `stage`, both explanations, and `ruleReference`. Offsets index the
text you submitted.

---

## Where it stands

Measured on 376 error cases and 124 clean sentences:

| Error class | Category | Stage | N | P | R | F0.5 |
|---|---|---|---:|---:|---:|---:|
| `REGISTER_INCONSISTENCY` | register | 1 | 12 | 1.000 | 0.917 | 0.982 |
| `PUNCTUATION` | punctuation | 1 | 30 | 0.968 | 1.000 | 0.974 |
| `GURUCHANDALI_DOSHA` | register | 1 | 45 | 0.957 | 1.000 | 0.966 |
| `CLASSIFIER` | morphology | 1 | 25 | 1.000 | 0.720 | 0.928 |
| `VERB_INFLECTION` | morphology | 1 | 35 | 0.966 | 0.800 | 0.927 |
| `NOTVA_SHOTVA` | orthography | 1 | 60 | 1.000 | 0.700 | 0.921 |
| `AGREEMENT` | syntax | 1 | 25 | 0.889 | 0.320 | 0.656 § |
| `NON_WORD` | orthography | 1 | 50 | 0.671 | 0.980 | 0.716 ‡ |
| `HOMONYM` | orthography | 1 | 27 | 1.000 | 0.148 | 0.465 † |
| `CASE_MARKER`, `WORD_ORDER`, `POS_ERROR` | — | Phase 2 | 67 | — | — | 0.000 |

```
false positives on clean text     0.00%  (0/124)   ceiling 3%
macro F0.5 (implemented classes)  0.837
latency p50 / p95 / p99 (ms)      5 / 581 / 674
gold set                          353 / 376 human-verified (23 awaiting sign-off)
```

§ `CLASSIFIER`, `VERB_INFLECTION` and `AGREEMENT` were Phase-2 classes until a
round of testing on prose outside the demo sample showed the common cases are
decidable from closed tables: a pronoun subject against a finite verb
(সে খাইবেন), a quantifier against a plural noun (সব ছাত্ররা), a numeral's classifier against
its head noun (একটি নারী). The parts that genuinely need a parser — arbitrary
noun-phrase subjects, tense-versus-adverb agreement — are still Phase 2, which
is why `AGREEMENT` recall is 0.320 rather than something that looks finished.

**The clean-text false-positive rate is the number that matters.** A checker that
underlines correct Bengali gets abandoned in one session; one that misses an
error merely leaves the writer where they started.

† Homonyms are correctly-spelt real words in the wrong slot (দিন/দীন). Stage 1
has three collocation rules and no sentence context, so it catches one case in 24
— but never guesses. Published research puts LLM accuracy on this class below
20%; it is a Phase 2 job.

‡ NON_WORD recall is 0.980. The precision figure is largely a scoring artefact:
sentences in *other* class slices contain deliberately malformed tokens, and every
surfaced edit that is not the expected one is charged as a false positive to
whichever class emitted it.

**Known limitation:** p99 latency of 674 ms sits just under the 800 ms budget.
It is almost entirely Hunspell's suggester on cold unknown words, and the gold
set is unusually dense with them. It is capped at 25 suggester calls per request.
Teaching the lexicon the numeral compounds (দুইশত, পাঁচশো) took a measurable bite
out of this for the same reason it removed the false positives: every word the
dictionary already knows is a suggester call that never happens.

---

## Roadmap by phase

### Phase 1 — Foundation ✅ shipped

`LanguagePack` interface, Stage 0 normalizer, Stage 1 lexical and rule checker,
evaluation harness, 353-case gold set, anonymous identity, CLI.

### Phase 3 (partial) — Application ✅ shipped early

FastAPI backend and the full Next.js + TipTap editor, brought forward because a
CLI-only checker is hard to evaluate as a product. Delivered: inline decorations,
suggestion table with accept / reject / accept-all, undo, five themes, resizable
panes, bilingual interface, landing and analytics pages.

**Still open in Phase 3:** Redis caching, incremental sentence-scoped re-check
(the whole document is re-checked today), server-side persistence of documents
and recovery-phrase hashes, and the Bengali typography QA pass across
Windows / Android / Safari.

### Phase 2 — Neural pipeline 🔜 next

Fine-tune BanglaBERT (detection) and BanglaT5 (correction) on Vaiyākaraṇa. Stand
up vLLM with Sarvam-30B and Qwen3-14B, run the head-to-head benchmark, and commit
the decision with data. Add confidence gating and escalation.

This is what activates the three still-dormant error classes — `CASE_MARKER`,
`WORD_ORDER`, `POS_ERROR` — lifts `CLASSIFIER`, `VERB_INFLECTION` and
`AGREEMENT` past the closed tables they run on today, and makes `HOMONYM` more
than a handful of collocation rules.

**Blocked on:** confirming Vaiyākaraṇa's availability and licence. The 12-class
taxonomy is built to match it.

### Phase 4 — Linguist tools

সাধু↔চলিত converter, completing the Bijoy↔Unicode table (detection ships today;
conversion refuses below 95% table coverage rather than producing convincing
garbage), Avro-style phonetic input, morphological analyser with sandhi and samas
decomposition, POS tagger view, CoNLL-U / TEI / CSV export, custom dictionaries
and house style guide, public REST API.

The morphological analyser also unlocks the তৎসম origin tag, which both the
ণত্ব/ষত্ব rules and the readability score currently approximate with heuristics.

### Phase 5 — Gamification

ভাষা স্কোর, 12-class error heatmap, streaks with freeze tokens, XP and Bengali
literary tiers, spaced-repetition micro-lessons built from the user's own
recurring errors, weekly wrapped cards, badges, opt-in cohort leaderboards,
community adjudication for low-confidence edits. Plus a Hindi language-pack stub
to prove the abstraction holds.

The analytics page is the first step: it already records the counts these
features need.

### Phase 6 — Hardening

Load testing, GPU autoscaling, OpenTelemetry and Grafana, abuse rate limiting,
a WCAG 2.2 AA audit including screen-reader behaviour with Bengali text, and a
full security review.

---

## Architecture

A **five-stage cascading pipeline**, not `text → LLM → corrected text`. Each
stage is independently testable and swappable, and every stage emits structured
`Edit` objects rather than rewritten prose — rewritten prose cannot be accepted
one change at a time, and cannot be scored.

| Stage | Name | Owns | Status |
|---|---|---|---|
| 0 | NORMALIZE | Unicode NFC + Bengali-specific repair, invisible characters, dari handling, Bijoy detection | **shipped** |
| 1 | LEXICAL | Dictionary lookup with affix stripping, Damerau-Levenshtein + Bangla-Soundex ranking, ণত্ব/ষত্ব, punctuation, register | **shipped** |
| 2 | DETECT | BanglaBERT token classification | Phase 2 |
| 3 | CORRECT | BanglaT5, span-constrained | Phase 2 |
| 4 | REASON | LLM for hard cases and teaching explanations | Phase 2 |

Stages 2–4 are **absent, not stubbed**. They report as `skipped`, so nothing
credits them with work they did not do.

**Backend:** FastAPI + Pydantic v2, Python 3.12+.
**Frontend:** Next.js 15 (App Router), TypeScript, Tailwind, TipTap/ProseMirror.
**Data:** SQLite for local dev; PostgreSQL 16 is the target.

---

## Design decisions worth knowing

- **Stages emit `Edit` objects, never rewritten text.**

- **NFC is not sufficient for Bengali.** U+09DC ড়, U+09DD ঢ়, U+09DF য় are in
  Unicode's composition-exclusion table, so `ড + ়` stays decomposed after NFC,
  compares unequal to `ড়`, misses the dictionary, and produces a false spelling
  flag on correctly typed text. The normalizer composes them explicitly, and a
  byte-level CI lint keeps every data file in composed form — the two look
  identical on screen, so this is not catchable by review.

- **ণত্ব/ষত্ব apply to তৎসম words only.** Phase 1 runs an explicit, hand-checked
  violation list rather than the generative rule, because applying the pattern
  blindly "corrects" ঠান্ডা into a misspelling.

- **Foreign text is out of scope, not wrong.** Reported as an `OutOfScopeSpan`,
  deliberately not a 13th error class. If English counted as errors, every
  mixed-script document would drag down precision.

- **The confidence gate does not delete.** Suppressed edits are returned
  separately, so the cost of a threshold change is measurable before it ships.

- **Offsets index the text you sent**, not the normalized text. Stage 0 can
  change length, and returning normalized offsets made replacements land a
  character early.

### Privacy

Your text is never stored server-side. It is checked and discarded when the
response is sent.

Analytics live in your own browser via IndexedDB. That store holds **counts and
error-class names only** — it has no field that could contain your text, and a
test asserts no Bengali code point ever appears in a stored record. Spec §10 asks
for no server-side persistence; this persists nothing locally either, because a
keystroke log in your own browser is still a keystroke log.

---

## Repository layout

```
src/bhashasetu/
  core/                  language-agnostic; CI fails if Bengali appears here
    types.py             Edit, ErrorClass (12), CheckResult, OutOfScopeSpan
    protocols.py         the LanguagePack contract
    pipeline.py          the cascade, confidence gate, overlap resolution
    identity.py          UUIDv7 device ids, 12-word recovery phrases
    storage.py           SQLite schema; upgrade_anonymous_to_account
  language_packs/bn/
    normalizer.py        Stage 0
    rules.py             Stage 1
    lexicon.py           dictionary + affix stripping + Hunspell
    phonetic.py          Bangla Soundex
    scope.py             out-of-scope (non-Bengali) detection
    error_classes.yaml   all 12 classes, both languages, rule citations
    data/                lexicon, ণত্ব/ষত্ব rules, register pairs, confusions
  api/                   FastAPI app and wire models
  eval/harness.py        per-class P/R/F0.5, clean-text FP rate, regression gate
  cli.py

frontend/
  app/                   landing (/), editor (/editor), analytics (/analytics)
  components/            Editor, SuggestionTable, DetailPane, Panels, HeroArt
  lib/                   api, types, i18n, theme, layout, analytics, offsets

eval/gold/               353 error cases + 124 clean sentences, README first
scripts/                 lints, gold validation, dictionary fetch
docs/                    phase1-review.md, readability.md
```

Further reading: [`docs/phase1-review.md`](docs/phase1-review.md) (what was
built, what was assumed, where the spec is wrong),
[`frontend/README.md`](frontend/README.md) (coordinate systems, theming,
IndexedDB), [`eval/gold/README.md`](eval/gold/README.md) (gold-set provenance).

---

## Licence

Application code: **TBD.**

Third-party components carry their own terms and are **not** vendored:

- **bn_BD Hunspell dictionary** — downloaded by `scripts/fetch_dictionaries.py`,
  gitignored. The `.aff` carries "Copyright 2018 Jacob Thomas, Bengal Creative
  Media LTD" and no explicit licence grant. **Resolve before distributing.**
- **Vaiyākaraṇa corpus** (Phase 2) — availability and licence unconfirmed.
- **Model weights** (Phase 2) — BanglaBERT, BanglaT5, Sarvam-30B / Qwen3-14B.

None of this blocks development; it blocks distribution.
