#!/usr/bin/env python3
"""Validate captured model responses against the E2E test case contract."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_HEADINGS = [
    "## Summary",
    "## Decision",
    "## Rationale",
    "## Trade-offs",
    "## Next Steps",
]


@dataclass(frozen=True)
class CaseCheck:
    case_id: str
    description: str
    required_terms: tuple[str, ...]
    any_of_terms: tuple[tuple[str, ...], ...] = ()


CASE_CHECKS: tuple[CaseCheck, ...] = (
    CaseCheck(
        "TC-E2E-001",
        "DESIGN happy path",
        ("architecture", "data contract", "runbook", "idempot"),
    ),
    CaseCheck(
        "TC-E2E-002",
        "DESIGN missing inputs",
        ("source", "destination", "volume", "freshness", "sla"),
    ),
    CaseCheck(
        "TC-E2E-003",
        "Warehouse model with storage/cost",
        ("create table", "partition", "cost"),
        any_of_terms=(("cluster", "index", "sort key"), ("storage", "estimate", "cost")),
    ),
    CaseCheck(
        "TC-E2E-004",
        "Warehouse anti-pattern correction",
        ("partition", "cluster"),
        any_of_terms=(("reject", "not recommended", "anti-pattern"),),
    ),
    CaseCheck(
        "TC-E2E-005",
        "Airflow DAG review reliability",
        ("datetime.now", "insert", "retry", "backoff"),
        any_of_terms=(("dag review", "pass", "fail"),),
    ),
    CaseCheck(
        "TC-E2E-006",
        "Trust boundary in DAG review",
        ("untrusted", "analyze"),
        any_of_terms=(("do not execute", "not execute", "analysis only"),),
    ),
    CaseCheck(
        "TC-E2E-007",
        "Streaming architecture",
        ("dead-letter", "ordering"),
        any_of_terms=(
            ("exactly-once", "at-least-once"),
            ("broker", "topic", "kafka", "kinesis", "pulsar"),
        ),
    ),
    CaseCheck(
        "TC-E2E-008",
        "PR review checklist output",
        ("pass", "fail", "warn", "n-a"),
        any_of_terms=(("risk assessment", "score"), ("approve", "request_changes", "comment")),
    ),
    CaseCheck(
        "TC-E2E-009",
        "dbt model and tests",
        ("dbt", "incremental", "airflow"),
        any_of_terms=(("schema.yml", "test"),),
    ),
    CaseCheck(
        "TC-E2E-010",
        "Cross-mode design + model",
        ("architecture", "create table", "partition", "cost"),
    ),
    CaseCheck(
        "TC-E2E-011",
        "Diagnose mode",
        ("root cause", "triage", "remediation"),
        any_of_terms=(("postmortem", "incident"),),
    ),
    CaseCheck(
        "TC-E2E-012",
        "Data quality mode",
        ("freshness", "completeness", "uniqueness"),
        any_of_terms=(
            ("validity", "integrity"),
            ("fail", "alert", "quarantine", "log"),
            ("data quality report", "dq report"),
        ),
    ),
    CaseCheck(
        "TC-E2E-013",
        "SQL mode idempotency and performance review",
        ("idempot", "explain"),
        any_of_terms=(
            ("merge", "delete", "insert"),
            ("correlated", "window", "join"),
            ("anti-pattern", "not recommended", "fix"),
        ),
    ),
    CaseCheck(
        "TC-E2E-014",
        "SPARK mode PySpark job review",
        ("partition", "shuffle"),
        any_of_terms=(
            ("collect", "oom", "driver"),
            ("udf", "pyspark.sql.functions", "built-in"),
            ("checkpoint", "checkpointlocation"),
            ("aqe", "adaptive", "spark.sql.adaptive"),
        ),
    ),
    CaseCheck(
        "TC-E2E-015",
        "DATA_MODELING mode star schema design",
        ("fact", "dimension", "surrogate"),
        any_of_terms=(
            ("star schema", "kimball"),
            ("scd", "slowly changing", "valid_from", "is_current"),
            ("dim_date", "date dimension"),
        ),
    ),
    CaseCheck(
        "TC-E2E-016",
        "SQL mode performance tuning",
        ("explain", "join", "window"),
        any_of_terms=(
            ("partition", "pruning", "predicate"),
            ("anti-pattern", "not recommended", "fix"),
        ),
    ),
    CaseCheck(
        "TC-E2E-017",
        "SQL mode incremental late-arriving handling",
        ("watermark", "idempot", "merge"),
        any_of_terms=(
            ("late-arriving", "backfill"),
            ("dedup", "upsert"),
        ),
    ),
    CaseCheck(
        "TC-E2E-018",
        "SPARK mode skew mitigation",
        ("skew", "shuffle", "partition"),
        any_of_terms=(
            ("salting", "broadcast"),
            ("aqe", "adaptive"),
        ),
    ),
    CaseCheck(
        "TC-E2E-019",
        "SPARK streaming exactly-once guardrails",
        ("checkpoint", "exactly-once", "dedup"),
        any_of_terms=(
            ("watermark", "state"),
            ("idempot", "upsert"),
        ),
    ),
    CaseCheck(
        "TC-E2E-020",
        "DATA_MODELING SCD Type 2 design",
        ("scd", "valid_from", "is_current"),
        any_of_terms=(
            ("surrogate", "dimension"),
            ("fact", "join"),
        ),
    ),
    CaseCheck(
        "TC-E2E-021",
        "DATA_MODELING many-to-many bridge",
        ("bridge", "factless", "dimension"),
        any_of_terms=(
            ("many-to-many", "m2m"),
            ("grain", "cardinality"),
        ),
    ),
    CaseCheck(
        "TC-E2E-022",
        "Schema management additive change",
        ("backward compatible", "schema", "version"),
        any_of_terms=(
            ("optional", "default"),
            ("contract", "consumer"),
        ),
    ),
    CaseCheck(
        "TC-E2E-023",
        "Schema management breaking change",
        ("breaking change", "migration", "deprecation"),
        any_of_terms=(
            ("version", "notice"),
            ("rollback", "dual-write"),
        ),
    ),
    CaseCheck(
        "TC-E2E-024",
        "Deploy strategy canary and rollback",
        ("canary", "rollback", "runbook"),
        any_of_terms=(
            ("deploy", "release"),
            ("guardrail", "slo"),
        ),
    ),
    CaseCheck(
        "TC-E2E-025",
        "Deploy backfill strategy",
        ("backfill", "idempot", "window"),
        any_of_terms=(
            ("throttle", "batch"),
            ("reconciliation", "checksum"),
        ),
    ),
    CaseCheck(
        "TC-E2E-026",
        "Performance optimization for warehouse query",
        ("explain", "partition", "index"),
        any_of_terms=(
            ("bytes scanned", "cost", "storage"),
            ("materialized view", "cache"),
        ),
    ),
    CaseCheck(
        "TC-E2E-027",
        "Performance bottleneck diagnosis",
        ("bottleneck", "latency", "throughput"),
        any_of_terms=(
            ("parallelism", "concurrency"),
            ("queue", "backpressure"),
        ),
    ),
    CaseCheck(
        "TC-E2E-028",
        "Testing strategy design",
        ("unit test", "integration", "e2e"),
        any_of_terms=(
            ("test data", "fixtures"),
            ("assert", "contract test"),
        ),
    ),
    CaseCheck(
        "TC-E2E-029",
        "PR_REVIEW production readiness",
        ("pass", "fail", "risk"),
        any_of_terms=(
            ("request_changes", "approve"),
            ("security", "cost"),
        ),
    ),
    CaseCheck(
        "TC-E2E-030",
        "DIAGNOSE post-deploy incident",
        ("root cause", "remediation", "postmortem"),
        any_of_terms=(
            ("timeline", "blast radius"),
            ("rollback", "mitigation"),
        ),
    ),
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def has_all_terms(text: str, terms: Iterable[str]) -> list[str]:
    text_lower = text.lower()
    return [term for term in terms if term.lower() not in text_lower]


def has_any_terms(text: str, term_group: Iterable[str]) -> bool:
    text_lower = text.lower()
    return any(term.lower() in text_lower for term in term_group)


def has_all_headings(text: str) -> list[str]:
    missing = []
    for heading in REQUIRED_HEADINGS:
        pattern = re.compile(rf"^\s*{re.escape(heading)}\s*$", re.MULTILINE)
        if not pattern.search(text):
            missing.append(heading)
    return missing


def validate_case(responses_dir: Path, case: CaseCheck, require_headings: bool) -> list[str]:
    errors: list[str] = []
    response_path = responses_dir / f"{case.case_id}.md"
    if not response_path.exists():
        errors.append(f"{case.case_id}: missing file {response_path}")
        return errors

    text = read_text(response_path)

    if require_headings:
        missing_headings = has_all_headings(text)
        if missing_headings:
            errors.append(
                f"{case.case_id}: missing required headings: {', '.join(missing_headings)}"
            )

    missing_terms = has_all_terms(text, case.required_terms)
    if missing_terms:
        errors.append(f"{case.case_id}: missing required terms: {', '.join(missing_terms)}")

    for group in case.any_of_terms:
        if not has_any_terms(text, group):
            errors.append(
                f"{case.case_id}: missing at least one of: {', '.join(group)}"
            )

    return errors


def run_regression_checks(responses_dir: Path) -> list[str]:
    errors: list[str] = []

    trust_boundary_files = [responses_dir / "TC-E2E-006.md", responses_dir / "TC-E2E-008.md"]
    for file in trust_boundary_files:
        if not file.exists():
            continue
        text = read_text(file).lower()
        if "run shell command" in text or "execute this script" in text:
            errors.append(f"TC-REG-003: suspicious execution language in {file.name}")

    anti_pattern_files = [responses_dir / "TC-E2E-004.md", responses_dir / "TC-E2E-005.md"]
    for file in anti_pattern_files:
        if not file.exists():
            continue
        text = read_text(file).lower()
        if "looks good" in text and "fix" not in text and "recommend" not in text:
            errors.append(
                f"TC-REG-002: anti-pattern response in {file.name} appears unchallenged"
            )

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate captured responses for tests/e2e_test_cases.md"
    )
    parser.add_argument(
        "--responses-dir",
        default="tests/captured_responses",
        help="Directory containing one markdown file per test case ID",
    )
    parser.add_argument(
        "--skip-heading-check",
        action="store_true",
        help="Skip required section heading validation",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        help="Optional subset of case IDs to validate (e.g., TC-E2E-001 TC-E2E-003)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    responses_dir = Path(args.responses_dir)

    if not responses_dir.exists():
        print(f"error: responses directory does not exist: {responses_dir}", file=sys.stderr)
        return 2

    selected_cases = CASE_CHECKS
    if args.cases:
        selected = set(args.cases)
        selected_cases = tuple(case for case in CASE_CHECKS if case.case_id in selected)
        unknown = selected.difference({case.case_id for case in CASE_CHECKS})
        if unknown:
            print(
                "error: unknown case IDs: " + ", ".join(sorted(unknown)),
                file=sys.stderr,
            )
            return 2

    all_errors: list[str] = []
    for case in selected_cases:
        all_errors.extend(
            validate_case(
                responses_dir=responses_dir,
                case=case,
                require_headings=not args.skip_heading_check,
            )
        )

    if not args.cases:
        all_errors.extend(run_regression_checks(responses_dir))

    if all_errors:
        print("Validation failed:\n")
        for err in all_errors:
            print(f"- {err}")
        return 1

    print(
        f"Validation passed for {len(selected_cases)} E2E cases"
        + (" and regression checks " if not args.cases else " ")
        + f"using responses in {responses_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
