#!/usr/bin/env python3
"""Verify benchmark contract alignment with validator case checks."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FILE = ROOT / "tests" / "benchmark" / "contract" / "v1.json"
VALIDATOR_FILE = ROOT / "tests" / "validate_captured_responses.py"


def load_validator_case_ids() -> list[str]:
    spec = importlib.util.spec_from_file_location("validate_captured_responses", VALIDATOR_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return [case.case_id for case in module.CASE_CHECKS]


def main() -> int:
    if not CONTRACT_FILE.exists():
        print(f"error: missing contract file: {CONTRACT_FILE}", file=sys.stderr)
        return 2

    contract = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
    contract_case_ids = contract.get("case_ids", [])
    validator_case_ids = load_validator_case_ids()

    if contract_case_ids != validator_case_ids:
        print("error: contract case_ids and CASE_CHECKS are not identical.", file=sys.stderr)
        print(f"contract count={len(contract_case_ids)} validator count={len(validator_case_ids)}", file=sys.stderr)
        return 1

    weights = contract.get("rubric", {}).get("weights", {})
    if not weights:
        print("error: contract rubric weights missing.", file=sys.stderr)
        return 1
    total = sum(float(v) for v in weights.values())
    if abs(total - 1.0) > 1e-9:
        print(f"error: rubric weights must sum to 1.0, got {total}", file=sys.stderr)
        return 1

    thresholds = contract.get("gate_threshold_defaults", {})
    required_threshold_keys = {
        "min_with_skill_pass_rate",
        "min_with_skill_required_coverage",
        "min_with_skill_rubric_total",
        "min_rubric_delta_vs_baseline",
    }
    missing = required_threshold_keys.difference(thresholds.keys())
    if missing:
        print(f"error: contract missing threshold keys: {', '.join(sorted(missing))}", file=sys.stderr)
        return 1

    print(
        "Benchmark contract verification passed "
        f"(version={contract.get('contract_version')}, cases={len(contract_case_ids)})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
