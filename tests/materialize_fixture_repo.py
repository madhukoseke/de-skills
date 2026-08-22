#!/usr/bin/env python3
"""Copy a benchmark repository fixture to an isolated temporary workspace."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "repositories"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    manifest = json.loads(FIXTURES.joinpath("repo_cases.json").read_text())
    case = next((item for item in manifest["cases"] if item["id"] == args.case_id), None)
    if case is None:
        raise SystemExit(f"unknown repository case: {args.case_id}")
    destination = args.destination or Path(tempfile.mkdtemp(prefix=f"de-{args.case_id.lower()}-"))
    if destination.exists() and any(destination.iterdir()):
        raise SystemExit(f"destination must be absent or empty: {destination}")
    shutil.copytree(FIXTURES / case["fixture"], destination, dirs_exist_ok=True)
    print(json.dumps({"case": case, "workspace": str(destination)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
