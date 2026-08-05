# BhashaSetu — web UI

Next.js 15 (App Router) + TypeScript + Tailwind + TipTap/ProseMirror, per spec §4.

## Running it

Two processes. The backend does the checking; Next proxies `/api/*` to it.

```bash
python -m uvicorn bhashasetu.api.app:app --port 8000
```

```bash
npm run dev
```

Then http://localhost:3000. From the repo root, `make api` and `make web` do the
same thing.

The proxy is not cosmetic: it keeps the browser on a single origin, which keeps
the `bhashasetu_device` cookie first-party. Cross-origin it would be dropped by
default and the anonymous identity (spec §5) would stop persisting — silently,
because everything else still works.

## Why TipTap and not a textarea

Spec §4 calls for it and the reason is decorations. A ProseMirror `Decoration`
is a **view-layer** overlay: it never enters the document. So highlighting
cannot corrupt the user's text, does not enter the undo history, and does not
fire change events that would re-trigger a check. A textarea would force either
a contenteditable overlay hack or a mirrored-div, both of which break on
Bengali's conjunct rendering and vowel-sign reordering.

## The coordinate problem

This is the thing to understand before changing `lib/`.

Three coordinate systems are in play:

| System | Unit | Lives in |
|---|---|---|
| normalized offsets | characters of the Stage-0 output | the pipeline |
| original offsets | characters of what the client sent | the wire |
| ProseMirror positions | doc positions, counting node boundaries | the editor |

The API converts the first into the second (`_remap_to_original` in
`api/app.py`) so the client never sees normalized coordinates. Stage 0 changes
length — composing `ড + ়` into `ড়` removes a character — so an edit at
normalized offset 40 can be at original offset 41. Shipping normalized offsets
made a replacement land one character early and eat the preceding space; "এর
কারন" became "এরকারণ". There is a regression test for it in
`tests/test_api.py::test_offsets_index_the_text_the_client_sent`.

`lib/offsets.ts` converts the second into the third. It builds the flat string
from the *same walk* that records the mapping, rather than taking
`editor.getText()` and hoping the two line up. Getting this wrong does not
throw — it shifts every underline a few characters left, which reads as a
checker that cannot spell.

## Two kinds of highlight

The visual grammar carries meaning, so the two must not converge:

| | Look | Means |
|---|---|---|
| `.bs-flag` | wavy underline, category-coloured | this looks wrong |
| `.bs-unsupported` | flat yellow fill, dotted underline | not Bengali — not read |

Out-of-scope spans come from the backend (`language_packs/bn/scope.py`) and are
never `Edit`s. Rendering them the same as errors would tell a user their English
had been checked and passed.

## Themes

Five, driven by CSS variables on `data-theme` rather than Tailwind `dark:`
variants — with more than two themes the variant approach multiplies out across
every component. Components reference semantic names (`--surface`,
`--text-muted`, `--cat-register`), so a sixth theme is one block in
`globals.css` plus one entry in `lib/theme.ts`.

The theme is applied by an inline script in `<head>` before first paint;
anything deferred shows a flash of the wrong theme on every load.

## Pages

| Route | What it is |
|---|---|
| `/` | Landing — hero artwork plus one detailed section per shipped capability |
| `/editor` | The checker |
| `/analytics` | Daily / weekly / monthly counts from IndexedDB |

The scroll lock is scoped to `/editor` via an `.app-fixed` class added on mount
and removed on unmount. Landing and analytics are ordinary documents and must
scroll; a global lock would clip them.

## The landing page

`components/HeroArt.tsx` is an inline SVG, not a photograph. A stock image would
need a licence and a download, would soften on a 2x display, and — the actual
reason — no photograph shows what this product does. The illustration *is* the
product: Bengali prose with a category-coloured wavy underline under the error, a
flat yellow highlight over the English it will not judge, and the suggestion card
carrying the correction and the rule. Every colour is a CSS variable, so it
follows all five themes.

Only shipped capabilities are listed, and each carries a worked example taken
from what the running checker actually produces. The `Left alone` rows are
load-bearing rather than decorative: what a checker declines to flag is as much a
quality claim as what it catches, and ঠান্ডা / ভাসা / বইগুলোকেও / Ph.D. are
exactly the cases a careless implementation gets wrong.

Nothing on this page claims the unbuilt stages exist. Honesty about them lives
where a user meets it — the editor greys out the six Phase-2 error classes and
the pipeline panel reports stages 2–4 as skipped.

## Analytics and IndexedDB

`lib/analytics.ts`. Three event types — `check`, `accept`, `ignore` — appended to
one object store, aggregated in the browser.

**The store cannot hold text, and that is the design.** Every field is a count or
an error-class name; there is no `text`, no `original`, no `suggestion`. Spec §10
says no text is persisted server-side; this goes further and persists none
locally either, because a keystroke log sitting in the user's own browser is
still a keystroke log. A test asserts no Bengali code point ever appears in a
stored record.

Two deliberate choices worth knowing before reading the numbers:

- **Words are a per-day high-water mark, not a sum.** A check fires every 600 ms
  while typing, so summing would report a 200-word document as tens of
  thousands. The maximum reached in a day is a defensible proxy that does not
  inflate with editing time. It undercounts someone writing several separate
  documents in a day — an honest limitation, and the safer direction to err in.
