"""Gemini provider transport for live benchmarking."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from .common import request_json


API_KEY_ENV = "GEMINI_API_KEY"
MODEL_ENV = "GEMINI_MODEL"
DEFAULT_MODEL = ""


def resolve_api_key(explicit: str | None) -> str | None:
    return explicit or os.getenv(API_KEY_ENV)


def resolve_model(explicit: str | None) -> str:
    return explicit or os.getenv(MODEL_ENV) or DEFAULT_MODEL


def extract_output_text(data: dict) -> str:
    chunks: list[str] = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
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
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
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

    data = request_json(req)
    text = extract_output_text(data)
    if not text:
        raise RuntimeError(f"Empty model output for prompt: {user_prompt[:80]}")
    return text
