/**
 * The BhashaSetu mark.
 *
 * ভাষাসেতু means "language bridge", and the mark is a suspension bridge whose
 * deck doubles as the মাত্রা — the horizontal line Bengali letters hang from.
 * One shape reads as both, which is the whole product in a glyph: the script on
 * top, the bridge underneath.
 *
 * The colours are literals rather than theme variables on purpose. A brand mark
 * that restyles itself across the five themes is not a brand mark, and the tile
 * has to keep its own contrast when it sits on a browser tab we do not control.
 * The green cable is the one deliberate borrowing from the UI palette: it is the
 * same "this is right" green as an accepted suggestion.
 *
 * The gradient id is a module constant, not `useId`. Two instances on one page
 * would collide — but there is one, in the nav, and a constant keeps this a
 * plain function usable from server components.
 */

const GRADIENT_ID = "bs-logo-gradient";

export default function Logo({
  size = 34,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={className}
      role="img"
      aria-label="BhashaSetu"
      focusable="false"
    >
      <defs>
        <linearGradient id={GRADIENT_ID} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#2f6df6" />
          <stop offset="100%" stopColor="#0e8ea8" />
        </linearGradient>
      </defs>

      <rect x="0" y="0" width="32" height="32" rx="8" fill={`url(#${GRADIENT_ID})`} />

      {/* Towers/piers first, so the deck reads as passing in front of them.
          They clear the deck by ~3px and no more: taller, and the mark turns
          into an H with a curve under it. */}
      <rect x="9.7" y="9.2" width="2.3" height="15.3" rx="1.15" fill="#ffffff" opacity="0.92" />
      <rect x="20" y="9.2" width="2.3" height="15.3" rx="1.15" fill="#ffffff" opacity="0.92" />

      {/* The deck — and the মাত্রা. */}
      <rect x="4" y="12.4" width="24" height="2.5" rx="1.25" fill="#ffffff" />

      {/* Hangers, deck down to the cable. Three thin strokes, and the whole
          reason the curve below reads as a suspension cable rather than as a
          smile — which is exactly what it looked like without them. */}
      <path
        d="M13.4 14.9 V17.7 M16 14.9 V18.7 M18.6 14.9 V17.7"
        stroke="#ffffff"
        strokeWidth="0.9"
        strokeLinecap="round"
        opacity="0.8"
      />

      {/* Main cable, sagging between the towers. */}
      <path
        d="M10.9 14.9 Q16 22.5 21.1 14.9"
        fill="none"
        stroke="#34d399"
        strokeWidth="1.9"
        strokeLinecap="round"
      />

      {/* Back-stays out to the abutments. */}
      <path
        d="M4.8 12.6 Q7.9 15.6 10.9 14.9 M27.2 12.6 Q24.1 15.6 21.1 14.9"
        fill="none"
        stroke="#ffffff"
        strokeWidth="1.3"
        strokeLinecap="round"
        opacity="0.55"
      />

      {/* Water. Cropped by the tile's corner radius, which is why it runs edge
          to edge rather than being inset like the deck. */}
      <rect x="0" y="25.6" width="32" height="1.7" rx="0.85" fill="#ffffff" opacity="0.38" />
    </svg>
  );
}
