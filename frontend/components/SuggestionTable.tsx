"use client";

import { useLang } from "@/lib/i18n";
import { CATEGORY_VAR, type Edit, type OutOfScopeSpan } from "@/lib/types";

interface Props {
  edits: Edit[];
  outOfScope: OutOfScopeSpan[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAccept: (edit: Edit, replacement: string) => void;
  onReject: (edit: Edit) => void;
}

/**
 * Suggestions as a dense table.
 *
 * The card layout this replaces put the Bengali explanation on every row, which
 * meant six suggestions filled the viewport and anything past that needed
 * scrolling to even know it existed. A table shows ~20 rows in the same space:
 * the user sees the whole shape of the problem at once and reads the reasoning
 * only for the row they care about, in the detail pane below.
 */
export default function SuggestionTable({
  edits,
  outOfScope,
  selectedId,
  onSelect,
  onAccept,
  onReject,
}: Props) {
  const { t } = useLang();

  if (!edits.length && !outOfScope.length) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-xs"
           style={{ color: "var(--text-muted)" }}>
        <span >{t("nothingToReport")}</span>
      </div>
    );
  }

  return (
    <div className="scroll-y h-full">
      <table className="tbl tbl-fixed">
        <thead>
          <tr>
            <th style={{ width: 16 }} aria-label={t("colCategory")} />
            <th>{t("colText")}</th>
            <th>{t("colFix")}</th>
            <th style={{ width: 74 }}>{t("colType")}</th>
            <th style={{ width: 30 }} className="text-right">
              %
            </th>
            <th style={{ width: 66 }} />
          </tr>
        </thead>
        <tbody>
          {edits.map((e) => (
            <tr
              key={e.id}
              data-selected={selectedId === e.id}
              onClick={() => onSelect(e.id)}
              tabIndex={0}
              onKeyDown={(ev) => {
                if (ev.key === "Enter" && e.suggestions[0]) {
                  onAccept(e, e.suggestions[0]);
                }
              }}
            >
              <td>
                <span
                  aria-hidden
                  className="inline-block h-2 w-2 rounded-full align-middle"
                  style={{ background: CATEGORY_VAR[e.category] }}
                />
              </td>
              <td className="truncate" title={e.original}>
                {e.original.trim() || <em style={{ opacity: 0.6 }}>—</em>}
              </td>
              <td
                className="truncate font-medium"
                style={{ color: "var(--ok)" }}
                title={e.suggestions.join(", ")}
              >
                {e.suggestions[0] ?? "—"}
              </td>
              <td
                className="truncate text-[10px] uppercase tracking-wide"
                style={{ color: "var(--text-muted)" }}
                title={e.errorClass}
              >
                {e.errorClass.replace(/_/g, " ")}
              </td>
              <td className="text-right tabular-nums" style={{ color: "var(--text-muted)" }}>
                {(e.confidence * 100).toFixed(0)}
              </td>
              <td>
                <div className="flex justify-end gap-1">
                  {e.suggestions[0] && (
                    <button
                      className="btn btn-icon btn-primary"
                      onClick={(ev) => {
                        ev.stopPropagation();
                        onAccept(e, e.suggestions[0]);
                      }}
                      aria-label={`${t("acceptAria")}: ${e.original} → ${e.suggestions[0]}`}
                    >
                      ✓
                    </button>
                  )}
                  <button
                    className="btn btn-icon"
                    onClick={(ev) => {
                      ev.stopPropagation();
                      onReject(e);
                    }}
                    aria-label={t("ignoreAria")}
                  >
                    ✕
                  </button>
                </div>
              </td>
            </tr>
          ))}

          {outOfScope.map((s, i) => (
            <tr key={`oos-${i}`} style={{ cursor: "default" }}>
              <td>
                <span
                  aria-hidden
                  className="inline-block h-2 w-2 rounded-sm align-middle"
                  style={{ background: "var(--unsupported)" }}
                />
              </td>
              <td className="truncate" title={s.text}>
                {s.text}
              </td>
              {/* "not checked" sits in the Fix column, which is wide enough for
                  it. In the 66px action column it wrapped to two lines and
                  collided with the row above. */}
              <td
                className="truncate text-[11px] italic"
                style={{ color: "var(--text-muted)" }}
                title={`${s.script} ${t("outOfScopeTitle")}`}
              >
                {t("notChecked")}
              </td>
              <td
                className="truncate text-[10px] uppercase tracking-wide"
                style={{ color: "var(--text-muted)" }}
                title={`${s.script} ${t("outOfScopeTitle")}`}
              >
                {s.script}
              </td>
              <td className="text-right" style={{ color: "var(--text-muted)" }}>
                —
              </td>
              <td />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
