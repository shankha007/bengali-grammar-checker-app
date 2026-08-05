"use client";

import Link from "next/link";

import HeroArt from "@/components/HeroArt";
import Nav from "@/components/Nav";
import { useLang, type StringKey } from "@/lib/i18n";
import { CATEGORY_VAR } from "@/lib/types";

/**
 * Landing page.
 *
 * Only shipped capabilities appear here, and each gets a worked example rather
 * than an adjective — the examples are real strings the running checker
 * produces, so the page cannot drift away from the product without someone
 * noticing.
 *
 * The counter-examples (`untouched`) are load-bearing, not padding: what a
 * grammar checker declines to flag is as much a claim about its quality as what
 * it catches, and ঠান্ডা / ভাসা / Ph.D. are exactly the cases a careless
 * implementation gets wrong.
 */

interface Feature {
  title: StringKey;
  body: StringKey;
  detail: StringKey;
  color: string;
  before?: string;
  after?: string;
  untouched?: string;
}

const FEATURES: Feature[] = [
  {
    title: "f1Title",
    body: "f1Body",
    detail: "f1Detail",
    color: CATEGORY_VAR.orthography,
    before: "এর কারন কী",
    after: "এর কারণ কী",
    untouched: "ঠান্ডা · ভাসা",
  },
  {
    title: "f2Title",
    body: "f2Body",
    detail: "f2Detail",
    color: CATEGORY_VAR.register,
    before: "সে তাহার বইটা পড়ছে",
    after: "সে তার বইটা পড়ছে",
    untouched: "সে তাহার পুস্তক পাঠ করিতেছে",
  },
  {
    title: "f3Title",
    body: "f3Body",
    detail: "f3Detail",
    color: CATEGORY_VAR.morphology,
    before: "একজন বিখ্যত লেখক",
    after: "একজন বিখ্যাত লেখক",
    untouched: "বইগুলোকেও",
  },
  {
    title: "f4Title",
    body: "f4Body",
    detail: "f4Detail",
    color: "var(--unsupported)",
    before: "He also writes in English.",
  },
  {
    title: "f5Title",
    body: "f5Body",
    detail: "f5Detail",
    color: CATEGORY_VAR.punctuation,
    before: "আমি বাড়ি যাচ্ছি ।",
    after: "আমি বাড়ি যাচ্ছি।",
    untouched: "Ph.D. · ১০.৩০ · example.com",
  },
  {
    title: "f6Title",
    body: "f6Body",
    detail: "f6Detail",
    color: CATEGORY_VAR.syntax,
  },
  { title: "f7Title", body: "f7Body", detail: "f7Detail", color: "var(--ok)" },
  { title: "f8Title", body: "f8Body", detail: "f8Detail", color: "var(--accent)" },
];

function Example({ feature }: { feature: Feature }) {
  const { t } = useLang();
  if (!feature.before && !feature.untouched) return null;

  return (
    <div
      className="mt-3 rounded-lg border p-3 text-[13px]"
      style={{ borderColor: "var(--border)", background: "var(--surface-2)" }}
    >
      {feature.before && (
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="muted w-24 shrink-0 text-[11px]">{t("exBefore")}</span>
          <span
            style={
              feature.after
                ? {
                    textDecoration: "underline wavy",
                    textDecorationColor: feature.color,
                    textUnderlineOffset: "0.3em",
                  }
                : {
                    background: "var(--unsupported-fill)",
                    borderBottom: "2px dotted var(--unsupported)",
                    padding: "0 2px",
                  }
            }
          >
            {feature.before}
          </span>
        </div>
      )}
      {feature.after && (
        <div className="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="muted w-24 shrink-0 text-[11px]">{t("exAfter")}</span>
          <span className="font-semibold" style={{ color: "var(--ok)" }}>
            {feature.after}
          </span>
        </div>
      )}
      {feature.untouched && (
        <div className="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="muted w-24 shrink-0 text-[11px]">{t("exUntouched")}</span>
          <span className="muted">{feature.untouched}</span>
        </div>
      )}
    </div>
  );
}

export default function LandingPage() {
  const { t } = useLang();

  return (
    <main className="p-2">
      <Nav />

      <div className="page">
        {/* Hero: copy left, product illustration right. Stacks below lg so the
            artwork never squeezes the headline into four words a line. */}
        <section className="grid items-center gap-8 py-10 lg:grid-cols-[1.05fr_1fr] lg:py-16">
          <div>
            <h1 className="text-3xl font-bold leading-tight sm:text-[2.6rem] sm:leading-[1.15]">
              {t("heroTitle")}
            </h1>
            <p className="muted mt-4 max-w-xl text-sm leading-relaxed sm:text-base">
              {t("heroSub")}
            </p>

            <ul className="mt-5 flex flex-wrap gap-2">
              {(["heroPill1", "heroPill2", "heroPill3"] as StringKey[]).map((k) => (
                <li
                  key={k}
                  className="rounded-full border px-3 py-1 text-[12px]"
                  style={{
                    borderColor: "var(--border)",
                    background: "var(--surface)",
                  }}
                >
                  {t(k)}
                </li>
              ))}
            </ul>

            <div className="mt-6 flex flex-wrap gap-2">
              <Link
                href="/editor"
                className="btn btn-primary no-underline"
                style={{ padding: "9px 18px", fontSize: 14 }}
              >
                {t("ctaStart")} →
              </Link>
              <Link
                href="/analytics"
                className="btn no-underline"
                style={{ padding: "9px 18px", fontSize: 14 }}
              >
                {t("ctaAnalytics")}
              </Link>
            </div>
          </div>

          <div className="min-w-0">
            <HeroArt />
          </div>
        </section>

        <section className="pb-6">
          <h2 className="text-xl font-semibold">{t("featuresTitle")}</h2>
          <p className="muted mt-1 text-[13px]">{t("featuresLede")}</p>

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {FEATURES.map((f) => (
              <article key={f.title} className="card flex flex-col">
                <div className="mb-2 flex items-center gap-2">
                  <span
                    aria-hidden
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: f.color }}
                  />
                  <h3 className="text-[15px] font-semibold">{t(f.title)}</h3>
                </div>
                <p className="text-[13px] leading-relaxed">{t(f.body)}</p>
                <p className="muted mt-2 text-[13px] leading-relaxed">
                  {t(f.detail)}
                </p>
                <Example feature={f} />
              </article>
            ))}
          </div>
        </section>

        <section className="pb-12">
          <div className="card flex flex-wrap items-center gap-4">
            <p className="text-[13px] leading-relaxed">{t("privacyBn")}</p>
            <Link
              href="/editor"
              className="btn btn-primary ml-auto no-underline"
              style={{ padding: "8px 16px", fontSize: 14 }}
            >
              {t("ctaStart")} →
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
