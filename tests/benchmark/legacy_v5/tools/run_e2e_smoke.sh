#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESPONSES_DIR="${1:-$ROOT_DIR/tests/captured_responses}"

python3 "$ROOT_DIR/tests/validate_captured_responses.py" \
  --responses-dir "$RESPONSES_DIR" \
  --cases TC-E2E-001 TC-E2E-003 TC-E2E-005 TC-E2E-007 TC-E2E-012 TC-E2E-013 TC-E2E-018 TC-E2E-024 TC-E2E-026 TC-E2E-030
