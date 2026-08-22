#!/usr/bin/env python3
"""Validate an ODCS 3.1.0 contract against the bundled de-skills profile."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEMA = SCRIPT_DIR.parent / "assets" / "data-contract-profile.schema.json"
PLACEHOLDER = re.compile(r"<[^<>]+>")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", help="ODCS YAML contract to validate")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Validation profile schema")
    parser.add_argument("--allow-placeholders", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args()


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read YAML: {exc}") from exc


def find_placeholders(value: Any, location: str = "<root>") -> list[str]:
    found: list[str] = []
    if isinstance(value, str) and PLACEHOLDER.search(value):
        found.append(location)
    elif isinstance(value, dict):
        for key, child in value.items():
            found.extend(find_placeholders(child, f"{location}/{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(find_placeholders(child, f"{location}/{index}"))
    return found


def semantic_checks(contract: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    model_names: set[str] = set()
    for model_index, model in enumerate(contract.get("schema", [])):
        if not isinstance(model, dict):
            continue
        name = model.get("name")
        if name in model_names:
            errors.append(f"schema/{model_index}/name: duplicate model name {name!r}")
        if isinstance(name, str):
            model_names.add(name)
        field_names: set[str] = set()
        primary_keys = 0
        for field_index, field in enumerate(model.get("properties", [])):
            if not isinstance(field, dict):
                continue
            field_name = field.get("name")
            if field_name in field_names:
                errors.append(
                    f"schema/{model_index}/properties/{field_index}/name: duplicate field {field_name!r}"
                )
            if isinstance(field_name, str):
                field_names.add(field_name)
            if field.get("primaryKey") is True:
                primary_keys += 1
        if primary_keys == 0:
            warnings.append(
                f"schema/{model_index}: no primaryKey field; confirm append-only or keyless semantics explicitly"
            )
        if not model.get("dataGranularityDescription"):
            warnings.append(f"schema/{model_index}: dataGranularityDescription is missing")
    if not contract.get("support"):
        warnings.append("support is missing")
    if not contract.get("team"):
        warnings.append("team ownership is missing")
    if not contract.get("servicelevels"):
        warnings.append("servicelevels are missing")
    return errors, warnings


def main() -> int:
    args = parse_args()
    contract_path = Path(args.contract).resolve()
    schema_path = Path(args.schema).resolve()
    result = {"valid": False, "errors": [], "warnings": [], "profile": str(schema_path)}

    try:
        contract = load_yaml(contract_path)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        result["errors"].append(str(exc))
    else:
        if not isinstance(contract, dict):
            result["errors"].append("contract root must be a YAML mapping")
        else:
            validator = jsonschema.Draft202012Validator(schema)
            for error in sorted(validator.iter_errors(contract), key=lambda item: list(item.path)):
                location = "/".join(str(part) for part in error.absolute_path) or "<root>"
                result["errors"].append(f"{location}: {error.message}")
            if not args.allow_placeholders:
                for location in find_placeholders(contract):
                    result["errors"].append(f"{location}: unresolved angle-bracket placeholder")
            semantic_errors, warnings = semantic_checks(contract)
            result["errors"].extend(semantic_errors)
            result["warnings"].extend(warnings)

    result["valid"] = not result["errors"]
    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print("VALID" if result["valid"] else "INVALID")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")
        print("Profile validation is non-normative; the ODCS 3.1.0 specification takes precedence.")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
