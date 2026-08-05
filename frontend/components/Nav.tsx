"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import Logo from "@/components/Logo";
import { useLang } from "@/lib/i18n";
import { applyTheme, readStoredTheme, THEMES, type ThemeId } from "@/lib/theme";
import { useEffect, useState } from "react";

const LINKS = [
  { href: "/", key: "navHome" },
  { href: "/editor", key: "navEditor" },
  { href: "/analytics", key: "navAnalytics" },
] as const;

/**
 * Shared chrome: brand, page links, language toggle, theme picker.
 *
 * Every label here uses the same font stack and the same font-size in both
 * languages — see `--font-ui` in globals.css, which lists a Bengali face after
 * the Latin one so Bengali glyphs fall through without changing the element's
 * metrics. Swapping `font-family` per language, which this used to do, made the
 * whole interface visibly resize on toggle.
 */
export default function Nav() {
  const { lang, setLang, t } = useLang();
  const pathname = usePathname();
  const [theme, setTheme] = useState<ThemeId>("light");

  useEffect(() => {
    const stored = readStoredTheme();
    setTheme(stored);
    applyTheme(stored);
  }, []);

  return (
    <nav className="nav-bar flex flex-wrap items-center gap-3">
      <Link href="/" className="flex items-center gap-2.5 no-underline">
        <Logo size={34} className="shrink-0" />
        {/* Stacked rather than inline: the mark gives the row its height, and
            the transliteration fills the space beside the name instead of
            hanging off it. */}
        <span className="flex flex-col leading-none">
          <span className="text-[19px] font-bold leading-tight">{t("brand")}</span>
          <span className="text-[11px] leading-tight" style={{ color: "var(--text-muted)" }}>
            {t("brandAlt")}
          </span>
        </span>
      </Link>

      <div className="ml-2 flex items-center gap-1">
        {LINKS.map((l) => {
          const active = pathname === l.href;
          return (
            <Link
              key={l.href}
              href={l.href}
              aria-current={active ? "page" : undefined}
              className="rounded-md px-3 py-1.5 text-[13px] no-underline"
              style={{
                background: active ? "var(--surface-2)" : "transparent",
                color: active ? "var(--text)" : "var(--text-muted)",
                fontWeight: active ? 600 : 400,
              }}
            >
              {t(l.key)}
            </Link>
          );
        })}
      </div>

      <div className="ml-auto flex items-center gap-2">
        {/* Two states, so a button rather than a select: one click to switch,
            and the label names the language you would GET, written in that
            language — "English" reads as English wherever you are. */}
        <button
          className="btn"
          onClick={() => setLang(lang === "bn" ? "en" : "bn")}
          aria-label={t("languageLabel")}
          title={t("languageLabel")}
          lang={lang === "bn" ? "en" : "bn"}
        >
          {lang === "bn" ? "English" : "বাংলা"}
        </button>

        <select
          className="btn"
          value={theme}
          onChange={(e) => {
            const next = e.target.value as ThemeId;
            setTheme(next);
            applyTheme(next);
          }}
          aria-label={t("themeLabel")}
          title={t("themeLabel")}
        >
          {THEMES.map((th) => (
            <option key={th.id} value={th.id}>
              {th.label}
            </option>
          ))}
        </select>
      </div>
    </nav>
  );
}
