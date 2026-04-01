"""OpenAI provider transport for live benchmarking."""

from __future__ import annotations

import json
import os
import urllib.request

from .common import request_json


API_KEY_ENV = "OPENAI_API_KEY"
MODEL_ENV = "OPENAI_MODEL"
DEFAULT_MODEL = "gpt-5"


def resolve_api_key(explicit: str | None) -> str | None:
    return explicit or os.getenv(API_KEY_ENV)


def resolve_model(explicit: str | None) -> str:
    return explicit or os.getenv(MODEL_ENV, DEFAULT_MODEL)


def extract_output_text(data: dict) -> str:
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
    data = request_json(req)
    text = extract_output_text(data)
    if not text:
        raise RuntimeError(f"Empty model output for prompt: {user_prompt[:80]}")
    return text
