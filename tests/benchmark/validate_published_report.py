#!/usr/bin/env python3
"""Require genuine, gate-passing benchmark evidence before a tagged release."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    version = sys.argv[1] if len(sys.argv) == 2 else ROOT.joinpath("VERSION").read_text().strip()
    base = ROOT / "tests" / "benchmark" / "published" / version
    json_path, markdown_path = base.with_suffix(".json"), base.with_suffix(".md")
    if not json_path.is_file() or not markdown_path.is_file():
        raise SystemExit(f"release evidence missing for {version}; require {json_path.relative_to(ROOT)} and {markdown_path.relative_to(ROOT)}")
    schema = json.loads(ROOT.joinpath("tests/benchmark/published-report.schema.json").read_text())
    report = json.loads(json_path.read_text())
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(report)
    if report["version"] != version or set(report["arms"]) != {"v6", "v5", "no_skill"}:
        raise SystemExit("published report version or comparison arms are invalid")
    gates = json.loads(ROOT.joinpath("tests/benchmark/contract/v4.json").read_text())["gates"]
    metrics, activation = report["metrics"], report["activation"]
    checks = [metrics["critical_failures"] == gates["critical_failures"], activation["precision"] >= gates["trigger_precision"], activation["recall"] >= gates["trigger_recall"], metrics["deterministic_pass_rate"] >= gates["deterministic_pass_rate"], metrics["expert_score"] >= gates["expert_score"], metrics["improvement_points"] >= gates["improvement_points"], metrics["median_references"] <= gates["median_references"], metrics["bounded_token_multiplier"] <= gates["bounded_token_multiplier"]]
    if not all(checks):
        raise SystemExit("published report claims pass but one or more v4 release gates fail")
    print(f"Published benchmark evidence passed for {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
