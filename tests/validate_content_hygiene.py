#!/usr/bin/env python3
"""Detect local-link drift, duplicated principles, stale sources, and bad absolutes."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "data-engineering"


def main() -> int:
    errors: list[str] = []
    markdown = [SKILL_DIR / "SKILL.md", *SKILL_DIR.joinpath("references").glob("*.md"), *SKILL_DIR.joinpath("assets").glob("*.md")]
    for path in markdown:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#") or target.startswith("mailto:"):
                continue
            local = (path.parent / target.split("#", 1)[0]).resolve()
            if not local.exists():
                errors.append(f"broken local link: {path.relative_to(ROOT)} -> {target}")
    skill = SKILL_DIR.joinpath("SKILL.md").read_text()
    principles = [match.group(1).strip() for match in re.finditer(r"\*\*[GP]\d{3} —[^*]+\.\*\*\s*([^\n]+)", skill)]
    reference_text = "\n".join(path.read_text() for path in SKILL_DIR.joinpath("references").glob("*.md"))
    for principle in principles:
        if len(principle) > 35 and principle in reference_text:
            errors.append(f"principle text duplicated in a reference: {principle[:60]}")
    forbidden = ["every write must use merge", "every large table must be partitioned", "every dq violation must stop", "every external call gets the same retries"]
    lowered = reference_text.lower()
    for phrase in forbidden:
        if phrase in lowered:
            errors.append(f"undocumented absolute found: {phrase}")
    today = dt.date.today()
    dated_files = [path for path in SKILL_DIR.joinpath("references").glob("*.md") if re.search(r"\b(airflow|dagster|dbt|spark|flink|kafka|iceberg|delta lake|hudi)\b", path.read_text(), re.I)]
    for path in dated_files:
        match = re.search(r"Last (?:verified|reviewed):\s*(\d{4}-\d{2}-\d{2})", path.read_text())
        if not match:
            errors.append(f"missing source-review date: {path.relative_to(ROOT)}")
            continue
        age = (today - dt.date.fromisoformat(match.group(1))).days
        if age > 366:
            errors.append(f"stale source-review date ({age} days): {path.relative_to(ROOT)}")
    if errors:
        raise SystemExit("\n".join(errors))
    print("Content hygiene passed: links, principle authority, dates, and absolutes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
