#!/usr/bin/env python3
"""Parse every YAML/JSON asset and validate shipped JSON schemas."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "skills" / "data-engineering" / "assets"


def main() -> int:
    count = 0
    for path in sorted(ASSETS.iterdir()):
        if path.suffix == ".json":
            payload = json.loads(path.read_text())
            jsonschema.Draft202012Validator.check_schema(payload)
            count += 1
        elif path.suffix in {".yaml", ".yml"}:
            payload = yaml.safe_load(path.read_text())
            if not isinstance(payload, dict):
                raise SystemExit(f"YAML asset must be a mapping: {path.relative_to(ROOT)}")
            count += 1
    if count < 3:
        raise SystemExit("expected at least three machine-readable assets")
    print(f"Parsed and validated {count} machine-readable asset(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
