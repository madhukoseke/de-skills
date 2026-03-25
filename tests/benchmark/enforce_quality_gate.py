#!/usr/bin/env python3
"""Enforce benchmark quality gates for skill-guided responses."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPARISON_FILE = ROOT / "tests" / "benchmark" / "results" / "comparison.json"


def parse_args() -> Path:
    if len(sys.argv) > 2:
        print("usage: enforce_quality_gate.py [comparison_json_path]", file=sys.stderr)
        raise SystemExit(2)
    if len(sys.argv) == 2:
        return Path(sys.argv[1])
    return COMPARISON_FILE


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"error: {name} must be numeric, got: {raw}", file=sys.stderr)
        raise SystemExit(2)


def main() -> int:
    comparison_file = parse_args()
    if not comparison_file.exists():
        print(
            f"error: comparison file missing: {comparison_file}. Run compare_skill_vs_no_skill.py first.",
            file=sys.stderr,
        )
        return 2

    data = json.loads(comparison_file.read_text(encoding="utf-8"))
    s = data["summary"]
    defaults = data.get("contract", {}).get("threshold_defaults", {})

    cases = float(s["cases"])
    with_pass_rate = s["with_skill_pass_count"] / cases
    no_pass_rate = s["no_skill_pass_count"] / cases

    min_with_pass_rate = env_float(
        "BENCHMARK_MIN_WITH_SKILL_PASS_RATE",
        float(defaults.get("min_with_skill_pass_rate", 0.92)),
    )
    min_with_required_cov = env_float(
        "BENCHMARK_MIN_WITH_SKILL_REQUIRED_COVERAGE",
        float(defaults.get("min_with_skill_required_coverage", 0.95)),
    )
    min_with_rubric = env_float(
        "BENCHMARK_MIN_WITH_SKILL_RUBRIC_TOTAL",
        float(defaults.get("min_with_skill_rubric_total", 75.0)),
    )
    min_rubric_delta = env_float(
        "BENCHMARK_MIN_RUBRIC_DELTA_VS_BASELINE",
        float(defaults.get("min_rubric_delta_vs_baseline", 8.0)),
    )

    checks = [
        (
            "with_skill_pass_rate",
            with_pass_rate,
            min_with_pass_rate,
            with_pass_rate >= min_with_pass_rate,
        ),
        (
            "with_skill_required_coverage_avg",
            float(s["with_skill_required_coverage_avg"]),
            min_with_required_cov,
            float(s["with_skill_required_coverage_avg"]) >= min_with_required_cov,
        ),
        (
            "with_skill_rubric_total_avg",
            float(s["with_skill_rubric_total_avg"]),
            min_with_rubric,
            float(s["with_skill_rubric_total_avg"]) >= min_with_rubric,
        ),
        (
            "rubric_delta_vs_baseline",
            float(s["with_skill_rubric_total_avg"]) - float(s["no_skill_rubric_total_avg"]),
            min_rubric_delta,
            (float(s["with_skill_rubric_total_avg"]) - float(s["no_skill_rubric_total_avg"]))
            >= min_rubric_delta,
        ),
        (
            "with_skill_beats_baseline_pass_rate",
            with_pass_rate,
            no_pass_rate,
            with_pass_rate > no_pass_rate,
        ),
    ]

    failed = [c for c in checks if not c[3]]

    print("Benchmark quality gate summary:")
    print(f"- cases: {int(cases)}")
    print(f"- with_skill_pass_rate: {with_pass_rate:.3f}")
    print(f"- no_skill_pass_rate: {no_pass_rate:.3f}")
    print(f"- with_skill_required_coverage_avg: {s['with_skill_required_coverage_avg']:.3f}")
    print(f"- with_skill_rubric_total_avg: {s['with_skill_rubric_total_avg']:.2f}")
    print(f"- no_skill_rubric_total_avg: {s['no_skill_rubric_total_avg']:.2f}")

    if failed:
        print("\nBenchmark quality gate failed:\n")
        for name, actual, expected, _ in failed:
            print(f"- {name}: actual={actual:.3f} expected>={expected:.3f}")
        return 1

    print("\nBenchmark quality gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
