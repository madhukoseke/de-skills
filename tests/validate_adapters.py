#!/usr/bin/env python3
"""Validate adapter manifests and provider scaffolding consistency."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "data-engineering-best-practices"
SKILL_MANIFEST_FILE = SKILL_DIR / "skill.json"
CAPABILITIES_FILE = SKILL_DIR / "agents" / "capabilities.json"
PROVIDER_MATRIX_FILE = ROOT / "tests" / "benchmark" / "live" / "provider_matrix.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    result: dict[str, object] = {}
    current_section: str | None = None

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            continue
        if stripped.startswith("#"):
            continue

        if not raw_line.startswith(" "):
            if not stripped.endswith(":"):
                raise ValueError(
                    f"malformed YAML in {path.relative_to(ROOT)}:{lineno}: expected top-level section"
                )
            current_section = stripped[:-1]
            if not current_section:
                raise ValueError(
                    f"malformed YAML in {path.relative_to(ROOT)}:{lineno}: empty section name"
                )
            result[current_section] = {}
            continue

        if current_section is None:
            raise ValueError(
                f"malformed YAML in {path.relative_to(ROOT)}:{lineno}: nested key before section"
            )
        if not raw_line.startswith("  "):
            raise ValueError(
                f"malformed YAML in {path.relative_to(ROOT)}:{lineno}: nested keys must use two spaces"
            )

        nested = raw_line[2:].strip()
        if ":" not in nested:
            raise ValueError(
                f"malformed YAML in {path.relative_to(ROOT)}:{lineno}: expected key/value pair"
            )
        key, value = nested.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(
                f"malformed YAML in {path.relative_to(ROOT)}:{lineno}: empty key"
            )

        parsed: object
        if value.lower() == "true":
            parsed = True
        elif value.lower() == "false":
            parsed = False
        elif value.startswith('"') and value.endswith('"') and len(value) >= 2:
            parsed = value[1:-1]
        else:
            raise ValueError(
                f"malformed YAML in {path.relative_to(ROOT)}:{lineno}: unsupported scalar value"
            )

        section = result.get(current_section)
        if not isinstance(section, dict):
            raise ValueError(
                f"malformed YAML in {path.relative_to(ROOT)}:{lineno}: section must be a mapping"
            )
        section[key] = parsed

    if not isinstance(result, dict) or not result:
        raise ValueError(f"adapter file must contain a YAML mapping: {path.relative_to(ROOT)}")
    return result


def validate_adapter_yaml(provider: str, path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = load_yaml(path)
    except ValueError as exc:
        return [str(exc)]

    interface = data.get("interface")
    runtime = data.get("runtime")
    policy = data.get("policy")

    if not isinstance(interface, dict):
        errors.append(f"{path.relative_to(ROOT)}: missing top-level 'interface' mapping")
    if not isinstance(runtime, dict):
        errors.append(f"{path.relative_to(ROOT)}: missing top-level 'runtime' mapping")
    if not isinstance(policy, dict):
        errors.append(f"{path.relative_to(ROOT)}: missing top-level 'policy' mapping")

    if isinstance(interface, dict):
        for key in ("display_name", "short_description", "default_prompt"):
            value = interface.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path.relative_to(ROOT)}: interface.{key} must be a non-empty string")
        default_prompt = interface.get("default_prompt", "")
        if isinstance(default_prompt, str) and "$data-engineering-best-practices" not in default_prompt:
            errors.append(f"{path.relative_to(ROOT)}: interface.default_prompt must reference $data-engineering-best-practices")

    if isinstance(runtime, dict):
        runtime_provider = runtime.get("provider")
        if runtime_provider != provider:
            errors.append(f"{path.relative_to(ROOT)}: runtime.provider must be '{provider}'")
        for key in ("prompt_role", "prompt_style"):
            value = runtime.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path.relative_to(ROOT)}: runtime.{key} must be a non-empty string")

    if isinstance(policy, dict):
        if not isinstance(policy.get("allow_implicit_invocation"), bool):
            errors.append(f"{path.relative_to(ROOT)}: policy.allow_implicit_invocation must be boolean")

    return errors


def main() -> int:
    skill_manifest = load_json(SKILL_MANIFEST_FILE)
    capabilities = load_json(CAPABILITIES_FILE)
    provider_matrix = load_json(PROVIDER_MATRIX_FILE)

    supported_providers = skill_manifest["supported_providers"]
    adapter_files = skill_manifest["adapter_files"]
    artifact_files = skill_manifest["generated_artifacts"]
    capability_providers = capabilities["providers"]
    matrix_providers = provider_matrix["providers"]

    errors: list[str] = []

    if sorted(supported_providers) != sorted(capability_providers.keys()):
        errors.append("skill.json supported_providers do not match capabilities.json providers")

    if sorted(supported_providers) != sorted(adapter_files.keys()):
        errors.append("skill.json adapter_files do not match supported_providers")

    if sorted(supported_providers) != sorted(artifact_files.keys()):
        errors.append("skill.json generated_artifacts do not match supported_providers")

    for provider in supported_providers:
        adapter_path = SKILL_DIR / adapter_files[provider]
        artifact_path = SKILL_DIR / artifact_files[provider]
        capability = capability_providers.get(provider)
        if capability is None:
            continue

        if not adapter_path.exists():
            errors.append(f"missing adapter file: {adapter_path.relative_to(ROOT)}")
            continue
        errors.extend(validate_adapter_yaml(provider, adapter_path))

        if not artifact_path.exists():
            errors.append(f"missing generated artifact: {artifact_path.relative_to(ROOT)}")

        if capability["live_benchmark_supported"]:
            if provider not in matrix_providers:
                errors.append(f"live provider missing from provider matrix: {provider}")
            else:
                module_rel = Path(matrix_providers[provider]["module"])
                module_path = ROOT / module_rel
                if not module_path.exists():
                    errors.append(f"missing live provider module: {module_rel}")

    if errors:
        print("Adapter validation failed.", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Adapter validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
