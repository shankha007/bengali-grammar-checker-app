/**
 * Rendering helpers for spans whose content is not self-describing on screen.
 */

/**
 * Spaces and tabs, made visible.
 *
 * Several punctuation rules flag whitespace and nothing else: a space before the
 * dari, a missing space after a comma, a run of spaces between two words.
 * Rendered literally those rows were unreadable — the table trimmed the flagged
 * text and so showed an em dash for a run of spaces, and the fix column showed a
 * single space, which is to say nothing at all. The user saw "— → " and had to
 * guess what was being proposed.
 *
 * A middle dot per space says exactly what changed and keeps the count visible:
 * "···" → "·" is a legible instruction in a way that "" → "" is not.
 * Non-whitespace in the span is left alone, so " ।" reads "·।".
 *
 * Display only. The value handed to `onAccept` is always the real string — the
 * dots must never reach the document.
 */
export function showSpaces(s: string): string {
  return s.replace(/\t/g, "→").replace(/ /g, "·");
}
