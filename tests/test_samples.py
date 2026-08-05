"""The editor's Sample-button corpus.

frontend/lib/samples.ts is generated from the gold set, and the frontend has no
test runner of its own, so the guarantees it relies on are checked here:

  - it is in step with the gold set and the detectors, and
  - every sentence it offers actually produces a flag.

The second is the one that matters in front of a user. A demo button that loads
text and reports nothing wrong with it reads as a broken product, and it would
break silently — a detector change or a gold edit is all it takes.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from bhashasetu.core.pipeline import Pipeline
from bhashasetu.core.registry import get_pack

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_TS = ROOT / "frontend" / "lib" / "samples.ts"


def load_samples() -> list[str]:
    """Read the string literals out of the generated TypeScript.

    A regex over generated code is acceptable where it would not be over
    hand-written code: the shape is fixed by scripts/generate_samples.py, and
    test_samples_file_is_up_to_date fails first if that stops being true.
    """
    source = SAMPLES_TS.read_text(encoding="utf-8")
    body = source.split("export const SAMPLES", 1)[1].split("] as const;", 1)[0]
    return [json.loads(m) for m in re.findall(r'^\s*("(?:[^"\\]|\\.)*"),$', body, re.M)]


@pytest.fixture(scope="module")
def samples() -> list[str]:
    return load_samples()


def test_samples_file_is_up_to_date() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_samples.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_there_are_a_hundred_samples(samples: list[str]) -> None:
    assert len(samples) == 100
    assert len(set(samples)) == len(samples), "duplicates make the button repeat itself"


def test_every_sample_produces_at_least_one_edit(samples: list[str]) -> None:
    """The whole point of the button: text that demonstrates the checker."""
    pipeline = Pipeline(get_pack("bn"))
    silent = [s for s in samples if not pipeline.check(s).edits]
    assert not silent, f"{len(silent)} sample(s) come back clean: {silent[:3]}"


def test_samples_are_bengali(samples: list[str]) -> None:
    for sample in samples:
        assert any("ঀ" <= ch <= "৿" for ch in sample), sample
