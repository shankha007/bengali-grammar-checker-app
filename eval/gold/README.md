# Gold set — provenance and review process

**Read this before quoting any number produced from this data.**

## Status

| | count |
|---|---:|
| error cases | 376 |
| clean sentences | 104 |
| `review: human` (signed off by the project owner, 2026-08-02) | **353** |
| `review: model` (awaiting sign-off) | 23 |

**Verification: partial.** 353 error cases were reviewed and accepted by the
project owner. Cases retain `source: model-authored` — that records who *wrote*
them — with `reviewed_by: project-owner` recording who checked them.

The 23 unsigned cases are the 2026-08-04 second pass: `gd-036`–`gd-045`,
`ns-051`–`ns-060` and `hm-031`–`hm-033`, added after testing the checker on
prose outside the demo sample. They exist because the gold set had been sampling the same shapes the
detector already handled — GURUCHANDALI_DOSHA scored 1.000 recall on 35 cases
while the সাধু honorific column (গিয়াছেন, করিয়াছেন) was mislabelled চলিত and
চলিত future (যাবে, করবেন) was not a marker at all. A gold set that only asks
questions the implementation can answer measures nothing; these ask the ones it
was getting wrong. They need the same sign-off as everything above them.

**Count: still short.** Spec §8 asks for 600; there are 376. `make eval-strict`
therefore still exits non-zero, on the count and on the 23 unsigned cases.
Raising it to 600 means authoring ~225 more, weighted toward the classes that
stopped early — see "Known weak spots" below.

`make eval` passes and reports the metrics.

## Why `review` is three-valued

`none` / `model` / `human`, not a boolean. Collapsing `model` into `verified`
would have let the project claim a bar it had not cleared, and the distinction
stays useful now: it is what lets `make eval` say whether the remaining shortfall
is *unreviewed cases* or *not enough cases*. Those need different work.

One caveat survives sign-off. Human review establishes that the Bengali is
correct; it does not make the sample independent, because these sentences were
still authored by the process being measured. Augmenting `clean.yaml` from real
published Bengali — spec §2 names Bangla Wikipedia and Prothom Alo dumps — would
strengthen the false-positive claim further, and remains the cheapest win
available on the metric that matters most.

## How to review a case

Take one file at a time — they are split per error class so a reviewer can hold
one grammatical topic in their head for a whole sitting.

For each case, confirm all four:

1. **The sentence is natural.** Would a competent writer plausibly produce it?
   Contrived sentences make the eval measure the wrong thing.
2. **The marked span really is an error**, and an error *of the stated class*.
   The boundaries that need the most care:
   - NON_WORD vs HOMONYM — is the erroneous form a real word? If yes it is
     HOMONYM.
   - NOTVA_SHOTVA vs NON_WORD — is the word তৎসম? The ণত্ব/ষত্ব বিধান apply to
     তৎসম only. If it is দেশি or বিদেশি there is no error at all.
   - VERB_INFLECTION vs AGREEMENT — person/honorific is VERB_INFLECTION;
     number/animacy is AGREEMENT.
   - GURUCHANDALI_DOSHA vs REGISTER_INCONSISTENCY — within one sentence vs
     across the document.
3. **`right` is the correction a careful editor would actually make** — not
   merely *a* possible fix.
4. **The rest of the sentence is clean.** Any second error makes the case score
   a false positive against whichever class catches it.

Then set `review: human` and add `reviewed_by:` naming who checked it. Leave
`source:` alone — it records who *wrote* the case, which stays true.

Cases carrying a `note:` are the ones flagged as uncertain during authoring —
review those first, and delete rather than repair anything that does not survive
scrutiny. A smaller correct gold set beats a larger doubtful one.

## Tooling

```bash
make validate-gold
```

Reports two kinds of finding, and the distinction is the point:

- **errors** (fail the build) — the case is structurally incoherent: `wrong` does
  not occur in `text`, `wrong` equals `right`, or a class is below the spec §3
  minimum of 3 cases. The eval would measure something other than what the case
  claims.
- **warnings** (do not fail the build) — the case is well-formed but the lexicon
  disagrees with it. That is a finding about the dictionary, or about a rule
  over-generating, and it must never pressure anyone into editing gold data to
  quiet a tool.

There is one standing warning, kept on purpose: `nw-038` (প্রতিরোদে). The
lexicon's productive-prefix rule strips প্রতি and accepts the remainder রোদে, so
Stage 1 can never catch it. The case is correct Bengali and stays; the eval
reports the miss rather than hiding it.

## Known weak spots

- **`ag-016` may be mislabelled.** "আমরা সবাই মিলে কাজটি করেছে।" is filed as
  AGREEMENT, but by this file's own boundary rule — person/honorific is
  VERB_INFLECTION, number/animacy is AGREEMENT — a first-person subject with a
  third-person verb is VERB_INFLECTION. The detector reports it as such and takes
  the scoring penalty rather than having the rule contort to match one case. A
  reviewer should settle it.

- **HOMONYM (27 cases)** — below the 50-per-class target. Authoring these
  requires pairs where the erroneous form is a real word *and* the context makes
  it unambiguously wrong, which is genuinely hard. Padding the count with weak
  cases was tried and reverted; the number is low because the good cases ran out,
  not because the file is unfinished in any recoverable sense.
- **WORD_ORDER (20 cases)** — Bengali word order is free enough that most
  reorderings are grammatical but merely marked. Only clearly ungrammatical
  orders are included, and a reviewer should be sceptical of every one.
- **`right` for WORD_ORDER is a whole sentence**, not a token, because a
  reordering has no single replacement span.
- **REGISTER_INCONSISTENCY (12 cases)** — each is a multi-sentence document, so
  these cost more to write and to review than the per-class count suggests.
