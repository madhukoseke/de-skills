#!/usr/bin/env python3
"""Run live benchmark prompts against the same model with skill on/off."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROMPTS = ROOT / "tests" / "benchmark" / "live" / "prompts_v1.json"
DEFAULT_SKILL_FILE = ROOT / "skills" / "data-engineering-best-practices" / "SKILL.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live skill-vs-no-skill benchmark.")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5"))
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--prompts-file", default=str(DEFAULT_PROMPTS))
    parser.add_argument("--skill-file", default=str(DEFAULT_SKILL_FILE))
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-output-tokens", type=int, default=1400)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--delay-sec", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def output_text_from_response(data: dict) -> str:
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()

    output = data.get("output", [])
    chunks: list[str] = []
    for item in output:
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip()


def call_responses_api(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int,
    temperature: float,
) -> str:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        url="https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc

    text = output_text_from_response(data)
    if not text:
        raise RuntimeError(f"Empty model output for prompt: {user_prompt[:80]}")
    return text


def write_response(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    prompts_file = Path(args.prompts_file)
    skill_file = Path(args.skill_file)
    out_dir = Path(args.out_dir)

    if not prompts_file.exists():
        print(f"error: prompts file missing: {prompts_file}", file=sys.stderr)
        return 2
    if not skill_file.exists():
        print(f"error: skill file missing: {skill_file}", file=sys.stderr)
        return 2
    if not args.dry_run and not args.api_key:
        print("error: OPENAI_API_KEY or --api-key is required for live benchmark.", file=sys.stderr)
        return 2

    prompts = json.loads(prompts_file.read_text(encoding="utf-8"))
    cases = prompts.get("cases", [])
    if not cases:
        print(f"error: no cases in prompts file: {prompts_file}", file=sys.stderr)
        return 2

    skill_text = skill_file.read_text(encoding="utf-8")
    with_skill_system = (
        "You are running with an active benchmark skill contract. "
        "Follow the following skill instructions exactly.\n\n"
        + skill_text
    )
    no_skill_system = (
        "You are a helpful data engineering assistant. "
        "Answer directly and do not assume an external skill contract."
    )

    with_dir = out_dir / "with_skill"
    no_dir = out_dir / "no_skill"
    with_dir.mkdir(parents=True, exist_ok=True)
    no_dir.mkdir(parents=True, exist_ok=True)

    for idx, case in enumerate(cases, start=1):
        case_id = case["case_id"]
        prompt = case["prompt"]
        print(f"[{idx}/{len(cases)}] {case_id}")

        if args.dry_run:
            write_response(with_dir / f"{case_id}.md", f"## Summary\nDRY RUN with skill for {case_id}\n")
            write_response(no_dir / f"{case_id}.md", f"## Summary\nDRY RUN no skill for {case_id}\n")
            continue

        with_resp = call_responses_api(
            api_key=args.api_key,
            model=args.model,
            system_prompt=with_skill_system,
            user_prompt=prompt,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
        )
        no_resp = call_responses_api(
            api_key=args.api_key,
            model=args.model,
            system_prompt=no_skill_system,
            user_prompt=prompt,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
        )

        write_response(with_dir / f"{case_id}.md", with_resp)
        write_response(no_dir / f"{case_id}.md", no_resp)

        if args.delay_sec > 0:
            time.sleep(args.delay_sec)

    metadata = {
        "model": args.model,
        "contract_version": prompts.get("contract_version"),
        "prompts_file": str(prompts_file),
        "skill_file": str(skill_file),
        "case_count": len(cases),
        "dry_run": args.dry_run,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Live benchmark responses written to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
