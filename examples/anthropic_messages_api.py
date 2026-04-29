#!/usr/bin/env python3
"""Minimal Anthropic Messages API example using the generated contract bundle.

Wires up **prompt caching** on the system block: the canonical contract is
~9KB of static text, and re-sending it on every request is wasteful. With
`cache_control: {"type": "ephemeral"}` the second-and-later requests within
the cache TTL pay roughly 10% of the input-token cost for the cached prefix.

Set `ANTHROPIC_PROMPT_CACHING=0` to disable for a baseline comparison.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT_FILE = (
    ROOT / "skills" / "data-engineering-best-practices" / "dist" / "anthropic" / "system_prompt.txt"
)


def main() -> int:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL")
    user_prompt = " ".join(sys.argv[1:]).strip()
    enable_cache = os.getenv("ANTHROPIC_PROMPT_CACHING", "1") != "0"

    if not api_key:
        print("error: ANTHROPIC_API_KEY is required", file=sys.stderr)
        return 2
    if not model:
        print("error: ANTHROPIC_MODEL is required", file=sys.stderr)
        return 2
    if not user_prompt:
        print("usage: examples/anthropic_messages_api.py '<prompt>'", file=sys.stderr)
        return 2

    system_prompt = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")

    if enable_cache:
        system_block: object = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        system_block = system_prompt

    payload = {
        "model": model,
        "system": system_block,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": 1400,
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        url="https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"error: HTTP {exc.code}: {body}", file=sys.stderr)
        return 1

    chunks: list[str] = []
    for content in data.get("content", []):
        text = content.get("text")
        if isinstance(text, str):
            chunks.append(text)
    print("\n".join(chunks).strip())

    usage = data.get("usage") or {}
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_create = usage.get("cache_creation_input_tokens", 0)
    if cache_read or cache_create:
        print(
            f"\n[cache] read={cache_read} created={cache_create} "
            f"input={usage.get('input_tokens', 0)} output={usage.get('output_tokens', 0)}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
