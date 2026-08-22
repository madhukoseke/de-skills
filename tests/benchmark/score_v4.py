#!/usr/bin/env python3
"""Score JSONL benchmark results for v6, v5, and no-skill baselines."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summary(rows: list[dict]) -> dict:
    return {
        "cases": len(rows),
        "critical_failures": sum(int(row.get("critical_failure", False)) for row in rows),
        "deterministic_pass_rate": sum(bool(row["deterministic_pass"]) for row in rows) / len(rows),
        "expert_score": statistics.mean(row["expert_score"] for row in rows),
        "median_references": statistics.median(row.get("references_loaded", 0) for row in rows),
        "median_output_tokens": statistics.median(row["output_tokens"] for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("v6", type=Path)
    parser.add_argument("v5", type=Path)
    parser.add_argument("no_skill", type=Path)
    parser.add_argument("--trigger-precision", type=float, required=True)
    parser.add_argument("--trigger-recall", type=float, required=True)
    args = parser.parse_args()
    groups = {name: summary(load(path)) for name, path in (("v6", args.v6), ("v5", args.v5), ("no_skill", args.no_skill))}
    v6, base = groups["v6"], groups["no_skill"]
    improvement = (v6["expert_score"] - base["expert_score"]) * 20
    token_ratio = v6["median_output_tokens"] / max(base["median_output_tokens"], 1)
    gates = json.loads(ROOT.joinpath("tests/benchmark/contract/v4.json").read_text())["gates"]
    passed = v6["critical_failures"] == 0 and v6["deterministic_pass_rate"] >= gates["deterministic_pass_rate"] and v6["expert_score"] >= gates["expert_score"] and improvement >= gates["improvement_points"] and v6["median_references"] <= gates["median_references"] and token_ratio <= gates["bounded_token_multiplier"] and args.trigger_precision >= gates["trigger_precision"] and args.trigger_recall >= gates["trigger_recall"]
    print(json.dumps({"groups": groups, "improvement_points": improvement, "token_ratio": token_ratio, "passed": passed}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
