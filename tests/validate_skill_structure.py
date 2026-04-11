#!/usr/bin/env python3
"""Validate canonical SKILL.md structure: modes, inputs, templates, principles, frontmatter."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "data-engineering-best-practices" / "SKILL.md"
README = ROOT / "README.md"


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_frontmatter(raw: str) -> dict[str, str]:
    if not raw.startswith("---"):
        die("SKILL.md must start with YAML frontmatter (---)")
    m = re.match(r"^---\n(.*?)\n---\n", raw, re.DOTALL)
    if not m:
        die("SKILL.md frontmatter missing closing ---")
    block = m.group(1)
    out: dict[str, str] = {}
    for line in block.splitlines():
        if line.startswith("name:"):
            out["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            out["description"] = line  # multi-line handled loosely below
        elif line.strip().startswith("version:"):
            out["version"] = line.split(":", 1)[1].strip().strip('"')
    if "name" not in out or not out["name"]:
        die("Frontmatter must set non-empty name:")
    if "version" not in out or not out["version"]:
        die("Frontmatter metadata must set version:")
    if "description:" not in block:
        die("Frontmatter must include description:")
    return out


def modes_from_table(raw: str) -> list[str]:
    """Modes declared in the Operating Modes markdown table (| **MODE** |)."""
    in_table = False
    modes: list[str] = []
    for line in raw.splitlines():
        if line.strip().startswith("| Mode |"):
            in_table = True
            continue
        if in_table:
            if not line.strip().startswith("|"):
                break
            if re.match(r"^\|\s*-+", line):
                continue
            m = re.match(r"^\|\s*\*\*([A-Z_]+)\*\*\s*\|", line)
            if m:
                modes.append(m.group(1))
    if not modes:
        die("Could not parse any modes from Operating Modes table")
    return modes


def input_section_modes(raw: str) -> set[str]:
    """Modes that have a ### <MODE> mode subsection under Inputs to Collect."""
    section = False
    modes: set[str] = set()
    for line in raw.splitlines():
        if line.strip() == "## Inputs to Collect":
            section = True
            continue
        if section and line.startswith("## ") and line != "## Inputs to Collect":
            break
        if section:
            m = re.match(r"^### ([A-Z_]+) mode\s*$", line)
            if m:
                modes.add(m.group(1))
    return modes


def principles_from_skill(raw: str) -> int:
    text = raw
    start = text.find("## Non-Negotiable Principles")
    if start == -1:
        die("SKILL.md missing ## Non-Negotiable Principles")
    chunk = text[start : start + 8000]
    return len(re.findall(r"(?m)^\d+\. \*\*", chunk))


def principles_from_readme(raw: str) -> int:
    start = raw.find("## Principles")
    if start == -1:
        die("README.md missing ## Principles")
    chunk = raw[start : start + 4000]
    return len(re.findall(r"(?m)^\d+\. \*\*", chunk))


def template_rows(raw: str) -> list[tuple[str, str]]:
    """List of (template_path, used_by_cell) from Template Index."""
    start = raw.find("## Template Index")
    if start == -1:
        die("SKILL.md missing ## Template Index")
    rest = raw[start:]
    end = rest.find("\n## ", 1)
    chunk = rest if end == -1 else rest[:end]
    rows: list[tuple[str, str]] = []
    for line in chunk.splitlines():
        if "[templates/" not in line or re.match(r"^\|\s*-", line):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        link_cell = parts[2]
        used_by = parts[3]
        m = re.search(r"\(templates/([^)]+)\)", link_cell)
        if not m:
            continue
        path = f"templates/{m.group(1)}"
        rows.append((path, used_by))
    if not rows:
        die("Could not parse Template Index rows")
    return rows


def parse_used_by_modes(cell: str, all_modes: set[str]) -> set[str] | None:
    cell = cell.strip()
    if cell.lower().startswith("all modes"):
        return None
    parts = re.split(r"[,/]", cell)
    out: set[str] = set()
    for p in parts:
        token = p.strip()
        token = re.sub(r"\s*\([^)]*\)\s*", "", token)
        if not token:
            continue
        if token in all_modes:
            out.add(token)
    return out


def main() -> None:
    skill_raw = SKILL.read_text(encoding="utf-8")
    readme_raw = README.read_text(encoding="utf-8")

    fm = parse_frontmatter(skill_raw)
    print(f"Frontmatter OK: name={fm['name']!r} version={fm['version']!r}")

    modes = modes_from_table(skill_raw)
    mode_set = set(modes)
    print(f"Modes from table ({len(modes)}): {', '.join(modes)}")

    input_modes = input_section_modes(skill_raw)
    missing_inputs = mode_set - input_modes
    if missing_inputs:
        die(f"Modes missing '### <MODE> mode' under Inputs to Collect: {sorted(missing_inputs)}")

    extra_inputs = input_modes - mode_set
    if extra_inputs:
        die(f"Input sections for unknown modes: {sorted(extra_inputs)}")

    p_skill = principles_from_skill(skill_raw)
    p_readme = principles_from_readme(readme_raw)
    if p_skill != p_readme:
        die(
            f"Principle count mismatch: SKILL.md has {p_skill} numbered principles, "
            f"README.md has {p_readme}"
        )
    print(f"Principles count OK: {p_skill} (SKILL.md and README.md match)")

    rows = template_rows(skill_raw)
    for path, used_by in rows:
        full = SKILL.parent / path
        if not full.is_file():
            die(f"Template Index references missing file: {path}")

    for path, used_by in rows:
        referenced = parse_used_by_modes(used_by, mode_set)
        if referenced is None:
            continue
        if not referenced:
            unknown = [t.strip() for t in re.split(r"[,/]", used_by) if t.strip()]
            die(
                f"Template {path}: could not map Used By to known modes: {used_by!r} "
                f"(tokens={unknown})"
            )
        bad = referenced - mode_set
        if bad:
            die(f"Template {path}: unknown modes in Used By: {sorted(bad)}")

    print(f"Template Index OK ({len(rows)} templates, Used By modes validated)")
    print("validate_skill_structure: all checks passed")


if __name__ == "__main__":
    main()
