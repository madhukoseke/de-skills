#!/usr/bin/env python3
"""Validate provider response parsers against recorded fixture payloads."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "benchmark" / "live"))

from providers import anthropic, gemini, openai


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "providers"
FIXTURES = {
    "openai": (FIXTURE_DIR / "openai_response.json", openai.extract_output_text),
    "anthropic": (FIXTURE_DIR / "anthropic_response.json", anthropic.extract_output_text),
    "gemini": (FIXTURE_DIR / "gemini_response.json", gemini.extract_output_text),
}
REQUIRED_MARKERS = (
    "## Summary",
    "## Decision",
    "## Rationale",
    "## Trade-offs",
    "## Next Steps",
)


def main() -> int:
    errors: list[str] = []
    for provider, (path, extractor) in FIXTURES.items():
        if not path.exists():
            errors.append(f"missing fixture: {path.relative_to(ROOT)}")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        text = extractor(payload)
        if not text.strip():
            errors.append(f"{provider}: extractor returned empty text")
            continue
        for marker in REQUIRED_MARKERS:
            if marker not in text:
                errors.append(f"{provider}: parsed fixture missing marker: {marker}")

    if errors:
        print("Provider fixture validation failed.", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Provider fixture validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
