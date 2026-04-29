#!/usr/bin/env python3
"""Validate JSON response fixtures against `schemas/skill_response.schema.json`.

Walks `tests/fixtures/**.json` and `tests/captured_responses/**.json` and asserts
each conforms to the optional JSON output contract described in SKILL.md.
Skips files that are not valid JSON (e.g., provider-API payloads under
`tests/fixtures/providers/`) and non-response fixtures whose top level is not an
object — those are out of scope for the response contract.

Exits 0 when no in-scope fixtures are present, so the harness stays usable
before any consumer adopts JSON output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT
    / "skills"
    / "data-engineering-best-practices"
    / "schemas"
    / "skill_response.schema.json"
)
FIXTURE_ROOTS = (
    ROOT / "tests" / "fixtures",
    ROOT / "tests" / "captured_responses",
)
PROVIDER_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "providers"


def is_response_fixture(payload: object) -> bool:
    """Heuristic: a response fixture is a JSON object with at least one of the
    schema's required keys (summary / decision / rationale / nextSteps)."""
    if not isinstance(payload, dict):
        return False
    return any(key in payload for key in ("summary", "decision", "rationale", "nextSteps"))


def collect_candidates() -> list[Path]:
    seen: set[Path] = set()
    candidates: list[Path] = []
    for root in FIXTURE_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            if PROVIDER_FIXTURE_DIR in path.parents:
                continue
            if path in seen:
                continue
            seen.add(path)
            candidates.append(path)
    return candidates


def main() -> int:
    if not SCHEMA_PATH.is_file():
        print(f"ERROR: schema not found at {SCHEMA_PATH.relative_to(ROOT)}", file=sys.stderr)
        return 1

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    candidates = collect_candidates()
    if not candidates:
        print("validate_json_responses: no JSON response fixtures found; skipping.")
        return 0

    errors: list[str] = []
    validated = 0

    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)}: invalid JSON — {exc}")
            continue

        if not is_response_fixture(payload):
            continue

        validation_errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
        if validation_errors:
            for err in validation_errors:
                location = "/".join(str(p) for p in err.absolute_path) or "<root>"
                errors.append(f"{path.relative_to(ROOT)}: {location}: {err.message}")
            continue
        validated += 1

    if errors:
        print("JSON response validation failed.", file=sys.stderr)
        for line in errors:
            print(line, file=sys.stderr)
        return 1

    print(f"validate_json_responses: {validated} fixture(s) validated against schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
