#!/usr/bin/env python3
"""Create a reproducible v6 skill release archive and checksum metadata."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "data-engineering"
DEFAULT_OUT = ROOT / "release-artifacts"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=ROOT.joinpath("VERSION").read_text().strip())
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", args.version):
        parser.error("--version must be semantic version syntax")
    required = [SKILL_DIR / "SKILL.md", SKILL_DIR / "agents", SKILL_DIR / "references", SKILL_DIR / "assets", SKILL_DIR / "scripts", ROOT / "integrations", ROOT / "dist" / "bundles", ROOT / "VERSION", ROOT / "LICENSE", ROOT / "README.md", ROOT / "docs" / "migration-v6.md"]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"missing release inputs: {', '.join(missing)}; run scripts/build_bundles.py")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    archive = args.out_dir / f"data-engineering-{args.version}.tar.gz"
    with archive.open("wb") as raw_archive:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_archive, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path in required:
                    tar.add(path, arcname=path.relative_to(ROOT), filter=_normalized)
    metadata = {
        "skill": "data-engineering",
        "version": args.version,
        "archive": archive.name,
        "sha256": sha256(archive),
        "canonical_path": "skills/data-engineering",
        "included_paths": [str(path.relative_to(ROOT)) for path in required],
    }
    metadata_path = args.out_dir / f"data-engineering-{args.version}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0


def _normalized(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    return info


if __name__ == "__main__":
    raise SystemExit(main())
