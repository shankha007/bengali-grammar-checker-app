"""Generate the editor's Sample button corpus from the gold set.

    python scripts/generate_samples.py        # rewrite frontend/lib/samples.ts
    python scripts/generate_samples.py --check # fail if it is out of date

WHY GENERATED, AND WHY FROM THE GOLD SET

The button needs ~100 sentences containing real mistakes. Hand-writing those
into a TypeScript file would mean 100 pieces of unreviewed Bengali living where
nobody looks at them, drifting away from what the checker actually detects.

The gold set already holds reviewed error cases with a known wrong span and a
known correction. Sampling from it means every sentence the button offers is one
a reviewer has seen, and it stays in step with the taxonomy: add gold cases for
a class and the demo starts showing them.

Each candidate is run through the pipeline and kept only if it still produces at
least one visible edit. A demo sentence that comes back clean makes the product
look broken, whichever of the two is at fault - and if a case that used to flag
stops flagging, regenerating this file is how you find out.

Selection is round-robin across error classes rather than first-N, so the button
does not serve twelve ণত্ব errors in a row.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "eval" / "gold" / "bn" / "errors"
OUT = ROOT / "frontend" / "lib" / "samples.ts"
TARGET = 100

HEADER = """\
/**
 * Sample sentences for the editor's নমুনা / Sample button.
 *
 * GENERATED FILE - do not edit by hand.
 *     python scripts/generate_samples.py
 *
 * Every sentence comes from eval/gold/bn/errors/, so each one contains a real
 * mistake that a reviewer has looked at, and each was verified to still produce
 * at least one edit when this file was written. Sentences are interleaved
 * across error classes so repeated clicks show variety rather than twelve
 * spelling errors in a row.
 *
 * Regenerate after changing the gold set or the detectors; `make samples-check`
 * fails the build when this file has drifted.
 */

export const SAMPLES: readonly string[] = [
"""

FOOTER = """] as const;

/**
 * A sample that is not the one currently shown.
 *
 * Random with a repeat guard, not a cycle: two clicks in a row returning the
 * same sentence reads as a broken button, which is the only property of the
 * randomness a user can actually perceive.
 */
export function pickSample(current?: string): string {
  const pool = SAMPLES.filter((s) => s !== current);
  const from = pool.length ? pool : SAMPLES;
  return from[Math.floor(Math.random() * from.length)];
}
"""


def load_cases() -> dict[str, list[str]]:
    by_class: dict[str, list[str]] = {}
    for path in sorted(GOLD.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for case in doc.get("cases", []):
            text = (case.get("text") or "").strip()
            if text:
                by_class.setdefault(case.get("error_class", "?"), []).append(text)
    return by_class


def flagged(texts: list[str]) -> list[str]:
    """Keep only sentences the checker still says something about."""
    sys.path.insert(0, str(ROOT / "src"))
    from bhashasetu.core.pipeline import Pipeline
    from bhashasetu.core.registry import get_pack

    pipe = Pipeline(get_pack("bn"))
    return [t for t in texts if pipe.check(t).edits]


def select() -> list[str]:
    by_class = load_cases()
    for klass, texts in by_class.items():
        by_class[klass] = flagged(texts)

    # Round-robin, longest pools last so a thin class is not crowded out.
    order = sorted(by_class, key=lambda k: len(by_class[k]))
    chosen: list[str] = []
    depth = 0
    while len(chosen) < TARGET:
        added = False
        for klass in order:
            pool = by_class[klass]
            if depth < len(pool):
                chosen.append(pool[depth])
                added = True
                if len(chosen) == TARGET:
                    break
        if not added:
            break  # every pool exhausted
        depth += 1
    return chosen


def render(samples: list[str]) -> str:
    body = "".join(f'  {escape(s)},\n' for s in samples)
    return HEADER + body + FOOTER


def escape(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the generated file is out of date",
    )
    args = parser.parse_args()

    samples = select()
    rendered = render(samples)

    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != rendered:
            print(
                f"{OUT.relative_to(ROOT)} is out of date - "
                "run `python scripts/generate_samples.py`",
                file=sys.stderr,
            )
            return 1
        print(f"samples up to date ({len(samples)} sentences)")
        return 0

    OUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(samples)} sentences")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
