"""BhashaSetu CLI - the Phase 1 deliverable.

    bhashasetu check "আমি বাংলা ভাসায় কথা বলি।"
    bhashasetu check --json --show-suppressed FILE.txt
    bhashasetu eval
    bhashasetu identity new
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from bhashasetu.core.pipeline import Pipeline, PipelineConfig
from bhashasetu.core.registry import available, get_pack
from bhashasetu.core.types import CheckResult, Edit

app = typer.Typer(
    add_completion=False,
    help="BhashaSetu - Bengali grammar and writing assistant (Phase 1).",
)
identity_app = typer.Typer(help="Anonymous identity utilities (spec §5).")
app.add_typer(identity_app, name="identity")


def _utf8_streams() -> None:
    """Force UTF-8 on stdout/stderr.

    On Windows these default to the system ANSI codepage — cp1252 on an English
    install — which cannot encode a single Bengali letter. Every command here
    prints Bengali, so `bhashasetu check "এর কারন কী?"`, the first command in
    the README, died with a UnicodeEncodeError traceback rather than printing a
    table. `bhashasetu eval` died on the Δ in a column header before it got as
    far as the Bengali.

    Rich picks up the stream's encoding when the Console is constructed, so this
    has to run first. `errors="replace"` keeps a console that genuinely cannot
    render the script printing boxes instead of losing the whole report.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


_utf8_streams()
console = Console()


def _read_input(text_or_path: str) -> str:
    if text_or_path == "-":
        return sys.stdin.read()
    p = Path(text_or_path)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    return text_or_path


@app.command()
def check(
    text: Annotated[str, typer.Argument(help="Text, a file path, or - for stdin")],
    language: Annotated[str, typer.Option("--language", "-l")] = "bn",
    as_json: Annotated[bool, typer.Option("--json")] = False,
    show_suppressed: Annotated[
        bool,
        typer.Option(
            "--show-suppressed",
            help="Also print edits below the confidence gate. With the seed "
            "lexicon most NON_WORD flags land here.",
        ),
    ] = False,
    min_confidence: Annotated[float, typer.Option("--min-confidence")] = 0.55,
) -> None:
    """Run the pipeline and print structured Edit objects."""
    body = _read_input(text)
    pack = get_pack(language)
    pipeline = Pipeline(pack, PipelineConfig(min_confidence=min_confidence))
    result = pipeline.check(body)

    if as_json:
        payload = result.to_json()
        if show_suppressed:
            payload["suppressed"] = [e.to_json() for e in result.suppressed]
        console.print_json(json.dumps(payload, ensure_ascii=False))
        raise typer.Exit(0)

    _render(result, show_suppressed=show_suppressed)


def _render(result: CheckResult, *, show_suppressed: bool) -> None:
    if result.normalized != result.original:
        console.print("[dim]stage 0 rewrote the input (normalization)[/dim]")

    _edit_table("Edits", result.edits)
    if show_suppressed:
        _edit_table(
            "Suppressed (below confidence gate or overlapping)", result.suppressed,
            style="dim",
        )

    stages = Table(show_header=True, title="Stage resolution")
    stages.add_column("Stage")
    stages.add_column("Name")
    stages.add_column("Edits", justify="right")
    stages.add_column("ms", justify="right")
    stages.add_column("Note")
    for r in result.stage_reports:
        stages.add_row(
            str(r.stage),
            r.name,
            str(r.edits_emitted),
            f"{r.duration_ms:.1f}",
            r.skipped_reason or "",
            style="dim" if r.skipped_reason else None,
        )
    console.print(stages)
    console.print(f"[dim]total {result.total_ms:.1f} ms[/dim]")


def _edit_table(title: str, edits: list[Edit], style: str | None = None) -> None:
    if not edits:
        console.print(f"[dim]{title}: none[/dim]")
        return
    table = Table(title=title)
    table.add_column("Span", justify="right")
    table.add_column("Original")
    table.add_column("Suggestions")
    table.add_column("Class")
    table.add_column("Conf", justify="right")
    table.add_column("S", justify="center")
    table.add_column("ব্যাখ্যা")
    for e in edits:
        table.add_row(
            f"{e.start}-{e.end}",
            repr(e.original)[1:-1] or "·",
            ", ".join(e.suggestions) or "—",
            e.error_class.value,
            f"{e.confidence:.2f}",
            str(e.stage),
            e.explanation_bn,
            style=style,
        )
    console.print(table)


