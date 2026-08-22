#!/usr/bin/env python3
"""Build and inspect the v6 release archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT.joinpath("VERSION").read_text().strip()
REQUIRED_PREFIXES = {"skills/data-engineering/SKILL.md", "skills/data-engineering/agents", "skills/data-engineering/references", "skills/data-engineering/assets", "skills/data-engineering/scripts", "integrations", "dist/bundles", "VERSION", "LICENSE", "README.md", "docs/migration-v6.md"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path)
    args = parser.parse_args()
    context = tempfile.TemporaryDirectory(prefix="de-release-") if args.release_dir is None else None
    out = args.release_dir or Path(context.name)
    subprocess.run([sys.executable, "scripts/build_bundles.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "scripts/package_release.py", "--out-dir", str(out)], cwd=ROOT, check=True)
    metadata_path = out / f"data-engineering-{VERSION}.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    archive = out / metadata["archive"]
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != metadata["sha256"]:
        raise SystemExit("release checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="de-release-repeat-") as repeat_dir:
        subprocess.run([sys.executable, "scripts/package_release.py", "--out-dir", repeat_dir], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        repeated = Path(repeat_dir) / archive.name
        if archive.read_bytes() != repeated.read_bytes():
            raise SystemExit("release archive is not reproducible")
    with tarfile.open(archive, "r:gz") as handle:
        members = set(handle.getnames())
    for prefix in REQUIRED_PREFIXES:
        if not any(name == prefix or name.startswith(prefix + "/") for name in members):
            raise SystemExit(f"release is missing {prefix}")
    forbidden = [name for name in members if "data-engineering-best-practices" in name or "/playbooks/" in name or "/templates/" in name]
    if forbidden:
        raise SystemExit(f"v5 paths leaked into release: {forbidden}")
    if context:
        context.cleanup()
    print("Release package validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
