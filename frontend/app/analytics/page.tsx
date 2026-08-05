"use client";

import { useCallback, useEffect, useState } from "react";

import Nav from "@/components/Nav";
import { bucket, clearAll, allEvents, type Buckets, type Summary } from "@/lib/analytics";
import { useLang, type StringKey } from "@/lib/i18n";

/**
 * Analytics over locally-stored counts.
 *
 * Everything is computed in the browser from IndexedDB. There is no server
 * call on this page and no text anywhere in the store — see the header comment
 * in `lib/analytics.ts`, which explains why that constraint is structural
 * rather than incidental.
 *
 * The chart is hand-rolled SVG. A charting library for fourteen bars would be
 * more bytes than the entire rest of this page.
 */

function StatCard({
  label,
  summary,
  t,
}: {
  label: string;
  summary: Summary;
  t: (k: StringKey) => string;
}) {
  const rows: [string, string | number][] = [
    [t("mWords"), summary.words],
    [t("mChecks"), summary.checks],
    [t("mIssues"), summary.issues],
    [t("mAccepted"), summary.accepted],
    [t("mIgnored"), summary.ignored],
    [
      t("mAcceptRate"),
      summary.accepted + summary.ignored
        ? `${Math.round(summary.acceptRate * 100)}%`
        : "—",
    ],
  ];
  return (
    <article className="card">
      <h3 className="muted mb-1 text-[11px] font-semibold uppercase tracking-wide">
        {label}
      </h3>
      <div className="stat mb-2">{summary.words}</div>
      <table className="tbl">
        <tbody>
          {rows.slice(1).map(([k, v]) => (
            <tr key={k} style={{ cursor: "default" }}>
              <td className="muted">{k}</td>
              <td className="text-right font-medium tabular-nums">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}

function DailyChart({ data, t }: { data: Buckets["daily"]; t: (k: StringKey) => string }) {
  const max = Math.max(1, ...data.map((d) => d.words));
  // A wide viewBox on purpose. The SVG scales to the container width, so the
  // rendered height is width x (H/W); at 640x130 a full-width card rendered a
  // 300px-tall chart for fourteen thin bars. A 1200x150 box keeps it in
  // proportion without needing a fixed pixel height.
  const W = 1200;
  const H = 150;
  const pad = 18;
  const bw = (W - pad * 2) / data.length;

  return (
    <div className="card">
      <h3 className="muted mb-2 text-[11px] font-semibold uppercase tracking-wide">
        {t("last14")} · {t("mWords")}
      </h3>
      {/* preserveAspectRatio + viewBox: the chart scales down inside a narrow
          column instead of forcing the page to scroll sideways. */}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        className="w-full"
        role="img"
        aria-label={`${t("last14")} — ${t("mWords")}`}
      >
        {data.map((d, i) => {
          const h = Math.round((d.words / max) * (H - pad * 2));
          const x = pad + i * bw;
          const y = H - pad - h;
          return (
            <g key={d.day}>
              <title>{`${d.day}: ${d.words} ${t("mWords")}, ${d.issues} ${t("mIssues")}`}</title>
              <rect
                x={x + 2}
                y={h ? y : H - pad - 1}
                width={Math.max(2, bw - 4)}
                height={h || 1}
                rx={2}
                fill="var(--accent)"
                opacity={h ? 0.85 : 0.25}
              />
              <text
                x={x + bw / 2}
                y={H - 5}
                textAnchor="middle"
                fontSize="13"
                fill="var(--text-muted)"
              >
                {d.day.slice(8)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default function AnalyticsPage() {
  const { t } = useLang();
  const [data, setData] = useState<Buckets | null>(null);

  const load = useCallback(async () => {
    setData(bucket(await allEvents()));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onClear = async () => {
    if (!window.confirm(t("clearConfirm"))) return;
    await clearAll();
    await load();
  };

  return (
    <main className="p-2">
      <Nav />

      <div className="page">
        <section className="py-6">
          <h1 className="text-2xl font-bold">{t("analyticsTitle")}</h1>
          <p className="muted mt-1 max-w-2xl text-[13px] leading-relaxed">
            {t("analyticsIntro")}
          </p>
        </section>

        {!data || data.total === 0 ? (
          <div className="card">
            <p className="muted text-[13px]">{t("noData")}</p>
          </div>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <StatCard label={t("today")} summary={data.today} t={t} />
              <StatCard label={t("thisWeek")} summary={data.week} t={t} />
              <StatCard label={t("thisMonth")} summary={data.month} t={t} />
            </div>

            <div className="mt-3">
              <DailyChart data={data.daily} t={t} />
            </div>

            {data.byClass.length > 0 && (
              <div className="card mt-3">
                <h3 className="muted mb-2 text-[11px] font-semibold uppercase tracking-wide">
                  {t("byClass")}
                </h3>
                <div className="scroll-y" style={{ maxHeight: 260 }}>
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>{t("colClass")}</th>
                        <th className="text-right">{t("mAccepted")}</th>
                        <th className="text-right">{t("mIgnored")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.byClass.map((c) => (
                        <tr key={c.errorClass} style={{ cursor: "default" }}>
                          <td>{c.errorClass.replace(/_/g, " ")}</td>
                          <td className="text-right tabular-nums">{c.accepted}</td>
                          <td className="text-right tabular-nums">{c.ignored}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button className="btn" onClick={onClear}>
            {t("clearData")}
          </button>
          <span className="muted text-[11px]">{t("storageNote")}</span>
        </div>
      </div>
    </main>
  );
}
