"use client";

import { useLang } from "@/lib/i18n";
import { CATEGORY_LABEL, CATEGORY_VAR, type Edit } from "@/lib/types";

/**
 * Explanation for the selected row only.
 *
 * Spec §10: "Every correction the app makes must be explainable. If the system
 * cannot say *why* in Bengali, it must not surface the edit." The reasoning is
 * still mandatory — it just lives in one fixed-height pane instead of repeating
 * on every row, which is what let the table stay dense.
 */
export default function DetailPane({
  edit,
  onAccept,
  onAcceptAllOfType,
  sameTypeCount,
}: {
  edit: Edit | null;
  onAccept: (replacement: string) => void;
  onAcceptAllOfType: () => void;
  sameTypeCount: number;
}) {
  const { lang, t } = useLang();
  if (!edit) {
    return (
      <div
        className="flex h-full items-center justify-center px-3 text-center text-[11px]"
        style={{ color: "var(--text-muted)" }}
      >
        {t("selectRow")}
      </div>
    );
  }

  return (
    <div className="scroll-y h-full px-3 py-2">
      <div className="mb-1.5 flex items-center gap-2">
        <span
          aria-hidden
          className="h-2 w-2 shrink-0 rounded-full"
          style={{ background: CATEGORY_VAR[edit.category] }}
        />
        <span className="text-[10px] font-semibold uppercase tracking-wide">
          {edit.errorClass.replace(/_/g, " ")}
        </span>
        <span
          className="text-[11px]"
          style={{ color: "var(--text-muted)" }}
        >
          {CATEGORY_LABEL[edit.category][lang]}
        </span>
        <span
          className="ml-auto text-[10px] tabular-nums"
          style={{ color: "var(--text-muted)" }}
          title={`resolved at stage ${edit.stage}`}
        >
          {(edit.confidence * 100).toFixed(0)}% · S{edit.stage}
        </span>
      </div>

      {/* The selected language leads; the other stays underneath rather than
          disappearing, because a learner often wants both and the pair is what
          makes a grammar rule land. */}
      <p
        className="mb-1 text-[13px]"
        lang={lang}
      >
        {lang === "bn" ? edit.explanation_bn : edit.explanation_en}
      </p>
      <p
        className="mb-1.5 text-[11px]"
        style={{ color: "var(--text-muted)" }}
        lang={lang === "bn" ? "en" : "bn"}
      >
        {lang === "bn" ? edit.explanation_en : edit.explanation_bn}
      </p>

      {edit.ruleReference && (
        <p className="mb-1.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
          {t("rule")}: {edit.ruleReference}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-1">
        {edit.suggestions.slice(0, 5).map((s, i) => (
          <button
            key={s}
            className={`btn ${i === 0 ? "btn-primary" : ""}`}
            onClick={() => onAccept(s)}
          >
            {s}
          </button>
        ))}
        {edit.suggestions.length === 0 && (
          <span className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>
            {t("noAutoFix")}
          </span>
        )}
        {sameTypeCount > 1 && edit.suggestions[0] && (
          <button className="btn ml-auto" onClick={onAcceptAllOfType}>
            {t("acceptAll")} {sameTypeCount}
          </button>
        )}
      </div>
    </div>
  );
}
