"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { STRINGS, type Lang, type StringKey } from "./strings";

export type { Lang, StringKey };

export const LANG_STORAGE_KEY = "bs-lang";

interface LangContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: StringKey) => string;
}

const LangContext = createContext<LangContextValue>({
  lang: "bn",
  setLang: () => {},
  t: (k) => STRINGS[k].bn,
});

export function LangProvider({ children }: { children: React.ReactNode }) {
  // Always "bn" for the first render, server and client alike. Reading
  // localStorage during render would make the two disagree and produce exactly
  // the hydration mismatch this app used to report.
  const [lang, setLangState] = useState<Lang>("bn");

  useEffect(() => {
    try {
      const stored = localStorage.getItem(LANG_STORAGE_KEY);
      if (stored === "en" || stored === "bn") setLangState(stored);
    } catch {
      /* private mode */
    }
  }, []);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem(LANG_STORAGE_KEY, next);
    } catch {
      /* private mode */
    }
  }, []);

  // One effect owns the `lang` attribute rather than the setter, because the
  // restore-from-storage path above sets state directly. A setter-side
  // assignment left <html lang="bn"> while the chrome rendered in English — a
  // screen reader would announce English labels in a Bengali voice, and only
  // after a reload.
  //
  // The editor keeps its own lang="bn" throughout: its content is Bengali
  // whichever language the buttons are in.
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo<LangContextValue>(
    () => ({ lang, setLang, t: (key) => STRINGS[key][lang] }),
    [lang, setLang],
  );

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export const useLang = () => useContext(LangContext);
