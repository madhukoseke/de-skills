#!/usr/bin/env python3
"""Build provider-specific adapter artifacts from the canonical skill contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "data-engineering-best-practices"
SKILL_MANIFEST_FILE = SKILL_DIR / "skill.json"
CAPABILITIES_FILE = SKILL_DIR / "agents" / "capabilities.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_skill_text(skill_manifest: dict) -> str:
    canonical_file = SKILL_DIR / skill_manifest["canonical_instruction_file"]
    return canonical_file.read_text(encoding="utf-8").rstrip() + "\n"


def canonical_skill_hash(skill_text: str) -> str:
    return hashlib.sha256(skill_text.encode("utf-8")).hexdigest()


def provider_preamble(provider_meta: dict) -> str:
    provider_label = provider_meta["display_name"]
    prompt_channel = provider_meta["prompt_channel"]
    api_family = provider_meta["api_family"]
    return (
        f"You are running with the Data Engineering Best Practices contract on the "
        f"{provider_label} runtime.\n"
        f"Apply the contract below as the authoritative instruction set.\n"
        f"Prompt channel: {prompt_channel}\n"
        f"API family: {api_family}\n"
        f"Preserve clarification behavior, safety boundaries, and output format requirements.\n"
    )


def render_system_prompt(provider_meta: dict, skill_text: str) -> str:
    preamble = provider_preamble(provider_meta)
    return f"{preamble}\n<skill_contract>\n{skill_text}</skill_contract>\n"


def render_metadata(
    provider_name: str,
    provider_meta: dict,
    skill_manifest: dict,
    skill_hash: str,
) -> str:
    payload = {
        "skill_name": skill_manifest["skill_name"],
        "contract_version": skill_manifest["contract_version"],
        "provider": provider_name,
        "provider_display_name": provider_meta["display_name"],
        "adapter_file": provider_meta["adapter_file"],
        "prompt_channel": provider_meta["prompt_channel"],
        "api_family": provider_meta["api_family"],
        "live_benchmark_supported": provider_meta["live_benchmark_supported"],
        "canonical_instruction_file": skill_manifest["canonical_instruction_file"],
        "canonical_instruction_sha256": skill_hash,
    }
    optimization = provider_meta.get("optimization")
    if optimization:
        payload["optimization"] = optimization
    return json.dumps(payload, indent=2) + "\n"


def render_adapter_index(skill_manifest: dict, capabilities: dict, skill_hash: str) -> str:
    payload = {
        "skill_name": skill_manifest["skill_name"],
        "contract_version": skill_manifest["contract_version"],
        "canonical_instruction_file": skill_manifest["canonical_instruction_file"],
        "canonical_instruction_sha256": skill_hash,
        "providers": {},
    }
    for provider_name, provider_meta in capabilities["providers"].items():
        payload["providers"][provider_name] = {
            "adapter_file": provider_meta["adapter_file"],
            "build_output_dir": provider_meta["build_output_dir"],
            "live_benchmark_supported": provider_meta["live_benchmark_supported"],
        }
    return json.dumps(payload, indent=2) + "\n"


def expected_outputs() -> dict[Path, str]:
    skill_manifest = load_json(SKILL_MANIFEST_FILE)
    capabilities = load_json(CAPABILITIES_FILE)
    skill_text = canonical_skill_text(skill_manifest)
    skill_hash = canonical_skill_hash(skill_text)

    outputs: dict[Path, str] = {}
    for provider_name, provider_meta in capabilities["providers"].items():
        output_dir = SKILL_DIR / provider_meta["build_output_dir"]
        outputs[output_dir / "system_prompt.txt"] = render_system_prompt(provider_meta, skill_text)
        outputs[output_dir / "metadata.json"] = render_metadata(
            provider_name, provider_meta, skill_manifest, skill_hash
        )

    outputs[SKILL_DIR / "dist" / "adapter_index.json"] = render_adapter_index(
        skill_manifest, capabilities, skill_hash
    )
    return outputs


def write_outputs(outputs: dict[Path, str]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_outputs(outputs: dict[Path, str]) -> list[str]:
    errors: list[str] = []
    for path, expected in outputs.items():
        if not path.exists():
            errors.append(f"missing generated file: {path.relative_to(ROOT)}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(f"stale generated file: {path.relative_to(ROOT)}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build provider adapter artifacts.")
    parser.add_argument("--check", action="store_true", help="Verify generated files are up to date.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = expected_outputs()

    if args.check:
        errors = check_outputs(outputs)
        if errors:
            print("Adapter artifact drift detected.", file=sys.stderr)
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("Adapter artifacts are up to date.")
        return 0

    write_outputs(outputs)
    print(f"Generated {len(outputs)} adapter artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
