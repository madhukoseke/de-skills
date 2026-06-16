#!/usr/bin/env python3
"""Validate that release archives include the full skill support surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "data-engineering-best-practices"
VERSION = "release-validation"
EXPECTED_INCLUDED_PATHS = {
    "skills/data-engineering-best-practices/agents",
    "skills/data-engineering-best-practices/dist",
    "skills/data-engineering-best-practices/playbooks",
    "skills/data-engineering-best-practices/templates",
    "skills/data-engineering-best-practices/schemas",
    "skills/data-engineering-best-practices/skill.json",
    "skills/data-engineering-best-practices/SKILL.md",
}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def expected_archive_members() -> set[str]:
    members = {
        "skills/data-engineering-best-practices/SKILL.md",
        "skills/data-engineering-best-practices/skill.json",
    }
    for rel_dir in ("agents", "dist", "playbooks", "templates", "schemas"):
        base = SKILL_DIR / rel_dir
        for path in base.rglob("*"):
            if path.is_file():
                members.add(str(path.relative_to(ROOT)))
    return members


def main() -> int:
    run([sys.executable, "scripts/build_adapters.py"])

    with tempfile.TemporaryDirectory(prefix="de-skills-release-") as tmp:
        out_dir = Path(tmp)
        run(
            [
                sys.executable,
                "scripts/package_release.py",
                "--version",
                VERSION,
                "--out-dir",
                str(out_dir),
            ]
        )

        metadata_path = out_dir / f"data-engineering-best-practices-{VERSION}.json"
        if not metadata_path.exists():
            print(f"ERROR: missing release metadata: {metadata_path}", file=sys.stderr)
            return 1

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        included_paths = set(metadata.get("included_paths", []))
        missing_paths = EXPECTED_INCLUDED_PATHS - included_paths
        if missing_paths:
            print("ERROR: release metadata missing included paths:", file=sys.stderr)
            for path in sorted(missing_paths):
                print(f"- {path}", file=sys.stderr)
            return 1

        archive_path = out_dir / metadata["archive"]
        if not archive_path.exists():
            print(f"ERROR: missing release archive: {archive_path}", file=sys.stderr)
            return 1

        with tarfile.open(archive_path, "r:gz") as archive:
            archive_members = set(archive.getnames())

        missing_members = expected_archive_members() - archive_members
        if missing_members:
            print("ERROR: release archive missing expected files:", file=sys.stderr)
            for path in sorted(missing_members):
                print(f"- {path}", file=sys.stderr)
            return 1

    print("Release package validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
