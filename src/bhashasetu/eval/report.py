"""Terminal rendering of an `EvalReport`, including the regression table."""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table

from bhashasetu.eval.harness import (
    BASELINE_PATH,
    MAX_CLEAN_FALSE_POSITIVE_RATE,
    REQUIRED_GOLD_SENTENCES,
    EvalReport,
    GateResult,
)


def render(report: EvalReport, gate: GateResult, console: Console | None = None) -> None:
    console = console or Console()
    baseline = (
        json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        if BASELINE_PATH.exists()
        else {}
    )
    prev = baseline.get("per_class", {})

    table = Table(title="Per-error-class metrics (F0.5, precision-weighted)")
    table.add_column("Error class")
    table.add_column("Stage", justify="center")
    table.add_column("N", justify="right")
    table.add_column("P", justify="right")
    table.add_column("R", justify="right")
    table.add_column("F0.5", justify="right")
    table.add_column("Δ vs base", justify="right")

    for code, m in report.per_class.items():
        delta = ""
        if code in prev:
            d = (m.f05 - prev[code]["f05"]) * 100
            delta = f"{d:+.1f}" if abs(d) >= 0.05 else "—"
        stage = "1" if m.implemented else "—"
        style = None if m.implemented else "dim"
        table.add_row(
            code,
            stage,
            str(m.support),
            f"{m.precision:.3f}",
            f"{m.recall:.3f}",
            f"{m.f05:.3f}",
            delta,
            style=style,
        )
    console.print(table)

    headline = Table(title="Headline metrics", show_header=False)
    headline.add_column("metric")
    headline.add_column("value", justify="right")
    fp_style = "green" if report.clean_fp_rate <= MAX_CLEAN_FALSE_POSITIVE_RATE else "red"
    headline.add_row(
        "[bold]false positives on clean text[/bold] (spec §8: the number that matters)",
        f"[{fp_style}]{report.clean_fp_rate:.2%}[/{fp_style}] "
        f"({report.clean_false_positives}/{report.clean_sentences})",
    )
    headline.add_row("macro F0.5 (implemented classes only)", f"{report.macro_f05:.3f}")
    headline.add_row("latency p50 / p95 / p99 (ms)",
                     f"{report.percentile(0.50):.1f} / "
                     f"{report.percentile(0.95):.1f} / "
                     f"{report.percentile(0.99):.1f}")
    headline.add_row(
        "gold sentences (verified / total)",
        f"{report.gold_verified} / {report.gold_total} "
        f"(need {REQUIRED_GOLD_SENTENCES} verified)",
    )
    dist = ", ".join(f"stage {s}: {n}" for s, n in sorted(report.stage_distribution.items()))
    headline.add_row("stage-resolution distribution", dist or "—")
    console.print(headline)

    for w in gate.warnings:
        console.print(f"[yellow]WARNING[/yellow]  {w}")
    for b in gate.blockers:
        console.print(f"[red]BLOCKER[/red]  {b}")
    if gate.passed and not gate.warnings:
        console.print("[green]all gates passed[/green]")
