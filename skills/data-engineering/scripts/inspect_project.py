#!/usr/bin/env python3
"""Inventory a data project without importing or executing project code."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".terraform",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}

SIGNALS: dict[str, tuple[str, ...]] = {
    "airflow": ("airflow.cfg", "dags", "airflow"),
    "dagster": ("dagster.yaml", "workspace.yaml", "dagster"),
    "prefect": ("prefect.yaml", "prefect"),
    "dbt": ("dbt_project.yml", "dbt_project.yaml", "profiles.yml"),
    "spark": ("spark-submit", "pyspark", "spark.sql", "build.sbt"),
    "flink": ("flink", "streamenvironment"),
    "kafka": ("kafka", "confluent", "redpanda"),
    "sql": (".sql",),
    "python": ("pyproject.toml", "requirements.txt", "setup.py", ".py"),
    "terraform": (".tf", "terraform.lock.hcl"),
    "docker": ("dockerfile", "compose.yaml", "docker-compose"),
    "iceberg": ("iceberg",),
    "delta": ("delta-spark", "delta.tables", "delta lake"),
    "hudi": ("hudi",),
    "openlineage": ("openlineage",),
}

TEXT_MANIFESTS = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.py",
    "setup.cfg",
    "package.json",
    "build.sbt",
    "pom.xml",
    "dockerfile",
    "compose.yaml",
    "docker-compose.yml",
    "dbt_project.yml",
    "dbt_project.yaml",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="Project directory to inspect")
    parser.add_argument("--max-files", type=int, default=20_000, help="Stop after this many files")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser.parse_args()


def iter_files(root: Path, max_files: int) -> tuple[list[Path], bool]:
    files: list[Path] = []
    truncated = False
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS)
        for name in sorted(names):
            files.append(Path(current) / name)
            if len(files) >= max_files:
                truncated = True
                return files, truncated
    return files, truncated


def readable_manifest_text(path: Path) -> str:
    name = path.name.lower()
    if name not in TEXT_MANIFESTS and path.suffix.lower() not in {".toml", ".yaml", ".yml"}:
        return ""
    try:
        if path.stat().st_size > 1_000_000:
            return ""
        return path.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return ""


def inspect(root: Path, max_files: int) -> dict:
    files, truncated = iter_files(root, max_files)
    relative = [str(path.relative_to(root)) for path in files]
    evidence: dict[str, list[str]] = {key: [] for key in SIGNALS}

    for path, rel in zip(files, relative, strict=True):
        lower_rel = rel.lower()
        manifest_text = readable_manifest_text(path)
        for technology, signals in SIGNALS.items():
            for signal in signals:
                matched = (
                    (signal.startswith(".") and lower_rel.endswith(signal))
                    or signal in lower_rel
                    or (manifest_text and signal in manifest_text)
                )
                if matched:
                    evidence[technology].append(rel)
                    break

    technologies = {
        key: sorted(dict.fromkeys(paths))[:10]
        for key, paths in evidence.items()
        if paths
    }
    return {
        "root": str(root),
        "filesScanned": len(files),
        "truncated": truncated,
        "technologies": technologies,
        "entrypoints": sorted(
            rel
            for rel in relative
            if Path(rel).name.lower()
            in {"dbt_project.yml", "dagster.yaml", "prefect.yaml", "airflow.cfg", "pyproject.toml"}
        ),
        "notes": [
            "Static inventory only; no project code was imported or executed.",
            "Signals are hints and require confirmation from project configuration and runtime evidence.",
        ],
    }


def render_text(result: dict) -> str:
    lines = [
        f"Root: {result['root']}",
        f"Files scanned: {result['filesScanned']}",
        f"Truncated: {result['truncated']}",
        "Technologies:",
    ]
    for technology, paths in result["technologies"].items():
        lines.append(f"- {technology}: {', '.join(paths)}")
    if not result["technologies"]:
        lines.append("- none detected")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.path).resolve()
    if not root.is_dir():
        raise SystemExit(f"error: project directory does not exist: {root}")
    if args.max_files <= 0:
        raise SystemExit("error: --max-files must be positive")
    result = inspect(root, args.max_files)
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
