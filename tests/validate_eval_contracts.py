#!/usr/bin/env python3
"""Validate benchmark v4 coverage and release-gate declarations."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    jsonschema.Draft202012Validator.check_schema(
        json.loads(ROOT.joinpath("tests/benchmark/published-report.schema.json").read_text())
    )
    contract = json.loads(ROOT.joinpath("tests/benchmark/contract/v4.json").read_text())
    scenarios = contract["scenarios"]
    if len(scenarios) != 48:
        raise SystemExit(f"benchmark v4 needs 48 scenarios; got {len(scenarios)}")
    counts = Counter(case["domain"] for case in scenarios)
    if len(counts) != 12 or set(counts.values()) != {4}:
        raise SystemExit(f"expected twelve domains with four cases each: {counts}")
    if len({case["id"] for case in scenarios}) != 48:
        raise SystemExit("scenario IDs are not unique")
    valid_workflows = {"GUIDE", "DESIGN", "BUILD", "REVIEW", "OPERATE", "MODERNIZE"}
    if any(case["workflow"] not in valid_workflows or not case["requires"] or not case["forbids"] for case in scenarios):
        raise SystemExit("scenario workflow or deterministic assertions are invalid")
    triggers = json.loads(ROOT.joinpath("tests/evals/trigger_cases.json").read_text())
    if len(triggers["should_trigger"]) != 40 or len(triggers["should_not_trigger"]) != 40:
        raise SystemExit("activation suite must contain 40 positive and 40 negative prompts")
    gates = contract["gates"]
    expected = {"critical_failures": 0, "trigger_precision": .95, "trigger_recall": .95, "deterministic_pass_rate": .90, "expert_score": 4.2, "improvement_points": 10, "median_references": 3, "bounded_token_multiplier": 2.0}
    if gates != expected:
        raise SystemExit(f"release gate drift: {gates}")
    repo_manifest = json.loads(ROOT.joinpath("tests/fixtures/repositories/repo_cases.json").read_text())
    scenario_ids = {case["id"] for case in scenarios}
    for case in repo_manifest["cases"]:
        fixture = ROOT / "tests" / "fixtures" / "repositories" / case["fixture"]
        if case["id"] not in scenario_ids or not fixture.is_dir():
            raise SystemExit(f"invalid repository fixture case: {case}")
        for artifact in case["required_artifacts"]:
            if not fixture.joinpath(artifact).is_file():
                raise SystemExit(f"missing repository fixture artifact: {fixture / artifact}")
    print("Benchmark v4 passed: 48 scenarios, 12 domains, 80 activation prompts, repository fixtures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
