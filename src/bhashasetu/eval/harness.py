"""Evaluation harness (spec §8).

Reports, per error class: precision, recall, F0.5. F-beta with beta=0.5 weights
precision twice as heavily as recall, which is the correct objective for a
grammar checker - a missed error costs the user nothing they did not already
have, a wrong flag costs them trust.

Separately and more importantly, it reports the **false-positive rate on
known-correct text**. Spec §8 calls this the single most important number in the
project, and it is the one metric that cannot be gamed by tuning thresholds
downward.

A detection counts as a true positive when its span overlaps the gold span AND
its error class matches. Every other surfaced edit on that sentence is charged as
a false positive to whichever class emitted it, so a noisy detector cannot hide
behind a quiet one.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from bhashasetu.core.pipeline import Pipeline, PipelineConfig
from bhashasetu.core.registry import get_pack
from bhashasetu.core.types import Edit, ErrorClass

GOLD_ROOT = Path(__file__).resolve().parents[3] / "eval" / "gold"
BASELINE_PATH = Path(__file__).resolve().parents[3] / "eval" / "baseline.json"

# Spec §8 targets.
REQUIRED_GOLD_SENTENCES = 600
MAX_CLEAN_FALSE_POSITIVE_RATE = 0.03
MAX_F05_REGRESSION = 2.0  # points


@dataclass(frozen=True, slots=True)
class GoldCase:
    """One gold sentence.

    `review` is deliberately three-valued rather than a bool:

        "none"   - nobody has looked at it
        "model"  - authored and cross-checked by the implementing agent
        "human"  - signed off by a Bengali-literate reviewer

    Only "human" counts toward the spec §8 requirement. Collapsing "model" into
    "verified" would let the project claim a quality bar it has not cleared;
    collapsing it into "none" would throw away the reviewer's queue ordering.
    """

    id: str
    text: str
    error_class: ErrorClass | None
    wrong: str | None
    right: str | None
    review: str
    source: str
    note: str | None = None

    @property
    def human_verified(self) -> bool:
        return self.review == "human"

    @property
    def span(self) -> tuple[int, int] | None:
        if not self.wrong:
            return None
        idx = self.text.find(self.wrong)
        return None if idx < 0 else (idx, idx + len(self.wrong))


@dataclass
class ClassMetrics:
    error_class: str
    support: int = 0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    implemented: bool = False

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f05(self) -> float:
        p, r = self.precision, self.recall
        if p == 0 and r == 0:
            return 0.0
        beta2 = 0.25
        return (1 + beta2) * p * r / (beta2 * p + r) if (beta2 * p + r) else 0.0


@dataclass
class EvalReport:
    per_class: dict[str, ClassMetrics] = field(default_factory=dict)
    clean_sentences: int = 0
    clean_false_positives: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    stage_distribution: dict[int, int] = field(default_factory=dict)
    gold_total: int = 0
    gold_verified: int = 0        # human-signed-off only
    gold_model_reviewed: int = 0

    # -- headline numbers ------------------------------------------------
    @property
    def clean_fp_rate(self) -> float:
        return (
            self.clean_false_positives / self.clean_sentences
            if self.clean_sentences
            else 0.0
        )

    @property
    def macro_f05(self) -> float:
        implemented = [m for m in self.per_class.values() if m.implemented]
        return statistics.fmean(m.f05 for m in implemented) if implemented else 0.0

    def percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        k = min(len(ordered) - 1, round(p * (len(ordered) - 1)))
        return ordered[k]

    @property
    def stage4_share(self) -> float:
        total = sum(self.stage_distribution.values())
        return self.stage_distribution.get(4, 0) / total if total else 0.0

    def to_json(self) -> dict[str, Any]:
        return {
            "macro_f05": round(self.macro_f05, 4),
            "clean_fp_rate": round(self.clean_fp_rate, 4),
            "gold_total": self.gold_total,
            "gold_verified": self.gold_verified,
            "gold_model_reviewed": self.gold_model_reviewed,
            "latency_p50": round(self.percentile(0.50), 2),
            "latency_p95": round(self.percentile(0.95), 2),
            "latency_p99": round(self.percentile(0.99), 2),
            "stage_distribution": self.stage_distribution,
            "per_class": {
                k: {
                    **asdict(v),
                    "precision": round(v.precision, 4),
                    "recall": round(v.recall, 4),
                    "f05": round(v.f05, 4),
                }
                for k, v in self.per_class.items()
            },
        }


def load_gold(language: str = "bn") -> tuple[list[GoldCase], list[str]]:
    """Read the gold set.

    Error cases live one file per error class under `errors/`, so a reviewer can
    take a single class end to end and so a merge conflict in one class cannot
    corrupt another.
    """
    root = GOLD_ROOT / language

    files = sorted((root / "errors").glob("*.yaml"))
    if not files and (root / "errors.yaml").exists():
        files = [root / "errors.yaml"]

    seen: set[str] = set()
    cases: list[GoldCase] = []
    for path in files:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for row in raw.get("cases", []):
            case_id = str(row["id"])
            if case_id in seen:
                raise ValueError(f"duplicate gold case id {case_id!r} in {path.name}")
            seen.add(case_id)
            cases.append(
                GoldCase(
                    id=case_id,
                    text=row["text"],
                    error_class=(
                        ErrorClass(row["error_class"]) if row.get("error_class") else None
                    ),
                    wrong=row.get("wrong"),
                    right=row.get("right"),
                    review=str(row.get("review", "none")),
                    source=row.get("source", "unknown"),
                    note=row.get("note"),
                )
            )

    clean_raw = yaml.safe_load((root / "clean.yaml").read_text(encoding="utf-8"))
    clean = list(clean_raw.get("sentences", []))
    return cases, clean


def evaluate(
    language: str = "bn", config: PipelineConfig | None = None
) -> EvalReport:
    pack = get_pack(language)
    pipeline = Pipeline(pack, config)
    cases, clean = load_gold(language)

    report = EvalReport()
    report.gold_total = len(cases)
    report.gold_verified = sum(1 for c in cases if c.human_verified)
    report.gold_model_reviewed = sum(1 for c in cases if c.review == "model")

    implemented = {
        code
        for code, spec in pack.error_classes.items()
        if spec.implemented_at_stage is not None
    }
    for code in ErrorClass:
        report.per_class[code.value] = ClassMetrics(
            error_class=code.value, implemented=code in implemented
        )

    # --- error slices ---------------------------------------------------
    for case in cases:
        t0 = time.perf_counter()
        result = pipeline.check(case.text)
        report.latencies_ms.append((time.perf_counter() - t0) * 1000)
        for stage, n in result.stage_distribution.items():
            report.stage_distribution[stage] = (
                report.stage_distribution.get(stage, 0) + n
            )

        if case.error_class is None:
            continue
        metrics = report.per_class[case.error_class.value]
        metrics.support += 1

        gold_span = case.span
        hit = _matching_edit(result.edits, case.error_class, gold_span)
        if hit is not None:
            metrics.tp += 1
        else:
            metrics.fn += 1

        # Any surfaced edit that is not the expected one is a false positive on
        # this sentence. Counted per class so a noisy detector cannot hide behind
        # a quiet one.
        for edit in result.edits:
            if edit is hit:
                continue
            report.per_class[edit.error_class.value].fp += 1

    # --- clean text: every flag is a false positive ---------------------
    for sentence in clean:
        t0 = time.perf_counter()
        result = pipeline.check(sentence)
        report.latencies_ms.append((time.perf_counter() - t0) * 1000)
        report.clean_sentences += 1
        if result.edits:
            report.clean_false_positives += 1
            for edit in result.edits:
                report.per_class[edit.error_class.value].fp += 1

    return report


def _matching_edit(
    edits: list[Edit], expected: ErrorClass, span: tuple[int, int] | None
) -> Edit | None:
    for edit in edits:
        if edit.error_class is not expected:
            continue
        if span is None:
            return edit
        if edit.start < span[1] and span[0] < edit.end:
            return edit
    return None


# ---------------------------------------------------------------------------
# Regression gate


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    blockers: list[str]
    warnings: list[str]


def check_gates(report: EvalReport, *, allow_provisional: bool) -> GateResult:
    blockers: list[str] = []
    warnings: list[str] = []

    if report.clean_fp_rate > MAX_CLEAN_FALSE_POSITIVE_RATE:
        blockers.append(
            f"clean-text false-positive rate {report.clean_fp_rate:.1%} exceeds the "
            f"{MAX_CLEAN_FALSE_POSITIVE_RATE:.0%} ceiling (spec §8)"
        )

    if report.gold_verified < REQUIRED_GOLD_SENTENCES:
        # Two different shortfalls, and conflating them hides which one is left.
        # "Nobody has checked these" and "these are checked but there are not
        # enough of them" call for completely different work.
        if report.gold_model_reviewed:
            msg = (
                f"{report.gold_model_reviewed} gold cases still await human "
                f"sign-off ({report.gold_verified} verified); spec §8 requires "
                f"{REQUIRED_GOLD_SENTENCES} human-verified"
            )
        else:
            msg = (
                f"all {report.gold_verified} gold cases are human-verified, but "
                f"spec §8 requires {REQUIRED_GOLD_SENTENCES}; "
                f"{REQUIRED_GOLD_SENTENCES - report.gold_verified} more need to be "
                f"authored and reviewed"
            )
        (warnings if allow_provisional else blockers).append(msg)

    if report.gold_total < REQUIRED_GOLD_SENTENCES:
        warnings.append(
            f"gold set holds {report.gold_total} cases; spec §8 wants at least "
            f"{REQUIRED_GOLD_SENTENCES} stratified across the 12 classes"
        )

    if report.stage4_share > 0.25:
        warnings.append(
            f"stage 4 resolves {report.stage4_share:.0%} of edits; spec §1 caps this "
            "at 25% before the earlier stages need retraining"
        )

    if BASELINE_PATH.exists():
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        for code, current in report.per_class.items():
            prev = baseline.get("per_class", {}).get(code)
            if not prev:
                continue
            drop = (prev["f05"] - current.f05) * 100
            if drop > MAX_F05_REGRESSION:
                blockers.append(
                    f"{code}: F0.5 dropped {drop:.1f} points vs baseline "
                    f"({prev['f05']:.3f} -> {current.f05:.3f})"
                )
    else:
        warnings.append("no baseline committed yet; run `make eval-baseline`")

    return GateResult(not blockers, blockers, warnings)


def write_baseline(report: EvalReport) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(report.to_json(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
