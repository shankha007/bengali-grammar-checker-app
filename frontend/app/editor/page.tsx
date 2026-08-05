"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import DetailPane from "@/components/DetailPane";
import Editor from "@/components/Editor";
import {
  AboutPanel,
  PipelinePanel,
  ReadabilityPanel,
  TaxonomyPanel,
} from "@/components/Panels";
import Nav from "@/components/Nav";
import { ResizeHandle } from "@/components/Resizable";
import SuggestionTable from "@/components/SuggestionTable";
import * as analytics from "@/lib/analytics";
import * as api from "@/lib/api";
import { useLang, type StringKey } from "@/lib/i18n";
import { LIMITS, useLayout } from "@/lib/layout";
import { pickSample } from "@/lib/samples";
import type {
  CheckResponse,
  Edit,
  ErrorClassInfo,
  LanguageInfo,
} from "@/lib/types";

const DEBOUNCE_MS = 600; // spec §6.1

type Tab = "readability" | "classes" | "pipeline" | "about";

const TABS: { id: Tab; key: StringKey }[] = [
  { id: "readability", key: "tabRead" },
  { id: "classes", key: "tabTypes" },
  { id: "pipeline", key: "tabStages" },
  { id: "about", key: "tabInfo" },
];

export default function Page() {
  const { t } = useLang();
  const { layout, update, reset } = useLayout();

  const [text, setText] = useState("");
  const [result, setResult] = useState<CheckResponse | null>(null);
  const [classes, setClasses] = useState<ErrorClassInfo[]>([]);
  const [language, setLanguage] = useState<LanguageInfo | null>(null);
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [recovery, setRecovery] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [minConfidence, setMinConfidence] = useState(0.55);
  const [showSuppressed, setShowSuppressed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("readability");

  const applyRef = useRef<(edit: Edit, replacement: string) => void>(() => {});
  const setTextRef = useRef<(t: string) => void>(() => {});
  const abortRef = useRef<AbortController | null>(null);

  // The scroll lock is scoped to this page: the landing and analytics pages are
  // ordinary documents and must scroll normally.
  useEffect(() => {
    document.documentElement.classList.add("app-fixed");
    return () => document.documentElement.classList.remove("app-fixed");
  }, []);

  useEffect(() => {
    api.getClasses().then(setClasses).catch(() => {});
    api.getLanguages().then((l) => setLanguage(l[0] ?? null)).catch(() => {});
    api
      .getIdentity()
      .then((i) => {
        setDeviceId(i.deviceId);
        // Spec §5: the id lives in BOTH localStorage and an httpOnly cookie, so
        // clearing either alone does not end the user's history.
        try {
          localStorage.setItem("bs-device", i.deviceId);
        } catch {
          /* private mode; the cookie still carries it */
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!text.trim()) {
      setResult(null);
      setError(null);
      return;
    }
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);
      try {
        const res = await api.check(text, {
          minConfidence,
          includeSuppressed: showSuppressed,
          signal: controller.signal,
        });
        setResult(res);
        setError(null);
        // Counts only. `lib/analytics.ts` has no field that could hold text,
        // and that is deliberate — this lives in the user's own browser.
        void analytics.record({
          type: "check",
          words: text.trim() ? text.trim().split(/\s+/).length : 0,
          sentences: res.sentences.length,
          issues: res.edits.length,
          outOfScope: res.outOfScope.length,
        });
      } catch (e) {
        if ((e as Error).name !== "AbortError") setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text, minConfidence, showSuppressed]);

  const visibleEdits = useMemo(() => {
    const base = result
      ? [...result.edits, ...(showSuppressed ? result.suppressed : [])]
      : [];
    return base.filter((e) => !dismissed.has(e.id)).sort((a, b) => a.start - b.start);
  }, [result, showSuppressed, dismissed]);

  const outOfScope = result?.outOfScope ?? [];

  const countsByClass = useMemo(() => {
    const out: Record<string, number> = {};
    for (const e of visibleEdits) out[e.errorClass] = (out[e.errorClass] ?? 0) + 1;
    return out;
  }, [visibleEdits]);

  const selected = visibleEdits.find((e) => e.id === selectedId) ?? null;

  const accept = useCallback((edit: Edit, replacement: string) => {
    applyRef.current(edit, replacement);
    setDismissed((d) => new Set(d).add(edit.id));
    setSelectedId(null);
    void analytics.record({ type: "accept", errorClass: edit.errorClass });
  }, []);

  const ignore = useCallback((edit: Edit) => {
    setDismissed((d) => new Set(d).add(edit.id));
    void analytics.record({ type: "ignore", errorClass: edit.errorClass });
  }, []);

  const acceptAllOfType = useCallback(
    (errorClass: string) => {
      // Back-to-front: each replacement shifts the offsets of everything after
      // it, and all edits carry offsets from one shared snapshot.
      const batch = visibleEdits
        .filter((e) => e.errorClass === errorClass && e.suggestions.length)
        .sort((a, b) => b.start - a.start);
      for (const e of batch) {
        applyRef.current(e, e.suggestions[0]);
        void analytics.record({ type: "accept", errorClass: e.errorClass });
      }
      setDismissed((d) => {
        const next = new Set(d);
        batch.forEach((e) => next.add(e.id));
        return next;
      });
      setSelectedId(null);
    },
    [visibleEdits],
  );

  const stats = useMemo(
    () => ({
      words: text.trim() ? text.trim().split(/\s+/).length : 0,
      sentences: result?.sentences.length ?? 0,
    }),
    [text, result],
  );

  return (
    // lg:h-screen pairs with the overflow lock in globals.css: on desktop the
    // page never scrolls and each pane scrolls internally, so editor, table and
    // side panel stay visible however long the document gets. Below lg the
    // columns stack and the page scrolls normally.
    <main className="flex min-h-screen flex-col gap-2 p-2 lg:h-screen lg:min-h-0">
      <Nav />

      <div className="flex flex-wrap items-center gap-2">
        <span
          className="rounded px-2 py-0.5 text-[11px] tabular-nums"
          style={{
            background: busy ? "var(--surface-2)" : "transparent",
            color: "var(--text-muted)",
          }}
          role="status"
          aria-live="polite"
        >
          {busy
            ? t("checking")
            : `${stats.words} ${t("words")} · ${stats.sentences} ${t("sentences")} · ${visibleEdits.length} ${t("issues")}`}
        </span>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1 text-[11px]">
            <input
              type="checkbox"
              checked={showSuppressed}
              onChange={(e) => setShowSuppressed(e.target.checked)}
            />
            {t("lowConfidence")}
          </label>
          <label
            className="flex items-center gap-1 text-[11px]"
            title={t("thresholdTitle")}
          >
            <input
              type="range"
              min={0}
              max={0.95}
              step={0.05}
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
              className="w-20"
            />
            <span className="tabular-nums">{minConfidence.toFixed(2)}</span>
          </label>

          {/* A different sentence each click, drawn from the gold set — see
              lib/samples.ts. One fixed sample taught you what the checker does
              once; a hundred show the range of it, and clicking twice on the
              same string reads as a broken button. */}
          <button
            className="btn"
            title={t("sampleTitle")}
            onClick={() => setTextRef.current(pickSample(text))}
          >
            {t("sample")}
          </button>
          <button
            className="btn"
            title={t("bijoyTitle")}
            onClick={async () => {
              try {
                const res = await api.convertBijoy(text);
                if (res.converted) setTextRef.current(res.text);
                else
                  setError(
                    res.detected
                      ? (res.note ?? "Detected as Bijoy but could not convert.")
                      : "This does not look like Bijoy/ANSI text.",
                  );
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            {t("bijoy")}
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded px-2 py-1 text-[11px]"
          style={{ background: "var(--warn-bg)", color: "var(--warn-fg)" }}
        >
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">
            {t("dismiss")}
          </button>
        </div>
      )}

      {/* Column widths come from state, so the two vertical handles below are
          the only thing that sets them. Handles are grid items rather than
          overlays — an overlaid handle drifts out of alignment the moment a
          pane's content changes its intrinsic width. */}
      <div
        className="grid min-h-0 flex-1 grid-cols-1 gap-2 lg:grid-cols-[minmax(0,1fr)_6px_var(--col-mid)_6px_var(--col-side)] lg:gap-0"
        style={
          {
            "--col-mid": `${layout.mid}px`,
            "--col-side": `${layout.side}px`,
          } as React.CSSProperties
        }
        data-testid="app-grid"
      >
        {/* Below lg the panes stack and the page scrolls, so only the editor
            keeps a viewport-relative height — it is a writing surface, and a
            predictable chunk of screen is what you want from one. The panes
            below it size to their content instead; see the middle column. */}
        <section className="panel min-h-0 overflow-hidden max-lg:h-[45vh]">
          <Editor
            edits={visibleEdits}
            outOfScope={outOfScope}
            activeId={selectedId}
            onTextChange={setText}
            onFlagClick={setSelectedId}
            registerApply={(fn) => (applyRef.current = fn)}
            registerSetText={(fn) => (setTextRef.current = fn)}
          />
        </section>

        <ResizeHandle
          orientation="vertical"
          value={layout.mid}
          limits={LIMITS.mid}
          invert
          label={t("resizeColumns")}
          className="max-lg:hidden"
          onChange={(v) => update("mid", v)}
          onReset={() => reset("mid")}
        />

        {/* The three-row grid is desktop-only. It used to apply at every width,
            which meant a phone got `1fr / 6px / var(--row-detail)` inside a
            60vh box with --row-detail still holding a desktop pixel value — so
            the detail pane was handed less height than one wrapped line needs
            and `overflow-hidden` cut the explanation off mid-sentence. Below lg
            the two panes simply stack. */}
        <section
          className="min-h-0 max-lg:flex max-lg:flex-col max-lg:gap-2 lg:grid lg:grid-rows-[minmax(0,1fr)_6px_var(--row-detail)] lg:gap-0"
          style={{ "--row-detail": `${layout.detail}px` } as React.CSSProperties}
        >
          {/* Capped, not fixed: the table shrinks to however many suggestions
              there are and scrolls internally past the cap, so a short list
              does not strand the explanation below a screen of white. */}
          <div className="panel min-h-0 overflow-hidden max-lg:h-auto">
            <SuggestionTable
              edits={visibleEdits}
              outOfScope={outOfScope}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onAccept={accept}
              onReject={ignore}
            />
          </div>

          <ResizeHandle
            orientation="horizontal"
            value={layout.detail}
            limits={LIMITS.detail}
            invert
            label={t("resizeRows")}
            className="max-lg:hidden"
            onChange={(v) => update("detail", v)}
            onReset={() => reset("detail")}
          />

          {/* Content height on mobile. This is the pane that answers "why was
              this flagged", and clipping the answer defeats the product. */}
          <div className="panel min-h-0 overflow-hidden max-lg:h-auto max-lg:overflow-visible">
            <DetailPane
              edit={selected}
              onAccept={(s) => selected && accept(selected, s)}
              onAcceptAllOfType={() =>
                selected && acceptAllOfType(selected.errorClass)
              }
              sameTypeCount={selected ? (countsByClass[selected.errorClass] ?? 0) : 0}
            />
          </div>
        </section>

        <ResizeHandle
          orientation="vertical"
          value={layout.side}
          limits={LIMITS.side}
          invert
          label={t("resizeColumns")}
          className="max-lg:hidden"
          onChange={(v) => update("side", v)}
          onReset={() => reset("side")}
        />

        {/* Readability and the reference tabs. Content height on mobile: a
            fixed 45vh left a tall empty box under short tab content and a
            scrollbar inside a page that already scrolls. */}
        <aside className="panel flex min-h-0 flex-col overflow-hidden max-lg:h-auto">
          <div
            role="tablist"
            className="flex shrink-0 border-b"
            style={{ borderColor: "var(--border)" }}
          >
            {TABS.map((tb) => (
              <button
                key={tb.id}
                role="tab"
                aria-selected={tab === tb.id}
                onClick={() => setTab(tb.id)}
                className="flex-1 px-1 py-1.5 text-[11px]"
                style={{
                  background: tab === tb.id ? "var(--surface-2)" : "transparent",
                  color: tab === tb.id ? "var(--text)" : "var(--text-muted)",
                  fontWeight: tab === tb.id ? 600 : 400,
                }}
              >
                {t(tb.key)}
              </button>
            ))}
          </div>
          {/* `overflow-hidden` is desktop's business: there the pane has a
              fixed height and each panel scrolls inside it. With an auto height
              on mobile it would clip whatever did not fit rather than letting
              the page scroll to it. */}
          <div className="min-h-0 flex-1 overflow-hidden max-lg:overflow-visible">
            {tab === "readability" && <ReadabilityPanel result={result} />}
            {tab === "classes" && (
              <TaxonomyPanel classes={classes} counts={countsByClass} />
            )}
            {tab === "pipeline" && <PipelinePanel result={result} />}
            {tab === "about" && (
              <AboutPanel
                language={language}
                deviceId={deviceId}
                recovery={recovery}
                onMintRecovery={() =>
                  api.mintRecovery().then((r) => setRecovery(r.phrase))
                }
              />
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
