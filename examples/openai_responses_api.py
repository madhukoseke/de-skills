#!/usr/bin/env python3
"""Minimal OpenAI Responses API example using the generated contract bundle."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT_FILE = (
    ROOT / "skills" / "data-engineering-best-practices" / "dist" / "openai" / "system_prompt.txt"
)


def main() -> int:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    user_prompt = " ".join(sys.argv[1:]).strip()

    if not api_key:
        print("error: OPENAI_API_KEY is required", file=sys.stderr)
        return 2
    if not model:
        print("error: OPENAI_MODEL is required", file=sys.stderr)
        return 2
    if not user_prompt:
        print("usage: examples/openai_responses_api.py '<prompt>'", file=sys.stderr)
        return 2

    system_prompt = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
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
        "max_output_tokens": 1400,
        "temperature": 0.2,
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
        print(f"error: HTTP {exc.code}: {body}", file=sys.stderr)
        return 1

    output_text = data.get("output_text", "").strip()
    if not output_text:
        chunks: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        output_text = "\n".join(chunks).strip()

    print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
