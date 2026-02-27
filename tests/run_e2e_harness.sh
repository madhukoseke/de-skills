#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESPONSES_DIR="${1:-$ROOT_DIR/tests/captured_responses}"

python3 "$ROOT_DIR/tests/validate_captured_responses.py" --responses-dir "$RESPONSES_DIR"
