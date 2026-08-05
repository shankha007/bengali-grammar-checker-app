import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        bengali: ["var(--font-bengali)"],
        bengaliSerif: ["var(--font-bengali-serif)"],
      },
      colors: {
        // One hue per error CATEGORY, not per class. Twelve distinguishable
        // underline colours is not a thing a reader can learn; five is.
        cat: {
          orthography: "#dc2626",
          morphology: "#d97706",
          syntax: "#7c3aed",
          register: "#0891b2",
          punctuation: "#65a30d",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
