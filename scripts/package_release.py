#!/usr/bin/env python3
"""Package release artifacts for the skill bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "data-engineering-best-practices"
SKILL_MANIFEST = json.loads((SKILL_DIR / "skill.json").read_text(encoding="utf-8"))
DEFAULT_OUT_DIR = ROOT / "release-artifacts"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package release artifacts.")
    parser.add_argument("--version", default=SKILL_MANIFEST["contract_version"])
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    archive_name = f"{SKILL_MANIFEST['skill_name']}-{args.version}.tar.gz"
    archive_path = out_dir / archive_name
    metadata_path = out_dir / f"{SKILL_MANIFEST['skill_name']}-{args.version}.json"

    include_paths = [
        SKILL_DIR / "agents",
        SKILL_DIR / "dist",
        SKILL_DIR / "skill.json",
        SKILL_DIR / "SKILL.md",
    ]

    with tarfile.open(archive_path, "w:gz") as tar:
        for path in include_paths:
            tar.add(path, arcname=path.relative_to(ROOT))

    metadata = {
        "skill_name": SKILL_MANIFEST["skill_name"],
        "contract_version": SKILL_MANIFEST["contract_version"],
        "release_version": args.version,
        "archive": archive_name,
        "archive_sha256": sha256(archive_path),
        "included_paths": [str(path.relative_to(ROOT)) for path in include_paths],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
