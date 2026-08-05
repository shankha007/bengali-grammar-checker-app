import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

import { buildDocIndex, spanToRange } from "./offsets";
import type { Edit, OutOfScopeSpan } from "./types";

export const editHighlightKey = new PluginKey<DecorationSet>("bhashasetu-edits");

export interface HighlightOptions {
  edits: Edit[];
  outOfScope: OutOfScopeSpan[];
}

/**
 * Decoration-based inline highlighting.
 *
 * Spec §4 requires TipTap/ProseMirror specifically for this: decorations are a
 * *view-layer* overlay. They never enter the document, so highlighting cannot
 * corrupt the user's text, does not enter the undo history, and does not fire
 * change events that would re-trigger a check.
 *
 * Two visually distinct kinds, and the distinction is the whole point:
 *
 *   `.bs-flag`        wavy underline, category-coloured — "this looks wrong"
 *   `.bs-unsupported` flat yellow fill — "this is not Bengali, I did not read it"
 *
 * Out-of-scope decorations are drawn first so an error inside a foreign run
 * (which should not happen, but would be a bug worth seeing) paints on top.
 *
 * Decorations are rebuilt on every doc change rather than mapped through
 * transactions. Mapping is cheaper but slides stale marks along with edits,
 * leaving an underline under a word the user already fixed. A fresh check is
 * 600 ms away regardless, so correctness beats the microseconds.
 */
export const EditHighlight = Extension.create<HighlightOptions>({
  name: "editHighlight",

  addOptions() {
    return { edits: [], outOfScope: [] };
  },

  addProseMirrorPlugins() {
    const extension = this;

    const build = (doc: Parameters<typeof buildDocIndex>[0]): DecorationSet => {
      const edits: Edit[] = extension.options.edits ?? [];
      const scope: OutOfScopeSpan[] = extension.options.outOfScope ?? [];
      if (!edits.length && !scope.length) return DecorationSet.empty;

      const index = buildDocIndex(doc);
      const decorations: Decoration[] = [];

      for (const span of scope) {
        const range = spanToRange(index, span.start, span.end);
        if (!range) continue;
        decorations.push(
          Decoration.inline(range.from, range.to, {
            class: "bs-unsupported",
            "data-script": span.script,
            title:
              `“${span.text}” — ${span.script} text. The Bengali engine has no ` +
              `opinion here; it is highlighted, not corrected.`,
          }),
        );
      }

      for (const edit of edits) {
        const range = spanToRange(index, edit.start, edit.end);
        if (!range) continue; // stale relative to the current doc; drop it
        decorations.push(
          Decoration.inline(range.from, range.to, {
            class: "bs-flag",
            "data-edit-id": edit.id,
            "data-category": edit.category,
            style: `--flag-color:var(--cat-${edit.category})`,
          }),
        );
      }

      return DecorationSet.create(doc, decorations);
    };

    return [
      new Plugin<DecorationSet>({
        key: editHighlightKey,
        state: {
          init: (_config, state) => build(state.doc),
          apply(tr, value, _old, newState) {
            // The meta flag is set by the React layer when a check returns.
            if (tr.getMeta(editHighlightKey) || tr.docChanged) {
              return build(newState.doc);
            }
            return value;
          },
        },
        props: {
          decorations(state) {
            return editHighlightKey.getState(state) ?? DecorationSet.empty;
          },
        },
      }),
    ];
  },
});
