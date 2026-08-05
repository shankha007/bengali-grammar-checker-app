"""Loader for `<pack>/error_classes.yaml`.

Application logic reads specs from here. It must never branch on a hard-coded
error-class string with a language-specific message attached.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bhashasetu.core.types import CATEGORY_OF, ErrorClass, ErrorClassSpec


class ErrorClassConfigError(ValueError):
    pass


def load_error_classes(path: Path) -> dict[ErrorClass, ErrorClassSpec]:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "error_classes" not in raw:
        raise ErrorClassConfigError(f"{path}: missing top-level 'error_classes' key")

    specs: dict[ErrorClass, ErrorClassSpec] = {}
    for code, body in raw["error_classes"].items():
        try:
            klass = ErrorClass(code)
        except ValueError as exc:
            raise ErrorClassConfigError(
                f"{path}: '{code}' is not one of the 12 declared error classes"
            ) from exc

        missing = [
            k
            for k in ("label_native", "label_en", "explanation_native", "explanation_en")
            if not body.get(k)
        ]
        if missing:
            raise ErrorClassConfigError(f"{path}: {code} missing {', '.join(missing)}")

        gold = list(body.get("gold_cases") or [])
        if len(gold) < 3:
            # Spec §3: "at least 3 gold test cases" per class. This is a load-time
            # failure, not a lint warning - an unverifiable error class must not
            # be shippable.
            raise ErrorClassConfigError(
                f"{path}: {code} declares {len(gold)} gold cases, needs at least 3"
            )

        specs[klass] = ErrorClassSpec(
            code=klass,
            category=CATEGORY_OF[klass],
            label_native=body["label_native"],
            label_en=body["label_en"],
            explanation_template_native=body["explanation_native"],
            explanation_template_en=body["explanation_en"],
            rule_reference=body.get("rule_reference"),
            implemented_at_stage=body.get("implemented_at_stage"),
            gold_cases=gold,
            explanation_template_native_no_fix=body.get("explanation_native_no_fix"),
            explanation_template_en_no_fix=body.get("explanation_en_no_fix"),
        )

    missing_classes = set(ErrorClass) - set(specs)
    if missing_classes:
        raise ErrorClassConfigError(
            f"{path}: no spec for {', '.join(sorted(c.value for c in missing_classes))}"
        )
    return specs
