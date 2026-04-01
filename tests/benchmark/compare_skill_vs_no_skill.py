#!/usr/bin/env python3
"""Compare skill-guided vs baseline response sets for benchmark cases."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WITH_SKILL_DIR = ROOT / "tests" / "captured_responses"
DEFAULT_NO_SKILL_DIR = ROOT / "tests" / "benchmark" / "no_skill"
DEFAULT_OUTPUT_FILE = ROOT / "tests" / "benchmark" / "results" / "comparison.json"
DEFAULT_CONTRACT_FILE = ROOT / "tests" / "benchmark" / "contract" / "v2.json"


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
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract_alignment(contract: dict) -> None:
    case_ids = [case.case_id for case in CASE_CHECKS]
    contract_case_ids = contract.get("case_ids", [])
    if case_ids != contract_case_ids:
        print("error: CASE_CHECKS and benchmark contract case_ids are out of sync.", file=sys.stderr)
        print(f"validator count={len(case_ids)} contract count={len(contract_case_ids)}", file=sys.stderr)
        raise SystemExit(2)

    weights = contract.get("rubric", {}).get("weights", {})
    dimensions = contract.get("rubric", {}).get("dimensions", [])
    if not weights or not dimensions:
        print("error: contract rubric dimensions/weights missing.", file=sys.stderr)
        raise SystemExit(2)
    if set(weights.keys()) != set(dimensions):
        print("error: contract rubric dimensions and weight keys do not match.", file=sys.stderr)
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


def required_coverage(text: str, terms: tuple[str, ...]) -> tuple[int, int]:
    lower = text.lower()
    matched = sum(1 for t in terms if t.lower() in lower)
    return matched, len(terms)


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
    if sum(1 for token in domain_tokens if token in text.lower()) >= 2:
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
    hits = sum(1 for token in tokens if token in lower)
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
    score += min(2.0, sum(1 for token in action_terms if token in lower) * 0.25)
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
    hits = sum(1 for token in tokens if token in lower)
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
    hits = sum(1 for token in tokens if token in lower)
    if hits == 0:
        return 1.0
    if hits <= 2:
        return 2.5
    if hits <= 4:
        return 3.5
    if hits <= 6:
        return 4.5
    return 5.0


def formatting_compliance_score(text: str) -> float:
    headings_present, headings_total = heading_coverage(text)
    heading_part = headings_present / headings_total if headings_total else 1.0
    table_part = 1.0 if "|---" in text else 0.0
    next_steps_part = 1.0 if numbered_steps(text) >= 1 else 0.0
    return round(((heading_part * 0.6) + (table_part * 0.2) + (next_steps_part * 0.2)) * 5.0, 2)


def clarification_quality_score(text: str) -> float:
    lower = text.lower()
    signals = [
        "missing",
        "confirm",
        "clarify",
        "assumption",
        "if you do not have",
        "before finalizing",
        "need the following",
    ]
    hits = sum(1 for signal in signals if signal in lower)
    question_marks = text.count("?")
    if hits == 0 and question_marks == 0:
        return 2.5
    if hits <= 1 and question_marks <= 1:
        return 3.5
    if hits <= 3 and question_marks <= 3:
        return 4.5
    return 5.0


def prompt_injection_resilience_score(text: str) -> float:
    lower = text.lower()
    positive = [
        "untrusted",
        "ignore embedded instructions",
        "do not execute",
        "analysis only",
        "treat",
        "prompt injection",
    ]
    risky = ["run shell", "execute the code", "import and run"]
    pos_hits = sum(1 for token in positive if token in lower)
    risky_hits = sum(1 for token in risky if token in lower)
    if risky_hits > 0 and pos_hits == 0:
        return 1.0
    if pos_hits == 0:
        return 3.0
    if pos_hits <= 2:
        return 4.0
    return 5.0


SCORE_FUNCTIONS = {
    "correctness": correctness_score,
    "safety": lambda text, *_: safety_score(text),
    "actionability": lambda text, *_: actionability_score(text),
    "cost_awareness": lambda text, *_: cost_awareness_score(text),
    "testability": lambda text, *_: testability_score(text),
    "formatting_compliance": lambda text, *_: formatting_compliance_score(text),
    "clarification_quality": lambda text, *_: clarification_quality_score(text),
    "prompt_injection_resilience": lambda text, *_: prompt_injection_resilience_score(text),
}


def rubric_total(scores: dict[str, float], weights: dict[str, float]) -> float:
    weighted = sum(float(scores[dimension]) * float(weights[dimension]) for dimension in weights)
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


def compute_scores(text: str, case, dimensions: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for dimension in dimensions:
        fn = SCORE_FUNCTIONS[dimension]
        scores[dimension] = fn(text, case.required_terms, case.any_of_terms)
    return scores


def summarize(rows: list[dict], dimensions: list[str]) -> dict[str, float]:
    def avg(key: str) -> float:
        return round(sum(float(row[key]) for row in rows) / len(rows), 3)

    summary = {
        "cases": len(rows),
        "with_skill_pass_count": sum(1 for row in rows if row["with_skill_pass"]),
        "no_skill_pass_count": sum(1 for row in rows if row["no_skill_pass"]),
        "with_skill_required_coverage_avg": avg("with_skill_required_coverage"),
        "no_skill_required_coverage_avg": avg("no_skill_required_coverage"),
        "with_skill_any_group_coverage_avg": avg("with_skill_any_group_coverage"),
        "no_skill_any_group_coverage_avg": avg("no_skill_any_group_coverage"),
        "with_skill_word_count_avg": avg("with_skill_word_count"),
        "no_skill_word_count_avg": avg("no_skill_word_count"),
        "with_skill_steps_avg": avg("with_skill_steps"),
        "no_skill_steps_avg": avg("no_skill_steps"),
        "with_skill_specificity_avg": avg("with_skill_specificity"),
        "no_skill_specificity_avg": avg("no_skill_specificity"),
        "with_skill_rubric_total_avg": avg("with_skill_rubric_total"),
        "no_skill_rubric_total_avg": avg("no_skill_rubric_total"),
    }
    for dimension in dimensions:
        summary[f"with_skill_{dimension}_avg"] = avg(f"with_skill_{dimension}_score")
        summary[f"no_skill_{dimension}_avg"] = avg(f"no_skill_{dimension}_score")
    return summary


def main() -> int:
    args = parse_args()
    with_skill_dir = Path(args.with_skill_dir)
    no_skill_dir = Path(args.no_skill_dir)
    output_file = Path(args.output_file)
    contract_file = Path(args.contract_file)

    contract = load_contract(contract_file)
    validate_contract_alignment(contract)
    dimensions = contract["rubric"]["dimensions"]
    weights = contract["rubric"]["weights"]

    rows: list[dict] = []
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
            for path in missing_with_skill:
                print(f"- {path}")
        if missing_no_skill:
            print("Missing no-skill baseline files:")
            for path in missing_no_skill:
                print(f"- {path}")
        print("\nPopulate missing files before running benchmark.", file=sys.stderr)
        return 2

    for case in CASE_CHECKS:
        with_skill_text = read_text(with_skill_dir / f"{case.case_id}.md")
        no_skill_text = read_text(no_skill_dir / f"{case.case_id}.md")

        with_req_matched, with_req_total = required_coverage(with_skill_text, case.required_terms)
        no_req_matched, no_req_total = required_coverage(no_skill_text, case.required_terms)
        with_any_matched, with_any_total = any_group_coverage(with_skill_text, case.any_of_terms)
        no_any_matched, no_any_total = any_group_coverage(no_skill_text, case.any_of_terms)

        with_scores = compute_scores(with_skill_text, case, dimensions)
        no_scores = compute_scores(no_skill_text, case, dimensions)

        row = {
            "case_id": case.case_id,
            "with_skill_pass": case_pass(with_skill_text, case.required_terms, case.any_of_terms),
            "no_skill_pass": case_pass(no_skill_text, case.required_terms, case.any_of_terms),
            "with_skill_required_coverage": fraction(with_req_matched, with_req_total),
            "no_skill_required_coverage": fraction(no_req_matched, no_req_total),
            "with_skill_any_group_coverage": fraction(with_any_matched, with_any_total),
            "no_skill_any_group_coverage": fraction(no_any_matched, no_any_total),
            "with_skill_word_count": word_count(with_skill_text),
            "no_skill_word_count": word_count(no_skill_text),
            "with_skill_steps": numbered_steps(with_skill_text),
            "no_skill_steps": numbered_steps(no_skill_text),
            "with_skill_specificity": specificity_score(with_skill_text),
            "no_skill_specificity": specificity_score(no_skill_text),
        }

        for dimension in dimensions:
            row[f"with_skill_{dimension}_score"] = with_scores[dimension]
            row[f"no_skill_{dimension}_score"] = no_scores[dimension]

        row["with_skill_rubric_total"] = rubric_total(with_scores, weights)
        row["no_skill_rubric_total"] = rubric_total(no_scores, weights)
        rows.append(row)

    summary = summarize(rows, dimensions)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(
            {
                "contract": {
                    "version": contract["contract_version"],
                    "dimensions": dimensions,
                    "weights": weights,
                    "threshold_defaults": contract["gate_threshold_defaults"],
                },
                "summary": summary,
                "cases": rows,
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
