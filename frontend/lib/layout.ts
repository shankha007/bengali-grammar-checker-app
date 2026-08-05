/**
 * Pane sizes for the editor's three-column layout.
 *
 * Data + hook only, no components — a file that exports both makes Fast Refresh
 * fall back to a full page reload on every edit, which is noisy and (in dev)
 * manufactures spurious hydration warnings.
 */

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "bs-layout";

export interface Layout {
  /** Width of the suggestions column, px. */
  mid: number;
  /** Width of the side panel column, px. */
  side: number;
  /** Height of the detail pane under the suggestion table, px. */
  detail: number;
}

export const DEFAULT_LAYOUT: Layout = { mid: 440, side: 260, detail: 150 };

/**
 * Clamps, not just defaults.
 *
 * A pane dragged to zero is unrecoverable — there is nothing left to grab — and
 * a persisted zero makes the app look broken on next load with no obvious
 * cause. The minimums are the width at which each pane still does its job.
 */
export const LIMITS = {
  mid: { min: 280, max: 720 },
  side: { min: 200, max: 460 },
  detail: { min: 90, max: 400 },
} as const;

const clamp = (v: number, k: keyof Layout) =>
  Math.round(Math.min(LIMITS[k].max, Math.max(LIMITS[k].min, v)));

export function useLayout() {
  // Defaults on the first render, server and client alike; storage is read in
  // an effect so hydration always matches.
  const [layout, setLayout] = useState<Layout>(DEFAULT_LAYOUT);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as Partial<Layout>;
      setLayout({
        mid: clamp(parsed.mid ?? DEFAULT_LAYOUT.mid, "mid"),
        side: clamp(parsed.side ?? DEFAULT_LAYOUT.side, "side"),
        detail: clamp(parsed.detail ?? DEFAULT_LAYOUT.detail, "detail"),
      });
    } catch {
      /* corrupt or unavailable storage — defaults are fine */
    }
  }, []);

  const update = useCallback((key: keyof Layout, value: number) => {
    setLayout((prev) => {
      const next = { ...prev, [key]: clamp(value, key) };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* non-fatal */
      }
      return next;
    });
  }, []);

  const reset = useCallback(
    (key: keyof Layout) => update(key, DEFAULT_LAYOUT[key]),
    [update],
  );

  return { layout, update, reset };
}
