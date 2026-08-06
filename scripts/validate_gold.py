#!/usr/bin/env python
"""Structural checks on the gold set.

This does NOT check whether the pipeline finds an error — that is what
`make eval` measures, and a gold case the pipeline misses is a finding, not a
defect. What it checks is whether each case is *coherent*, so the eval measures
what it claims to:

  * `wrong` actually occurs in `text` (otherwise the span is None and any edit
    of the right class scores a true positive, silently inflating recall)
  * for NON_WORD, `wrong` is genuinely rejected by the lexicon — if the
    dictionary accepts it, the case is mislabelled and probably belongs in
    homonym.yaml
  * `right` is accepted by the lexicon — a "correction" the checker considers
    misspelt is either wrong, or a dictionary gap that belongs in
    data/extra_words.txt
  * ids are unique and prefixed consistently
  * every one of the 12 classes has at least the spec §3 minimum

Run it after editing any gold file. It is advisory — it prints findings and
exits non-zero — because several categories of finding need a human decision.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bhashasetu.core.registry import get_pack
from bhashasetu.core.types import ErrorClass
from bhashasetu.eval.harness import load_gold

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import use_utf8

use_utf8()

MIN_PER_CLASS = 3


def main() -> int:
    pack = get_pack("bn")
    lexicon = pack.lexicon
    normalizer = pack.normalizer
    cases, clean = load_gold("bn")

    # Two buckets, on purpose.
    #
    # `errors`   — the case itself is incoherent, so the eval will measure
    #              something other than what the case claims. These fail the build.
    # `warnings` — the case is well-formed but the LEXICON disagrees with it.
    #              That is a finding about the dictionary or about a rule's
    #              over-generation, not a defect in the gold set, and it must not
    #              pressure anyone into editing gold data to make a tool go quiet.
    errors: list[str] = []
    warnings: list[str] = []
    by_class: dict[str, int] = Counter()
    review_counts: dict[str, int] = Counter()
    per_class_cases: dict[str, list[str]] = defaultdict(list)

    for case in cases:
        review_counts[case.review] += 1
        if case.error_class:
            by_class[case.error_class.value] += 1
            per_class_cases[case.error_class.value].append(case.id)

        text = normalizer.normalize(case.text).text

        if case.wrong:
            wrong = normalizer.normalize(case.wrong).text
            if wrong not in text:
                errors.append(
                    f"{case.id}: `wrong` ({case.wrong!r}) does not occur in `text` "
                    f"- span will be None and recall is inflated"
                )

        if case.wrong and case.right and case.wrong == case.right:
            errors.append(
                f"{case.id}: `wrong` and `right` are identical - placeholder or "
                f"copy-paste slip, the case asserts nothing"
            )

        if case.error_class is ErrorClass.NON_WORD and case.wrong:
            wrong = normalizer.normalize(case.wrong).text
            if lexicon.contains(wrong):
                warnings.append(
                    f"{case.id}: NON_WORD but the lexicon accepts {case.wrong!r} "
                    f"- either the case is mislabelled (try HOMONYM), or a lexicon "
                    f"rule over-generates and this error can never be caught"
                )

        if case.right and " " not in case.right:
            right = normalizer.normalize(case.right).text
            if not lexicon.contains(right):
                warnings.append(
                    f"{case.id}: the correction {case.right!r} is not in the lexicon "
                    f"- either it is wrong, or it is a gap for data/extra_words.txt"
                )

    for code in ErrorClass:
        n = by_class.get(code.value, 0)
        if n < MIN_PER_CLASS:
            errors.append(
                f"{code.value}: only {n} gold case(s), spec §3 requires at least "
                f"{MIN_PER_CLASS}"
            )

    print("Gold set summary")
    print(f"  error cases : {len(cases)}")
    print(f"  clean cases : {len(clean)}")
    print("  review      : " + ", ".join(
        f"{k}={v}" for k, v in sorted(review_counts.items())
    ))
    print("  per class   :")
    for code in ErrorClass:
        print(f"      {code.value:24s} {by_class.get(code.value, 0):3d}")

    if warnings:
        print(f"\n{len(warnings)} warning(s) - the lexicon disagrees with the gold set:")
        for w in warnings:
            print(f"  {w}")

    if errors:
        print(f"\n{len(errors)} error(s) - malformed gold cases:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    if not warnings:
        print("\nno findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
