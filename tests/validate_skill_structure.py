#!/usr/bin/env python3
"""Validate v6 package structure and progressive-disclosure invariants."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "data-engineering"
SKILL = SKILL_DIR / "SKILL.md"
EXPECTED_WORKFLOWS = ["GUIDE", "DESIGN", "BUILD", "REVIEW", "OPERATE", "MODERNIZE"]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def frontmatter(raw: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", raw, re.DOTALL)
    if not match:
        fail("SKILL.md needs valid YAML frontmatter")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            fail(f"unsupported multiline frontmatter: {line}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    if set(fields) != {"name", "description"}:
        fail(f"frontmatter fields must be name and description only; got {sorted(fields)}")
    if fields["name"] != SKILL_DIR.name or not re.fullmatch(r"[a-z0-9-]{1,64}", fields["name"]):
        fail("frontmatter name must match skills/data-engineering and specification syntax")
    if not fields["description"] or len(fields["description"]) > 1024:
        fail("description must contain 1..1024 characters")
    return fields


def main() -> int:
    raw = SKILL.read_text(encoding="utf-8")
    fm = frontmatter(raw)
    if len(raw.splitlines()) >= 300:
        fail("SKILL.md must remain below 300 lines")
    if len(re.findall(r"\S+", raw)) >= 4000:
        fail("SKILL.md must remain below 4,000 whitespace-delimited tokens")
    workflows = re.findall(r"^\| `([A-Z]+)` \|", raw, re.MULTILINE)
    if workflows != EXPECTED_WORKFLOWS:
        fail(f"workflow table mismatch: {workflows}")
    for prefix, expected in (("G", 8), ("P", 6)):
        ids = re.findall(rf"\*\*{prefix}(\d{{3}}) —", raw)
        wanted = [f"{value:03d}" for value in range(1, expected + 1)]
        if ids != wanted:
            fail(f"{prefix} IDs must be contiguous: expected {wanted}, got {ids}")
    references = re.findall(r"\]\(references/([a-z0-9-]+\.md)\)", raw)
    if len(references) != 13 or len(set(references)) != 13:
        fail("SKILL.md must directly route exactly 13 unique lifecycle references")
    actual_references = {path.name for path in (SKILL_DIR / "references").glob("*.md")}
    if set(references) != actual_references:
        fail(f"reference index drift: routed={sorted(references)}, actual={sorted(actual_references)}")
    for name in references:
        ref = SKILL_DIR / "references" / name
        lines = ref.read_text(encoding="utf-8").splitlines()
        if len(lines) > 100 and not any(line.strip().lower() == "## contents" for line in lines):
            fail(f"reference over 100 lines requires ## Contents: {name}")
        if re.search(r"\]\((?:\.\./)?references/", ref.read_text(encoding="utf-8")):
            fail(f"references must not create a nested reference graph: {name}")
    assets = set(re.findall(r"\]\(assets/([A-Za-z0-9._-]+)\)", raw))
    missing_assets = [name for name in assets if not (SKILL_DIR / "assets" / name).is_file()]
    if missing_assets:
        fail(f"missing routed assets: {missing_assets}")
    if "playbooks/" in raw or "templates/" in raw or "Operating Modes" in raw:
        fail("v5 vocabulary or paths leaked into canonical contract")
    print(f"Skill structure passed: {fm['name']}, {len(raw.splitlines())} lines, 6 workflows, 13 references.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
