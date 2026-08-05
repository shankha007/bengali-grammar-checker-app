import type { Metadata, Viewport } from "next";
import { Inter, Noto_Sans_Bengali } from "next/font/google";

import { LangProvider } from "@/lib/i18n";
import "./globals.css";

/*
 * Both faces are self-hosted by next/font at build time — no runtime request to
 * Google, which matters for a product whose pitch is that nothing about your
 * writing leaves the page.
 *
 * They are exposed as CSS variables rather than applied as classes because
 * globals.css owns the two stacks (--font-ui, --font-bengali) and the ordering
 * inside them is load-bearing; see the comment there.
 *
 * `display: swap` on both: a blocking web font would hide Bengali text behind
 * invisible glyphs, and this is an editor.
 */
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const notoBengali = Noto_Sans_Bengali({
  subsets: ["bengali", "latin"],
  display: "swap",
  variable: "--font-noto-bengali",
});

export const metadata: Metadata = {
  title: "ভাষাসেতু · BhashaSetu",
  description:
    "বাংলা ব্যাকরণ ও বানান সহায়ক — লগইন ছাড়াই, সম্পূর্ণ বিনামূল্যে। " +
    "A Bengali grammar and writing assistant. No login, every feature free.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8fafc" },
    { media: "(prefers-color-scheme: dark)", color: "#020617" },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // `lang` and `data-theme` are BOTH rendered on the server, so the HTML
    // already carries the attributes the inline script may then change. Leaving
    // data-theme off server-side means React hydrates against an element the
    // script has already mutated — the classic source of the "server rendered
    // HTML didn't match the client" warning.
    //
    // `suppressHydrationWarning` is the documented escape hatch for exactly this
    // pattern. It covers this one element and does NOT extend to descendants,
    // so nothing else can quietly hide behind it.
    //
    // lang="bn" is load-bearing beyond hydration: it drives font selection and
    // how a screen reader pronounces the content (spec §10).
    <html
      lang="bn"
      data-theme="light"
      className={`${inter.variable} ${notoBengali.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            // Set the theme before first paint. Inline because any deferred
            // script is already too late — the user would see a flash of the
            // wrong theme on every load.
            __html: `(function(){try{var v=['light','dark','sepia','nord','contrast'];var t=localStorage.getItem('bs-theme');if(!t||v.indexOf(t)<0){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','light');}})();`,
          }}
        />
      </head>
      {/*
        `suppressHydrationWarning` here is about extensions, not about our own
        markup. Grammarly, password managers and reader-mode extensions all
        stamp attributes onto <body> before React hydrates
        (`data-new-gr-c-s-check-loaded`, `cz-shortcut-listen`, …), and React
        reports that as a mismatch the app cannot fix and the user cannot act
        on. It covers this element's own attributes only and does NOT extend to
        descendants, so a real mismatch inside the tree still surfaces.
      */}
      <body suppressHydrationWarning>
        <LangProvider>{children}</LangProvider>
      </body>
    </html>
  );
}
