"""Anthropic provider transport for live benchmarking."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


API_KEY_ENV = "ANTHROPIC_API_KEY"
MODEL_ENV = "ANTHROPIC_MODEL"
DEFAULT_MODEL = ""


def resolve_api_key(explicit: str | None) -> str | None:
    return explicit or os.getenv(API_KEY_ENV)


def resolve_model(explicit: str | None) -> str:
    return explicit or os.getenv(MODEL_ENV, DEFAULT_MODEL)


def extract_output_text(data: dict) -> str:
    chunks: list[str] = []
    for content in data.get("content", []):
        text = content.get("text")
        if isinstance(text, str):
            chunks.append(text)
    return "\n".join(chunks).strip()


def call_model(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int,
    temperature: float,
) -> str:
    payload = {
        "model": model,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": max_output_tokens,
        "temperature": temperature,
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
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc

    text = extract_output_text(data)
    if not text:
        raise RuntimeError(f"Empty model output for prompt: {user_prompt[:80]}")
    return text
