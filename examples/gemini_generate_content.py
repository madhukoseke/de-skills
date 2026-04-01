#!/usr/bin/env python3
"""Minimal Gemini GenerateContent API example using the generated contract bundle."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT_FILE = (
    ROOT / "skills" / "data-engineering-best-practices" / "dist" / "gemini" / "system_prompt.txt"
)


def main() -> int:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL")
    user_prompt = " ".join(sys.argv[1:]).strip()

    if not api_key:
        print("error: GEMINI_API_KEY is required", file=sys.stderr)
        return 2
    if not model:
        print("error: GEMINI_MODEL is required", file=sys.stderr)
        return 2
    if not user_prompt:
        print("usage: examples/gemini_generate_content.py '<prompt>'", file=sys.stderr)
        return 2

    system_prompt = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
    payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1400,
        },
    }

    encoded_key = urllib.parse.quote(api_key, safe="")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={encoded_key}"
    )
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
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
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)
    print("\n".join(chunks).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
