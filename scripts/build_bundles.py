#!/usr/bin/env python3
"""Build deterministic, profile-scoped context bundles from the canonical skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "data-engineering"
PROFILES_FILE = ROOT / "integrations" / "profiles.json"
DEFAULT_OUT = ROOT / "dist" / "bundles"


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_profiles() -> dict[str, list[str]]:
    payload = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    if payload.get("skill") != "data-engineering":
        raise SystemExit("profiles.json must target data-engineering")
    return payload["profiles"]


def render(profile: str, references: list[str]) -> str:
    sections = [SKILL_DIR.joinpath("SKILL.md").read_text(encoding="utf-8").rstrip()]
    for name in references:
        path = SKILL_DIR / "references" / f"{name}.md"
        if not path.is_file():
            raise SystemExit(f"profile {profile!r} references missing file: {path}")
        sections.append(f"<!-- reference: {name} -->\n" + path.read_text(encoding="utf-8").rstrip())
    return "\n\n---\n\n".join(sections) + "\n"


def expected(selected: str, out_dir: Path) -> dict[Path, str]:
    profiles = load_profiles()
    if selected != "all" and selected not in profiles:
        raise SystemExit(f"unknown profile {selected!r}; choose one of: {', '.join(profiles)}")
    names = profiles if selected == "all" else {selected: profiles[selected]}
    outputs = {out_dir / f"{name}.txt": render(name, refs) for name, refs in names.items()}
    manifest = {
        "skill": "data-engineering",
        "version": ROOT.joinpath("VERSION").read_text(encoding="utf-8").strip(),
        "profiles": {
            name: {
                "file": f"{name}.txt",
                "references": refs,
                "sha256": digest(outputs[out_dir / f"{name}.txt"]),
            }
            for name, refs in names.items()
        },
    }
    outputs[out_dir / "manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="all")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = expected(args.profile, args.out_dir)
    if args.check:
        drift = [path for path, content in outputs.items() if not path.is_file() or path.read_text(encoding="utf-8") != content]
        if drift:
            for path in drift:
                print(f"stale or missing: {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        print("Bundle artifacts are up to date.")
        return 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"Generated {len(outputs) - 1} bundle profiles in {args.out_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
