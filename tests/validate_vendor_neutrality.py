#!/usr/bin/env python3
"""Validate that canonical skill content stays vendor-neutral."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "data-engineering-best-practices"
CANONICAL_GLOBS = (
    "SKILL.md",
    "playbooks/*.md",
    "templates/*.md",
    "templates/*.yaml",
    "templates/*.yml",
)
FORBIDDEN_PATTERN = re.compile(r"\b(claude|anthropic|openai|codex|chatgpt)\b", re.IGNORECASE)


def canonical_files() -> list[Path]:
    files: list[Path] = []
    for pattern in CANONICAL_GLOBS:
        files.extend(sorted(SKILL_ROOT.glob(pattern)))
    return files


def main() -> int:
    violations: list[str] = []

    for path in canonical_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if FORBIDDEN_PATTERN.search(line):
                rel = path.relative_to(ROOT)
                violations.append(f"{rel}:{lineno}: {line.strip()}")

    if violations:
        print("Canonical skill content must remain vendor-neutral.", file=sys.stderr)
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1

    print("Vendor-neutrality validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