- **Days are local, not UTC.** A UTC key puts an evening's work on tomorrow's
  row.

The row shape is one a server could ingest unchanged, so the "dedicated backend
later" path is a migration rather than a rewrite.

## Screenshots

```bash
npm run screenshot        # or: make screenshot
```

Drives the Chrome or Edge already installed via `playwright-core` — no browser
download. It fails the run rather than saving a shot if a page has a horizontal
scrollbar, and reports any hydration warning seen on any page. Both are things
that are invisible to a DOM assertion and obvious in an image, which is exactly
why the check lives with the capture.

## Language toggle

Two languages for the chrome, `lib/i18n.tsx`: a flat ~70-key dictionary and a
context, rather than an i18n library that would be more code than the thing it
replaces. Bengali is listed first in every pair because it is the product's
first language, not its translation — the ordering makes an untranslated string
obvious in review.

The grammar **explanations are not translated here.** The backend already
returns `explanation_bn` and `explanation_en` for every edit; the toggle picks
which one leads in the detail pane and keeps the other underneath. A Bengali
grammar rule explained in English is a different sentence, not a translated one,
and it belongs beside the rule in `error_classes.yaml`.

One effect owns `document.documentElement.lang`, not the setter. The
restore-from-storage path sets state directly, so a setter-side assignment left
`<html lang="bn">` while the chrome rendered in English — a screen reader would
announce English labels in a Bengali voice, and only after a reload. The editor
keeps its own `lang="bn"` throughout: its content is Bengali whichever language
the buttons are in.

## Resizable panes

Three drag handles — editor|table, table|detail, table|side — in
`components/Resizable.tsx`. Sizes live in state, are written to CSS custom
properties (`--col-mid`, `--col-side`, `--row-detail`), and persist to
`localStorage`.

Handles are **grid items, not overlays**. An absolutely-positioned handle drifts
out of alignment the moment a pane's content changes its intrinsic width.

Three things that are easy to leave out and shouldn't be:

- **Clamps, not just defaults.** A pane dragged to zero is unrecoverable —
  there is nothing left to grab — and a persisted zero makes the app look broken
  on next load with no obvious cause. Minimums are the width at which each pane
  still does its job.
- **Keyboard operation.** `role="separator"` with arrow keys (Shift for a bigger
  step, Home to reset). A mouse-only layout control fails WCAG 2.2, and a resize
  you cannot undo without a mouse is worse than no resize.
- **Pointer events with capture,** not mouse events, so touch and pen work and a
  fast drag that outruns the 6px handle keeps tracking instead of dropping the
  gesture. While dragging, the body cursor and `user-select` are overridden —
  otherwise the browser starts selecting the editor's Bengali text mid-drag.

Handles are hidden below `lg`, where the columns stack and there is nothing
horizontal left to divide.

## Layout and scrolling

At ≥1024px `html, body { overflow: hidden }` and the three columns each scroll
internally, so the page never moves however long the document is. Below that the
columns stack and the lock is lifted — locking there would crush three panes
into ~200px each, and a cramped dashboard is worse than a scrollable one.

## Fonts

The stack is `Noto Sans Bengali` → platform Bengali faces (Nirmala UI, Kohinoor
Bangla, Lohit Bengali) → `sans-serif`. It degrades to a system Bengali face
rather than to a Latin fallback, which would render Bengali as boxes.

Spec §4 asks for self-hosted, subsetted Noto with `font-display: swap`. That is
**not done** — it needs downloading and subsetting third-party font files, which
carry their own licence (Noto is OFL). Until then the app relies on whatever
Bengali face the reader's OS provides, which means line metrics vary between
Windows and macOS. Conjunct rendering (ক্ষ, জ্ঞ, ঙ্ক্ষ) also differs between
platforms and needs the QA pass spec §4 describes.

`line-height: 1.9` is the spec §4 floor and is not negotiable downward: Bengali's
matra runs along the top of every word and collides with the previous line's
descenders at Latin-comfortable leading.

## Files

```
app/
  layout.tsx          lang="bn", theme-before-paint script
  page.tsx            state, debounced checking, three-column layout
  globals.css         five themes, Bengali typography, the two highlight styles
components/
  Editor.tsx          TipTap instance, decoration refresh, apply-edit
  SuggestionTable.tsx dense table of edits + out-of-scope rows
  DetailPane.tsx      Bengali explanation for the selected row
  Panels.tsx          readability / taxonomy / pipeline / identity, all tabular
lib/
  api.ts              fetch wrappers (credentials: "include" everywhere)
  types.ts            wire types, mirrors api/models.py
  theme.ts            theme list, persistence
  offsets.ts          flat-string ↔ ProseMirror position mapping
  EditHighlight.ts    the decoration plugin (flags + out-of-scope)
```

## What is deliberately absent

Everything scheduled after Phase 1. The UI shows the six unimplemented error
classes greyed out with a "Ph2" marker rather than hiding them, and the pipeline
panel lists stages 2–4 as skipped rather than omitting them — the same principle
as the backend: absent, not silently empty.

The recovery phrase mints but does not persist; storing the hash is Phase 3
work, and the UI says so rather than implying progress is safe.
