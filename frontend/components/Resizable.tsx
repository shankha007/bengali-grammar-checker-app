"use client";

import { useEffect, useRef, useState } from "react";

import { useLang } from "@/lib/i18n";

interface HandleProps {
  orientation: "vertical" | "horizontal";
  value: number;
  onChange: (next: number) => void;
  onReset: () => void;
  limits: { min: number; max: number };
  /** Dragging right/down should shrink this pane rather than grow it. */
  invert?: boolean;
  label: string;
  className?: string;
}

/**
 * A drag handle between two panes.
 *
 * Pointer events rather than mouse events so it works with touch and pen, and
 * `setPointerCapture` so a fast drag that outruns the 6px handle keeps tracking
 * instead of dropping the gesture.
 *
 * Keyboard-operable via `role="separator"` and arrow keys, because a
 * mouse-only layout control fails WCAG 2.2 (spec §10) — and because a resize
 * you cannot undo without a mouse is worse than no resize.
 */
export function ResizeHandle({
  orientation,
  value,
  onChange,
  onReset,
  limits,
  invert = false,
  label,
  className = "",
}: HandleProps) {
  const { t } = useLang();
  const [dragging, setDragging] = useState(false);
  const origin = useRef({ pos: 0, value: 0 });

  const vertical = orientation === "vertical";

  // While a drag is in flight, suppress selection and force the resize cursor
  // document-wide. Without this the browser starts selecting the editor's
  // Bengali text the moment the pointer outruns the 6px handle.
  useEffect(() => {
    if (!dragging) return;
    const prevCursor = document.body.style.cursor;
    const prevSelect = document.body.style.userSelect;
    document.body.style.cursor = vertical ? "col-resize" : "row-resize";
    document.body.style.userSelect = "none";
    return () => {
      document.body.style.cursor = prevCursor;
      document.body.style.userSelect = prevSelect;
    };
  }, [dragging, vertical]);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    origin.current = { pos: vertical ? e.clientX : e.clientY, value };
    setDragging(true);
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    const current = vertical ? e.clientX : e.clientY;
    const delta = current - origin.current.pos;
    onChange(origin.current.value + (invert ? -delta : delta));
  };

  const stop = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
    setDragging(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 48 : 16;
    const back = vertical ? "ArrowLeft" : "ArrowUp";
    const fwd = vertical ? "ArrowRight" : "ArrowDown";
    if (e.key === back) {
      e.preventDefault();
      onChange(value + (invert ? step : -step));
    } else if (e.key === fwd) {
      e.preventDefault();
      onChange(value + (invert ? -step : step));
    } else if (e.key === "Home") {
      e.preventDefault();
      onReset();
    }
  };

  return (
    <div
      role="separator"
      tabIndex={0}
      aria-orientation={vertical ? "vertical" : "horizontal"}
      aria-label={`${label} — ${t("resetSize")}`}
      aria-valuenow={value}
      aria-valuemin={limits.min}
      aria-valuemax={limits.max}
      title={`${label} · ${t("resetSize")}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={stop}
      onPointerCancel={stop}
      onDoubleClick={onReset}
      onKeyDown={onKeyDown}
      data-dragging={dragging || undefined}
      className={`bs-handle ${vertical ? "bs-handle-v" : "bs-handle-h"} ${className}`}
    />
  );
}