@app.command(name="eval")
def eval_cmd(
    language: Annotated[str, typer.Option("--language", "-l")] = "bn",
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Enforce the 600-verified-sentence gold-set requirement (spec §8).",
        ),
    ] = False,
    write_baseline_flag: Annotated[
        bool, typer.Option("--write-baseline", help="Commit these numbers as the baseline.")
    ] = False,
) -> None:
    """Run the evaluation harness and print the regression table."""
    from bhashasetu.eval.harness import check_gates, evaluate, write_baseline
    from bhashasetu.eval.report import render

    report = evaluate(language)
    gate = check_gates(report, allow_provisional=not strict)
    render(report, gate, console)

    if write_baseline_flag:
        write_baseline(report)
        console.print("[green]baseline written to eval/baseline.json[/green]")

    raise typer.Exit(0 if gate.passed else 1)


@app.command()
def classes(language: Annotated[str, typer.Option("--language", "-l")] = "bn") -> None:
    """List the error taxonomy and which stage implements each class today."""
    pack = get_pack(language)
    table = Table(title=f"Error taxonomy - {pack.name_native}")
    table.add_column("Code")
    table.add_column("Category")
    table.add_column("নাম")
    table.add_column("English")
    table.add_column("Stage", justify="center")
    table.add_column("Gold", justify="right")
    for code, spec in pack.error_classes.items():
        stage = str(spec.implemented_at_stage) if spec.implemented_at_stage else "—"
        table.add_row(
            code.value,
            spec.category,
            spec.label_native,
            spec.label_en,
            stage,
            str(len(spec.gold_cases)),
            style=None if spec.implemented_at_stage else "dim",
        )
    console.print(table)


@app.command()
def languages() -> None:
    """List registered language packs."""
    for code in available():
        console.print(code)


@identity_app.command("new")
def identity_new() -> None:
    """Mint a device id and a recovery phrase."""
    from bhashasetu.core.identity import generate_recovery_phrase, new_device_id

    device_id = new_device_id()
    phrase, secret_hash = generate_recovery_phrase()
    console.print(f"[bold]deviceId[/bold]      {device_id}")
    console.print(f"[bold]recovery[/bold]      {phrase}")
    console.print(f"[dim]secret_hash    {secret_hash}[/dim]")
    console.print(
        "\n[yellow]Store only secret_hash server-side. The phrase is shown once "
        "and cannot be recovered.[/yellow]"
    )


@identity_app.command("verify")
def identity_verify(
    phrase: Annotated[str, typer.Argument()],
    expected_hash: Annotated[str, typer.Argument()],
) -> None:
    """Check a recovery phrase against a stored hash."""
    from bhashasetu.core.identity import verify_recovery_phrase

    ok = verify_recovery_phrase(phrase, expected_hash)
    console.print("[green]match[/green]" if ok else "[red]no match[/red]")
    raise typer.Exit(0 if ok else 1)


@app.command()
def readability(
    text: Annotated[str, typer.Argument(help="Text, a file path, or - for stdin")],
    language: Annotated[str, typer.Option("--language", "-l")] = "bn",
) -> None:
    """Bangla-calibrated readability score. Formula: docs/readability.md."""
    body = _read_input(text)
    pack = get_pack(language)
    norm = pack.normalizer.normalize(body)
    sentences = pack.tokenizer.sentences(norm.text)
    scores = pack.readability.score(norm.text, sentences)
    table = Table(title="Readability")
    table.add_column("component")
    table.add_column("value", justify="right")
    for k, v in scores.items():
        table.add_row(k, f"{v}")
    console.print(table)
    missing = getattr(pack.readability, "components_missing", [])
    if missing:
        console.print(
            f"[yellow]not yet computed: {', '.join(missing)} "
            "(needs the parser landing in Phase 4); weights redistributed[/yellow]"
        )


if __name__ == "__main__":
    app()
