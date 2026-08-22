#!/usr/bin/env python3
"""Validate explicitly designated v6 result fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "skills" / "data-engineering" / "assets" / "data-engineering-result.schema.json"
FIXTURES = ROOT / "tests" / "fixtures" / "results"


def main() -> int:
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text()))
    files = sorted(FIXTURES.glob("*.json"))
    if not files:
        raise SystemExit("no v6 result fixtures found")
    errors: list[str] = []
    for path in files:
        payload = json.loads(path.read_text())
        for error in validator.iter_errors(payload):
            location = "/".join(map(str, error.absolute_path)) or "<root>"
            errors.append(f"{path.relative_to(ROOT)}:{location}: {error.message}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Validated {len(files)} v6 JSON result fixture(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
