"use client";

/**
 * Hero artwork.
 *
 * Drawn rather than photographed, for three reasons that all matter here:
 * a stock photo would need a licence and a download, it would be a raster that
 * softens on a 2x display, and — the real one — no photograph shows what this
 * product actually does. This is the product: Bengali prose with a wavy
 * category-coloured underline under the error, a flat yellow highlight over the
 * English it will not judge, and the suggestion card that explains why.
 *
 * Every colour is a CSS variable, so the illustration follows all five themes
 * instead of being a light-mode rectangle sitting in a dark page.
 */

/** A hand-built wave path — the same motif as the editor's `text-decoration: wavy`. */
function wave(x: number, y: number, width: number, amp = 2.2, step = 6) {
  let d = `M ${x} ${y}`;
  for (let i = 0; i < width; i += step) {
    d += ` q ${step / 2} ${-amp} ${step} 0`;
    d += ` q ${step / 2} ${amp} ${step} 0`;
    i += step;
  }
  return d;
}

export default function HeroArt() {
  return (
    <svg
      viewBox="0 0 640 430"
      className="h-auto w-full"
      role="img"
      aria-label="বাংলা লেখায় ভুল চিহ্নিত করার নমুনা — a sample of Bengali text with corrections marked"
    >
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.16" />
          <stop offset="55%" stopColor="var(--cat-register)" stopOpacity="0.10" />
          <stop offset="100%" stopColor="var(--cat-syntax)" stopOpacity="0.14" />
        </linearGradient>
        <filter id="card-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow
            dx="0"
            dy="6"
            stdDeviation="10"
            floodColor="#000"
            floodOpacity="0.13"
          />
        </filter>
      </defs>

      {/* Backdrop */}
      <rect x="0" y="0" width="640" height="430" rx="20" fill="url(#bg)" />

      {/* মাত্রা motif: the headstroke that runs along the top of Bengali words,
          used here as the page's own decorative rule. */}
      <g stroke="var(--text)" strokeOpacity="0.12" strokeWidth="2">
        <line x1="40" y1="42" x2="240" y2="42" />
        <line x1="256" y1="42" x2="330" y2="42" />
        <line x1="346" y1="42" x2="470" y2="42" />
      </g>

      {/* The document */}
      <g filter="url(#card-shadow)">
        <rect
          x="40"
          y="70"
          width="470"
          height="250"
          rx="14"
          fill="var(--surface)"
          stroke="var(--border)"
        />
      </g>

      <g fontFamily="var(--font-bengali)" fill="var(--text)">
        <text x="68" y="126" fontSize="19">
          সে তাহার বইটা পড়ছে।
        </text>
        <text x="68" y="176" fontSize="19">
          এর কারন কী কেউ জানে না।
        </text>
        <text x="68" y="226" fontSize="19">
          তিনি একজন বিখ্যত লেখক।
        </text>
      </g>

      {/* Out-of-scope: flat fill, no underline. The visual grammar is the point —
          highlight means "not read", underline means "looks wrong". */}
      <rect
        x="66"
        y="256"
        width="243"
        height="26"
        rx="3"
        fill="var(--unsupported-fill)"
      />
      <line
        x1="66"
        y1="282"
        x2="309"
        y2="282"
        stroke="var(--unsupported)"
        strokeWidth="2"
        strokeDasharray="3 3"
      />
      <text x="70" y="276" fontSize="17" fill="var(--text)">
        He also writes in English.
      </text>

      {/* Wavy underlines, coloured by error category */}
      <path
        d={wave(103, 136, 54)}
        fill="none"
        stroke="var(--cat-register)"
        strokeWidth="2"
      />
      <path
        d={wave(97, 186, 48)}
        fill="none"
        stroke="var(--cat-orthography)"
        strokeWidth="2"
      />
      <path
        d={wave(205, 236, 58)}
        fill="none"
        stroke="var(--cat-orthography)"
        strokeWidth="2"
      />

      {/* The suggestion card — the part that makes this product itself: not just
          a flag, but the correction, the rule, and why. */}
      <g filter="url(#card-shadow)">
        <rect
          x="330"
          y="196"
          width="272"
          height="152"
          rx="12"
          fill="var(--surface)"
          stroke="var(--border)"
        />
      </g>
      <circle cx="350" cy="220" r="4.5" fill="var(--cat-orthography)" />
      <text
        x="364"
        y="225"
        fontSize="11"
        letterSpacing="0.6"
        fill="var(--text-muted)"
        fontFamily="var(--font-ui)"
      >
        NOTVA SHOTVA
      </text>
      <text
        x="576"
        y="225"
        fontSize="11"
        textAnchor="end"
        fill="var(--text-muted)"
        fontFamily="var(--font-ui)"
      >
        93%
      </text>

      <g fontFamily="var(--font-bengali)">
        <text
          x="350"
          y="262"
          fontSize="21"
          fill="var(--text-muted)"
          textDecoration="line-through"
        >
          কারন
        </text>
        <text x="415" y="262" fontSize="19" fill="var(--text-muted)">
          →
        </text>
        <text x="440" y="262" fontSize="21" fontWeight="700" fill="var(--ok)">
          কারণ
        </text>
        <text x="350" y="292" fontSize="13" fill="var(--text)">
          তৎসম শব্দে ণ হবে।
        </text>
        <text x="350" y="314" fontSize="12" fill="var(--text-muted)">
          বিধান: ণত্ব-বিধান §2
        </text>
      </g>

      <rect
        x="350"
        y="322"
        width="54"
        height="18"
        rx="5"
        fill="var(--ok)"
        opacity="0.92"
      />
      <text
        x="377"
        y="335"
        fontSize="11"
        textAnchor="middle"
        fill="#fff"
        fontFamily="var(--font-bengali)"
      >
        কারণ
      </text>

      {/* Category legend — five hues, the same five the editor uses. */}
      <g>
        {[
          "var(--cat-orthography)",
          "var(--cat-morphology)",
          "var(--cat-syntax)",
          "var(--cat-register)",
          "var(--cat-punctuation)",
        ].map((c, i) => (
          <circle key={c} cx={48 + i * 18} cy={368} r="5" fill={c} />
        ))}
        <rect x={131} y={363} width="10" height="10" rx="2" fill="var(--unsupported)" />
      </g>
    </svg>
  );
}
