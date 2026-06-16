#!/usr/bin/env python3
"""Run live benchmark prompts against the same model with contract on/off."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from providers import get_provider


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROMPTS = ROOT / "tests" / "benchmark" / "live" / "prompts_v3.json"
DEFAULT_CONTRACT_FILE = ROOT / "skills" / "data-engineering-best-practices" / "SKILL.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live skill-vs-no-skill benchmark.")
    parser.add_argument("--provider", default=os.getenv("BENCHMARK_PROVIDER", "openai"))
    parser.add_argument("--model")
    parser.add_argument("--api-key")
    parser.add_argument("--prompts-file", default=str(DEFAULT_PROMPTS))
    parser.add_argument("--contract-file", default=str(DEFAULT_CONTRACT_FILE))
    parser.add_argument("--skill-file", dest="legacy_skill_file", help=argparse.SUPPRESS)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-output-tokens", type=int, default=1400)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--delay-sec", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N prompts (for scheduled smoke / cost control).",
    )
    return parser.parse_args()


def write_response(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    prompts_file = Path(args.prompts_file)
    contract_file = Path(args.legacy_skill_file or args.contract_file)
    out_dir = Path(args.out_dir)

    try:
        provider = get_provider(args.provider)
    except KeyError:
        print(f"error: unsupported provider: {args.provider}", file=sys.stderr)
        return 2

    model = provider.resolve_model(args.model)
    api_key = provider.resolve_api_key(args.api_key)

    if not prompts_file.exists():
        print(f"error: prompts file missing: {prompts_file}", file=sys.stderr)
        return 2
    if not contract_file.exists():
        print(f"error: contract file missing: {contract_file}", file=sys.stderr)
        return 2
    if not model:
        print(
            f"error: model is required for provider '{args.provider}'. "
            "Pass --model or set the provider-specific model env var.",
            file=sys.stderr,
        )
        return 2
    if not args.dry_run and not api_key:
        print(
            f"error: API key is required for provider '{args.provider}'. "
            "Pass --api-key or set the provider-specific API key env var.",
            file=sys.stderr,
        )
        return 2

    prompts = json.loads(prompts_file.read_text(encoding="utf-8"))
    cases = prompts.get("cases", [])
    if not cases:
        print(f"error: no cases in prompts file: {prompts_file}", file=sys.stderr)
        return 2
    if args.max_cases is not None:
        if args.max_cases < 1:
            print("error: --max-cases must be >= 1", file=sys.stderr)
            return 2
        cases = cases[: args.max_cases]

    contract_text = contract_file.read_text(encoding="utf-8")
    with_skill_system = (
        "You are running with an active benchmark contract. "
        "Follow the following contract instructions exactly.\n\n"
        + contract_text
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

        with_resp = provider.call_model(
            api_key=api_key,
            model=model,
            system_prompt=with_skill_system,
            user_prompt=prompt,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
        )
        no_resp = provider.call_model(
            api_key=api_key,
            model=model,
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
        "model": model,
        "provider": args.provider,
        "contract_version": prompts.get("contract_version"),
        "prompts_file": str(prompts_file),
        "contract_file": str(contract_file),
        "case_count": len(cases),
        "dry_run": args.dry_run,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Live benchmark responses written to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
