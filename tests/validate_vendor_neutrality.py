#!/usr/bin/env python3
"""Keep stable skill behavior neutral while allowing dated technology references."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "data-engineering"
AI_PROVIDER = re.compile(r"\b(openai|anthropic|claude|chatgpt|codex|gemini api)\b", re.I)
UNDATED_PRODUCT = re.compile(r"\b(airflow|dagster|dbt|spark|flink|kafka|snowflake|bigquery|databricks|redshift)\b", re.I)


def main() -> int:
    errors: list[str] = []
    files = [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]
    for path in files:
        text = path.read_text(encoding="utf-8")
        if AI_PROVIDER.search(text):
            errors.append(f"AI-provider behavior leaked into canonical content: {path.relative_to(ROOT)}")
        if path.name != "SKILL.md" and UNDATED_PRODUCT.search(text) and not re.search(r"Last verified:\s*\d{4}-\d{2}-\d{2}", text):
            errors.append(f"technology-specific reference lacks Last verified date: {path.relative_to(ROOT)}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Vendor neutrality and dated-product guidance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
