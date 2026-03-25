#!/usr/bin/env python3
"""Compare skill-guided vs baseline response sets for benchmark cases."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WITH_SKILL_DIR = ROOT / "tests" / "captured_responses"
DEFAULT_NO_SKILL_DIR = ROOT / "tests" / "benchmark" / "no_skill"
DEFAULT_OUTPUT_FILE = ROOT / "tests" / "benchmark" / "results" / "comparison.json"
DEFAULT_CONTRACT_FILE = ROOT / "tests" / "benchmark" / "contract" / "v1.json"


def load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "validate_captured_responses",
        ROOT / "tests" / "validate_captured_responses.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = load_validator_module()
CASE_CHECKS = validator.CASE_CHECKS
REQUIRED_HEADINGS = validator.REQUIRED_HEADINGS
has_any_terms = validator.has_any_terms


@dataclass
class CaseMetrics:
    case_id: str
    with_skill_pass: bool
    no_skill_pass: bool
    with_skill_required_coverage: float
    no_skill_required_coverage: float
    with_skill_any_group_coverage: float
    no_skill_any_group_coverage: float
    with_skill_word_count: int
    no_skill_word_count: int
    with_skill_steps: int
    no_skill_steps: int
    with_skill_specificity: int
    no_skill_specificity: int
    with_skill_correctness_score: float
    no_skill_correctness_score: float
    with_skill_safety_score: float
    no_skill_safety_score: float
    with_skill_actionability_score: float
    no_skill_actionability_score: float
    with_skill_cost_awareness_score: float
    no_skill_cost_awareness_score: float
    with_skill_testability_score: float
    no_skill_testability_score: float
    with_skill_rubric_total: float
    no_skill_rubric_total: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare skill-guided and baseline benchmark responses.")
    parser.add_argument("--with-skill-dir", default=str(DEFAULT_WITH_SKILL_DIR))
    parser.add_argument("--no-skill-dir", default=str(DEFAULT_NO_SKILL_DIR))
    parser.add_argument("--output-file", default=str(DEFAULT_OUTPUT_FILE))
    parser.add_argument("--contract-file", default=str(DEFAULT_CONTRACT_FILE))
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_contract(path: Path) -> dict:
    if not path.exists():
        print(f"error: contract file missing: {path}", file=sys.stderr)
        raise SystemExit(2)
    contract = json.loads(path.read_text(encoding="utf-8"))
    return contract


def validate_contract_alignment(contract: dict) -> None:
    case_ids = [case.case_id for case in CASE_CHECKS]
    contract_case_ids = contract.get("case_ids", [])
    if case_ids != contract_case_ids:
        print("error: CASE_CHECKS and benchmark contract case_ids are out of sync.", file=sys.stderr)
        print(f"validator count={len(case_ids)} contract count={len(contract_case_ids)}", file=sys.stderr)
        raise SystemExit(2)

    weights = contract.get("rubric", {}).get("weights", {})
    if not weights:
        print("error: contract rubric weights missing.", file=sys.stderr)
        raise SystemExit(2)
    total = sum(float(v) for v in weights.values())
    if abs(total - 1.0) > 1e-9:
        print(f"error: rubric weights must sum to 1.0, got {total}", file=sys.stderr)
        raise SystemExit(2)


def heading_coverage(text: str) -> tuple[int, int]:
    present = 0
    for heading in REQUIRED_HEADINGS:
        if re.search(rf"^\s*{re.escape(heading)}\s*$", text, re.MULTILINE):
            present += 1
    return present, len(REQUIRED_HEADINGS)


def required_coverage(text: str, terms: Iterable[str]) -> tuple[int, int]:
    lower = text.lower()
    matched = sum(1 for t in terms if t.lower() in lower)
    total = len(tuple(terms))
    return matched, total


def any_group_coverage(text: str, groups: tuple[tuple[str, ...], ...]) -> tuple[int, int]:
    if not groups:
        return 0, 0
    matched = sum(1 for g in groups if has_any_terms(text, g))
    return matched, len(groups)


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def numbered_steps(text: str) -> int:
    return len(re.findall(r"^\s*\d+\.\s+", text, re.MULTILINE))


def specificity_score(text: str) -> int:
    score = 0
    if "`" in text:
        score += 1
    if len(re.findall(r"\d", text)) >= 2:
        score += 1
    if "|---" in text:
        score += 1
    if numbered_steps(text) >= 3:
        score += 1
    domain_tokens = [
        "idempot",
        "partition",
        "backoff",
        "dead-letter",
        "schema.yml",
        "root cause",
        "quarantine",
        "risk assessment",
    ]
    if sum(1 for t in domain_tokens if t in text.lower()) >= 2:
        score += 1
    return score


def correctness_score(text: str, required_terms: tuple[str, ...], any_groups: tuple[tuple[str, ...], ...]) -> float:
    req_matched, req_total = required_coverage(text, required_terms)
    any_matched, any_total = any_group_coverage(text, any_groups)
    req_part = (req_matched / req_total) if req_total else 1.0
    any_part = (any_matched / any_total) if any_total else 1.0
    technical = specificity_score(text) / 5.0
    return round(((req_part * 0.5) + (any_part * 0.3) + (technical * 0.2)) * 5.0, 2)


def safety_score(text: str) -> float:
    lower = text.lower()
    tokens = [
        "idempot",
        "retry",
        "backoff",
        "dead-letter",
        "risk",
        "alert",
        "quarantine",
        "untrusted",
        "do not execute",
        "analysis only",
        "fail loud",
        "rollback",
    ]
    hits = sum(1 for t in tokens if t in lower)
    if hits == 0:
        return 1.0
    if hits <= 2:
        return 2.5
    if hits <= 4:
        return 3.5
    if hits <= 6:
        return 4.5
    return 5.0


def actionability_score(text: str) -> float:
    steps = numbered_steps(text)
    score = 0.0
    if steps >= 3:
        score += 3.0
    elif steps == 2:
        score += 2.0
    elif steps == 1:
        score += 1.0

    lower = text.lower()
    action_terms = ["implement", "add", "validate", "configure", "define", "monitor", "run", "review", "plan"]
    score += min(2.0, sum(1 for t in action_terms if t in lower) * 0.25)
    return round(min(5.0, score), 2)


def cost_awareness_score(text: str) -> float:
    lower = text.lower()
    tokens = [
        "cost",
        "bytes scanned",
        "partition pruning",
        "storage",
        "materialized view",
        "cache",
        "index",
        "throughput",
        "latency",
    ]
    hits = sum(1 for t in tokens if t in lower)
    if hits == 0:
        return 1.0
    if hits <= 2:
        return 2.5
    if hits <= 4:
        return 3.5
    if hits <= 6:
        return 4.5
    return 5.0


def testability_score(text: str) -> float:
    lower = text.lower()
    tokens = [
        "unit test",
        "integration",
        "e2e",
        "assert",
        "fixture",
        "contract test",
        "reconciliation",
        "checksum",
        "explain",
    ]
    hits = sum(1 for t in tokens if t in lower)
    if hits == 0:
        return 1.0
    if hits <= 2:
        return 2.5
    if hits <= 4:
        return 3.5
    if hits <= 6:
        return 4.5
    return 5.0


def rubric_total(
    correctness: float,
    safety: float,
    actionability: float,
    cost_awareness: float,
    testability: float,
    weights: dict[str, float],
) -> float:
    weighted = (
        correctness * float(weights["correctness"])
        + safety * float(weights["safety"])
        + actionability * float(weights["actionability"])
        + cost_awareness * float(weights["cost_awareness"])
        + testability * float(weights["testability"])
    )
    return round(weighted * 20.0, 2)


def case_pass(text: str, required_terms: tuple[str, ...], any_groups: tuple[tuple[str, ...], ...]) -> bool:
    headings_present, headings_total = heading_coverage(text)
    if headings_present != headings_total:
        return False
    required_matched, required_total = required_coverage(text, required_terms)
    if required_matched != required_total:
        return False
    for group in any_groups:
        if not has_any_terms(text, group):
            return False
    return True


def fraction(num: int, den: int) -> float:
    if den == 0:
        return 1.0
    return round(num / den, 4)


def summarize(rows: list[CaseMetrics]) -> dict[str, float]:
    def avg(getter):
        return round(sum(getter(r) for r in rows) / len(rows), 3)

    return {
        "cases": len(rows),
        "with_skill_pass_count": sum(1 for r in rows if r.with_skill_pass),
        "no_skill_pass_count": sum(1 for r in rows if r.no_skill_pass),
        "with_skill_required_coverage_avg": avg(lambda r: r.with_skill_required_coverage),
        "no_skill_required_coverage_avg": avg(lambda r: r.no_skill_required_coverage),
        "with_skill_any_group_coverage_avg": avg(lambda r: r.with_skill_any_group_coverage),
        "no_skill_any_group_coverage_avg": avg(lambda r: r.no_skill_any_group_coverage),
        "with_skill_word_count_avg": avg(lambda r: r.with_skill_word_count),
        "no_skill_word_count_avg": avg(lambda r: r.no_skill_word_count),
        "with_skill_steps_avg": avg(lambda r: r.with_skill_steps),
        "no_skill_steps_avg": avg(lambda r: r.no_skill_steps),
        "with_skill_specificity_avg": avg(lambda r: r.with_skill_specificity),
        "no_skill_specificity_avg": avg(lambda r: r.no_skill_specificity),
        "with_skill_correctness_avg": avg(lambda r: r.with_skill_correctness_score),
        "no_skill_correctness_avg": avg(lambda r: r.no_skill_correctness_score),
        "with_skill_safety_avg": avg(lambda r: r.with_skill_safety_score),
        "no_skill_safety_avg": avg(lambda r: r.no_skill_safety_score),
        "with_skill_actionability_avg": avg(lambda r: r.with_skill_actionability_score),
        "no_skill_actionability_avg": avg(lambda r: r.no_skill_actionability_score),
        "with_skill_cost_awareness_avg": avg(lambda r: r.with_skill_cost_awareness_score),
        "no_skill_cost_awareness_avg": avg(lambda r: r.no_skill_cost_awareness_score),
        "with_skill_testability_avg": avg(lambda r: r.with_skill_testability_score),
        "no_skill_testability_avg": avg(lambda r: r.no_skill_testability_score),
        "with_skill_rubric_total_avg": avg(lambda r: r.with_skill_rubric_total),
        "no_skill_rubric_total_avg": avg(lambda r: r.no_skill_rubric_total),
    }


def main() -> int:
    args = parse_args()
    with_skill_dir = Path(args.with_skill_dir)
    no_skill_dir = Path(args.no_skill_dir)
    output_file = Path(args.output_file)
    contract_file = Path(args.contract_file)

    contract = load_contract(contract_file)
    validate_contract_alignment(contract)
    weights = contract["rubric"]["weights"]

    rows: list[CaseMetrics] = []
    missing_with_skill: list[str] = []
    missing_no_skill: list[str] = []

    for case in CASE_CHECKS:
        with_path = with_skill_dir / f"{case.case_id}.md"
        no_path = no_skill_dir / f"{case.case_id}.md"
        if not with_path.exists():
            missing_with_skill.append(str(with_path))
        if not no_path.exists():
            missing_no_skill.append(str(no_path))

    if missing_with_skill or missing_no_skill:
        if missing_with_skill:
            print("Missing with-skill response files:")
            for p in missing_with_skill:
                print(f"- {p}")
        if missing_no_skill:
            print("Missing no-skill baseline files:")
            for p in missing_no_skill:
                print(f"- {p}")
        print("\nPopulate missing files before running benchmark.", file=sys.stderr)
        return 2

    for case in CASE_CHECKS:
        with_skill_text = read_text(with_skill_dir / f"{case.case_id}.md")
        no_skill_text = read_text(no_skill_dir / f"{case.case_id}.md")

        with_req_matched, with_req_total = required_coverage(with_skill_text, case.required_terms)
        no_req_matched, no_req_total = required_coverage(no_skill_text, case.required_terms)
        with_any_matched, with_any_total = any_group_coverage(with_skill_text, case.any_of_terms)
        no_any_matched, no_any_total = any_group_coverage(no_skill_text, case.any_of_terms)

        with_correctness = correctness_score(with_skill_text, case.required_terms, case.any_of_terms)
        no_correctness = correctness_score(no_skill_text, case.required_terms, case.any_of_terms)
        with_safety = safety_score(with_skill_text)
        no_safety = safety_score(no_skill_text)
        with_actionability = actionability_score(with_skill_text)
        no_actionability = actionability_score(no_skill_text)
        with_cost = cost_awareness_score(with_skill_text)
        no_cost = cost_awareness_score(no_skill_text)
        with_testability = testability_score(with_skill_text)
        no_testability = testability_score(no_skill_text)

        rows.append(
            CaseMetrics(
                case_id=case.case_id,
                with_skill_pass=case_pass(with_skill_text, case.required_terms, case.any_of_terms),
                no_skill_pass=case_pass(no_skill_text, case.required_terms, case.any_of_terms),
                with_skill_required_coverage=fraction(with_req_matched, with_req_total),
                no_skill_required_coverage=fraction(no_req_matched, no_req_total),
                with_skill_any_group_coverage=fraction(with_any_matched, with_any_total),
                no_skill_any_group_coverage=fraction(no_any_matched, no_any_total),
                with_skill_word_count=word_count(with_skill_text),
                no_skill_word_count=word_count(no_skill_text),
                with_skill_steps=numbered_steps(with_skill_text),
                no_skill_steps=numbered_steps(no_skill_text),
                with_skill_specificity=specificity_score(with_skill_text),
                no_skill_specificity=specificity_score(no_skill_text),
                with_skill_correctness_score=with_correctness,
                no_skill_correctness_score=no_correctness,
                with_skill_safety_score=with_safety,
                no_skill_safety_score=no_safety,
                with_skill_actionability_score=with_actionability,
                no_skill_actionability_score=no_actionability,
                with_skill_cost_awareness_score=with_cost,
                no_skill_cost_awareness_score=no_cost,
                with_skill_testability_score=with_testability,
                no_skill_testability_score=no_testability,
                with_skill_rubric_total=rubric_total(
                    with_correctness,
                    with_safety,
                    with_actionability,
                    with_cost,
                    with_testability,
                    weights,
                ),
                no_skill_rubric_total=rubric_total(
                    no_correctness,
                    no_safety,
                    no_actionability,
                    no_cost,
                    no_testability,
                    weights,
                ),
            )
        )

    summary = summarize(rows)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(
            {
                "contract": {
                    "version": contract["contract_version"],
                    "weights": weights,
                    "threshold_defaults": contract["gate_threshold_defaults"],
                },
                "summary": summary,
                "cases": [asdict(r) for r in rows],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
