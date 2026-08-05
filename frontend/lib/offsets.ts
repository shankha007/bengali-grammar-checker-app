import type { Node as PMNode } from "@tiptap/pm/model";

/**
 * Bridge between the two coordinate systems in play.
 *
 * The pipeline speaks **character offsets into a flat string**. ProseMirror
 * speaks **document positions**, which count node boundaries as well as
 * characters — so the two diverge by one for every block opened before a given
 * point, and by more once there is nesting.
 *
 * Getting this wrong does not throw; it silently shifts every underline by a
 * few characters, which looks like a checker that cannot spell. So the flat
 * string is built here, from the same walk that records the mapping, rather
 * than taken from `editor.getText()` and hoped to line up.
 */

export interface Segment {
  /** ProseMirror position of the first character of this text node. */
  pmFrom: number;
  /** Offset of that same character in the flat string. */
  textStart: number;
  length: number;
}

export interface DocIndex {
  text: string;
  segments: Segment[];
}

/** Separator inserted between text blocks. Must match what the backend sees. */
export const BLOCK_SEPARATOR = "\n";

export function buildDocIndex(doc: PMNode): DocIndex {
  const parts: string[] = [];
  const segments: Segment[] = [];
  let textLen = 0;
  let seenTextblock = false;

  const walk = (node: PMNode, pos: number): void => {
    if (node.isText) {
      const value = node.text ?? "";
      segments.push({ pmFrom: pos, textStart: textLen, length: value.length });
      parts.push(value);
      textLen += value.length;
      return;
    }

    if (node.isTextblock) {
      if (seenTextblock) {
        parts.push(BLOCK_SEPARATOR);
        textLen += BLOCK_SEPARATOR.length;
      }
      seenTextblock = true;
      // +1 steps inside the block's opening token.
      let childPos = pos + 1;
      node.forEach((child) => {
        walk(child, childPos);
        childPos += child.nodeSize;
      });
      return;
    }

    let childPos = pos + (node.type.name === "doc" ? 0 : 1);
    node.forEach((child) => {
      walk(child, childPos);
      childPos += child.nodeSize;
    });
  };

  walk(doc, 0);
  return { text: parts.join(""), segments };
}

/**
 * Map a flat-string span to a ProseMirror range.
 *
 * Returns null when the span falls outside the mapped text — which happens
 * legitimately while a response is in flight and the user keeps typing. A stale
 * decoration is worse than a missing one, so the caller drops it.
 */
export function spanToRange(
  index: DocIndex,
  start: number,
  end: number,
): { from: number; to: number } | null {
  if (end <= start) return null;

  let from: number | null = null;
  let to: number | null = null;

  for (const seg of index.segments) {
    const segEnd = seg.textStart + seg.length;
    if (from === null && start >= seg.textStart && start < segEnd) {
      from = seg.pmFrom + (start - seg.textStart);
    }
    if (end > seg.textStart && end <= segEnd) {
      to = seg.pmFrom + (end - seg.textStart);
    }
    if (from !== null && to !== null) break;
  }

  if (from === null || to === null || to <= from) return null;
  return { from, to };
}
