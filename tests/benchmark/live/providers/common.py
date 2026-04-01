"""Shared HTTP helpers for live benchmark provider transports."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


def parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        delay = float(value)
    except ValueError:
        return None
    return max(delay, 0.0)


def request_json(req: urllib.request.Request, *, timeout: int = 180) -> dict:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            should_retry = exc.code in RETRYABLE_STATUS_CODES and attempt < MAX_ATTEMPTS
            if should_retry:
                delay = parse_retry_after(exc.headers.get("Retry-After")) or float(2 ** (attempt - 1))
                time.sleep(delay)
                continue
            raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            if attempt < MAX_ATTEMPTS:
                time.sleep(float(2 ** (attempt - 1)))
                continue
            raise RuntimeError(f"Network error: {exc}") from exc

    raise RuntimeError("request_json exhausted retries without returning a response")
