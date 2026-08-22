#!/usr/bin/env python3
"""Validate the thin product adapter and dated integration metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    adapter = yaml.safe_load(ROOT.joinpath("skills/data-engineering/agents/openai.yaml").read_text())
    interface = adapter.get("interface", {})
    short = interface.get("short_description", "")
    if not 25 <= len(short) <= 64:
        raise SystemExit("openai short_description must be 25..64 characters")
    if "$data-engineering" not in interface.get("default_prompt", ""):
        raise SystemExit("openai default_prompt must reference $data-engineering")
    if adapter.get("policy", {}).get("allow_implicit_invocation") is not True:
        raise SystemExit("allow_implicit_invocation must be true")
    providers = yaml.safe_load(ROOT.joinpath("integrations/providers.yaml").read_text())
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(providers.get("last_verified", ""))):
        raise SystemExit("provider notes require a verification date")
    profiles = json.loads(ROOT.joinpath("integrations/profiles.json").read_text())
    if profiles.get("skill") != "data-engineering" or "core" not in profiles["profiles"] or "full" not in profiles["profiles"]:
        raise SystemExit("integration profiles are incomplete")
    print("Adapter and integration metadata validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
