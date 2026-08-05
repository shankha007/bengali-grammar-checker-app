"use client";

import { useLang } from "@/lib/i18n";
import {
  CATEGORY_LABEL,
  CATEGORY_VAR,
  type CheckResponse,
  type ErrorCategory,
  type ErrorClassInfo,
  type LanguageInfo,
} from "@/lib/types";

const muted = { color: "var(--text-muted)" } as const;

function KV({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <table className="tbl">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k} style={{ cursor: "default" }}>
            <td style={muted}>{k}</td>
            <td className="text-right tabular-nums font-medium">{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Readability — never an opaque number (spec §6.3). */
export function ReadabilityPanel({ result }: { result: CheckResponse | null }) {
  const { t } = useLang();
  if (!result?.readability) {
    return (
      <p className={"p-3 text-[11px]"} style={muted}>
        {t("writeSomething")}
      </p>
    );
  }
  const r = result.readability;
  return (
    <div className="scroll-y h-full">
      <div className="flex items-baseline gap-2 px-2 py-2">
        <span className="text-2xl font-bold tabular-nums">
          {r.score?.toFixed(0)}
        </span>
        <span className={"text-[11px]"} style={muted}>
          {t("readabilityHint")}
        </span>
      </div>
      <KV
        rows={[
          [t("syllablesPerWord"), r.syllables_per_word?.toFixed(2) ?? "—"],
          [t("tatsamaDensity"), `${((r.tatsama_density ?? 0) * 100).toFixed(0)}%`],
          [t("meanSentenceLength"), r.mean_sentence_length?.toFixed(1) ?? "—"],
          [t("sentenceVariance"), r.sentence_length_variance?.toFixed(1) ?? "—"],
          [t("wordCount"), r.words ?? 0],
          [t("sentenceCount"), r.sentences ?? 0],
        ]}
      />
      {result.readabilityMissing.length > 0 && (
        <p
          className="m-2 rounded p-2 text-[10px] leading-relaxed"
          style={{ background: "var(--warn-bg)", color: "var(--warn-fg)" }}
        >
          {t("notComputed")}: <b>{result.readabilityMissing.join(", ")}</b>{" "}
          {t("readabilityCaveat")}
        </p>
      )}
    </div>
  );
}

/** Where edits resolved — a first-class metric per spec §1. */
export function PipelinePanel({ result }: { result: CheckResponse | null }) {
  const { t } = useLang();
  if (!result) {
    return (
      <p className={"p-3 text-[11px]"} style={muted}>
        {t("noRunYet")}
      </p>
    );
  }
  return (
    <div className="scroll-y h-full">
      <table className="tbl">
        <thead>
          <tr>
            <th >{t("colStage")}</th>
            <th className="text-right">{t("colEdits")}</th>
            <th className="text-right">ms</th>
          </tr>
        </thead>
        <tbody>
          {result.stages.map((s) => (
            <tr
              key={s.stage}
              style={{ cursor: "default", opacity: s.skipped ? 0.5 : 1 }}
              title={s.skipped ?? undefined}
            >
              <td>
                {s.stage} · {s.name}
              </td>
              <td className="text-right tabular-nums">
                {s.skipped ? "—" : s.edits}
              </td>
              <td className="text-right tabular-nums">
                {s.skipped ? "—" : s.ms.toFixed(1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={"p-2 text-[10px] leading-relaxed"} style={muted}>
        {t("pipelineNote")} {result.totalMs.toFixed(0)} ms.
      </p>
    </div>
  );
}

/** The 12-class taxonomy, with honest availability. */
export function TaxonomyPanel({
  classes,
  counts,
}: {
  classes: ErrorClassInfo[];
  counts: Record<string, number>;
}) {
  const { lang, t } = useLang();
  return (
    <div className="scroll-y h-full">
      <table className="tbl">
        <thead>
          <tr>
            <th style={{ width: 16 }} />
            <th >{t("colClass")}</th>
            <th className="text-right" style={{ width: 46 }}>
              {t("colFound")}
            </th>
          </tr>
        </thead>
        <tbody>
          {classes.map((c) => {
            const live = c.implementedAtStage !== null;
            return (
              <tr
                key={c.code}
                style={{ cursor: "default", opacity: live ? 1 : 0.45 }}
                title={
                  live
                    ? `${c.label_en} — ${t("activeAtStage")} ${c.implementedAtStage}`
                    : `${c.label_en} — ${t("noDetectorYet")}`
                }
              >
                <td>
                  <span
                    aria-hidden
                    className="inline-block h-2 w-2 rounded-full align-middle"
                    style={{ background: CATEGORY_VAR[c.category] }}
                  />
                </td>
                <td className="truncate">
                  {lang === "bn" ? c.label_native : c.label_en}
                </td>
                <td className="text-right tabular-nums" style={muted}>
                  {live ? (counts[c.code] ?? 0) : "Ph2"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="flex flex-wrap gap-x-3 gap-y-1 p-2 text-[10px]">
        {(Object.keys(CATEGORY_LABEL) as ErrorCategory[]).map((k) => (
          <span key={k} className="flex items-center gap-1">
            <span
              aria-hidden
              className="h-2 w-2 rounded-full"
              style={{ background: CATEGORY_VAR[k] }}
            />
            <span >{CATEGORY_LABEL[k][lang]}</span>
          </span>
        ))}
        <span className="flex items-center gap-1">
          <span
            aria-hidden
            className="h-2 w-2 rounded-sm"
            style={{ background: "var(--unsupported)" }}
          />
          <span >{t("otherScript")}</span>
        </span>
      </div>
    </div>
  );
}

export function AboutPanel({
  language,
  deviceId,
  recovery,
  onMintRecovery,
}: {
  language: LanguageInfo | null;
  deviceId: string | null;
  recovery: string | null;
  onMintRecovery: () => void;
}) {
  const { t } = useLang();
  return (
    <div className="scroll-y h-full p-2 text-[11px] leading-relaxed">
      <p className={"mb-1"}>{t("privacyBn")}</p>
      <p className={"mb-2"} style={muted}>
        {t("privacyMore")}
      </p>

      <KV
        rows={[
          [
            t("dictionary"),
            language
              ? `${language.dictionary === "hunspell" ? "bn_BD" : "seed"} · ${language.lexiconSize.toLocaleString()}`
              : "…",
          ],
          [
            t("device"),
            <code key="d" className="text-[9px]">
              {deviceId ? `${deviceId.slice(0, 13)}…` : "…"}
            </code>,
          ],
        ]}
      />

      <button className={"btn mt-2 w-full"} onClick={onMintRecovery}>
        {t("generateRecovery")}
      </button>
      {recovery && (
        <div
          className="mt-2 rounded p-2"
          style={{ background: "var(--warn-bg)", color: "var(--warn-fg)" }}
        >
          <p className="font-mono text-[10px] leading-relaxed">{recovery}</p>
          <p className={"mt-1 text-[10px]"}>{t("recoveryNote")}</p>
        </div>
      )}
    </div>
  );
}
