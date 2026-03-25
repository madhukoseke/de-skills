#!/usr/bin/env python3
"""Generate markdown report for skill vs no-skill benchmark comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = ROOT / "tests" / "benchmark" / "results"
DEFAULT_COMPARISON_FILE = DEFAULT_RESULTS_DIR / "comparison.json"
DEFAULT_OUT_FILE = ROOT / "tests" / "benchmark" / "skill_vs_no_skill_report.md"
DEFAULT_NO_SKILL_VALIDATOR_FILE = DEFAULT_RESULTS_DIR / "no_skill_validator.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate skill-vs-no-skill benchmark markdown report.")
    parser.add_argument("--comparison-file", default=str(DEFAULT_COMPARISON_FILE))
    parser.add_argument("--no-skill-validator-file", default=str(DEFAULT_NO_SKILL_VALIDATOR_FILE))
    parser.add_argument("--out-file", default=str(DEFAULT_OUT_FILE))
    return parser.parse_args()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    args = parse_args()
    comparison_file = Path(args.comparison_file)
    no_skill_validator_file = Path(args.no_skill_validator_file)
    out_file = Path(args.out_file)

    comp = json.loads(read(comparison_file))
    summary = comp["summary"]
    cases = comp["cases"]
    contract = comp.get("contract", {})

    fail_lines: list[str] = []
    if no_skill_validator_file.exists():
        no_skill_val = read(no_skill_validator_file)
        fail_lines = [line.strip() for line in no_skill_val.splitlines() if line.strip().startswith("- ")]

    lines: list[str] = []
    lines.append("# Skill vs No-Skill Benchmark Report")
    lines.append("")
    lines.append("## Scope")
    lines.append(f"- Contract version: `{contract.get('version', 'unknown')}`.")
    lines.append(f"- Compared {summary['cases']} DE use cases from the E2E suite.")
    lines.append(f"- Comparison file: `{comparison_file}`.")
    lines.append("")
    lines.append("## Method")
    lines.append("- Contract pass/fail against required headings, required terms, and any-of groups.")
    lines.append("- Coverage metrics: required-term coverage and any-of-group coverage.")
    lines.append("- Rubric metrics (0-5 each): correctness, safety, actionability, cost awareness, testability.")
    lines.append("- Weighted rubric total normalized to 100 using contract-defined weights.")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(
        f"- Contract pass rate: **with skill {summary['with_skill_pass_count']}/{summary['cases']}** vs **no skill {summary['no_skill_pass_count']}/{summary['cases']}**."
    )
    lines.append(
        f"- Required-term coverage avg: **with skill {summary['with_skill_required_coverage_avg']:.3f}** vs **no skill {summary['no_skill_required_coverage_avg']:.3f}**."
    )
    lines.append(
        f"- Any-of-group coverage avg: **with skill {summary['with_skill_any_group_coverage_avg']:.3f}** vs **no skill {summary['no_skill_any_group_coverage_avg']:.3f}**."
    )
    lines.append(
        f"- Weighted rubric total avg: **with skill {summary['with_skill_rubric_total_avg']:.2f}/100** vs **no skill {summary['no_skill_rubric_total_avg']:.2f}/100**."
    )
    lines.append("")
    lines.append("## Aggregate Metrics")
    lines.append("| Metric | With Skill | No Skill | Delta |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| Contract pass count | {summary['with_skill_pass_count']} | {summary['no_skill_pass_count']} | {summary['with_skill_pass_count'] - summary['no_skill_pass_count']} |"
    )
    lines.append(
        f"| Required-term coverage avg | {summary['with_skill_required_coverage_avg']:.3f} | {summary['no_skill_required_coverage_avg']:.3f} | {summary['with_skill_required_coverage_avg'] - summary['no_skill_required_coverage_avg']:+.3f} |"
    )
    lines.append(
        f"| Any-group coverage avg | {summary['with_skill_any_group_coverage_avg']:.3f} | {summary['no_skill_any_group_coverage_avg']:.3f} | {summary['with_skill_any_group_coverage_avg'] - summary['no_skill_any_group_coverage_avg']:+.3f} |"
    )
    lines.append(
        f"| Rubric: correctness (0-5) | {summary['with_skill_correctness_avg']:.2f} | {summary['no_skill_correctness_avg']:.2f} | {summary['with_skill_correctness_avg'] - summary['no_skill_correctness_avg']:+.2f} |"
    )
    lines.append(
        f"| Rubric: safety (0-5) | {summary['with_skill_safety_avg']:.2f} | {summary['no_skill_safety_avg']:.2f} | {summary['with_skill_safety_avg'] - summary['no_skill_safety_avg']:+.2f} |"
    )
    lines.append(
        f"| Rubric: actionability (0-5) | {summary['with_skill_actionability_avg']:.2f} | {summary['no_skill_actionability_avg']:.2f} | {summary['with_skill_actionability_avg'] - summary['no_skill_actionability_avg']:+.2f} |"
    )
    lines.append(
        f"| Rubric: cost awareness (0-5) | {summary['with_skill_cost_awareness_avg']:.2f} | {summary['no_skill_cost_awareness_avg']:.2f} | {summary['with_skill_cost_awareness_avg'] - summary['no_skill_cost_awareness_avg']:+.2f} |"
    )
    lines.append(
        f"| Rubric: testability (0-5) | {summary['with_skill_testability_avg']:.2f} | {summary['no_skill_testability_avg']:.2f} | {summary['with_skill_testability_avg'] - summary['no_skill_testability_avg']:+.2f} |"
    )
    lines.append(
        f"| Rubric weighted total (0-100) | {summary['with_skill_rubric_total_avg']:.2f} | {summary['no_skill_rubric_total_avg']:.2f} | {summary['with_skill_rubric_total_avg'] - summary['no_skill_rubric_total_avg']:+.2f} |"
    )
    lines.append("")
    lines.append("## Per-Case Results")
    lines.append("| Case | With Skill Pass | No Skill Pass | Required Coverage (W/N) | Any-Group Coverage (W/N) | Rubric Total (W/N) |")
    lines.append("|---|---|---|---:|---:|---:|")
    for c in cases:
        lines.append(
            f"| {c['case_id']} | {'PASS' if c['with_skill_pass'] else 'FAIL'} | {'PASS' if c['no_skill_pass'] else 'FAIL'} | {c['with_skill_required_coverage']:.3f}/{c['no_skill_required_coverage']:.3f} | {c['with_skill_any_group_coverage']:.3f}/{c['no_skill_any_group_coverage']:.3f} | {c['with_skill_rubric_total']:.2f}/{c['no_skill_rubric_total']:.2f} |"
        )
    lines.append("")
    lines.append("## No-Skill Failure Details")
    if fail_lines:
        for line in fail_lines:
            lines.append(line)
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Notes")
    lines.append("- Baseline responses are synthetic unless this run was generated via the live benchmark harness.")
    lines.append("- Contract and thresholds should be versioned via `tests/benchmark/contract/`.")
    lines.append("")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
