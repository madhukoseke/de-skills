#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RESULTS_DIR="$ROOT_DIR/tests/benchmark/results"

mkdir -p "$RESULTS_DIR"

python3 "$ROOT_DIR/tests/benchmark/verify_contract.py"

python3 "$ROOT_DIR/tests/validate_captured_responses.py" \
  --responses-dir "$ROOT_DIR/tests/captured_responses" \
  > "$RESULTS_DIR/with_skill_validator.txt"
echo $? > "$RESULTS_DIR/with_skill_validator.exit"

set +e
python3 "$ROOT_DIR/tests/validate_captured_responses.py" \
  --responses-dir "$ROOT_DIR/tests/benchmark/no_skill" \
  > "$RESULTS_DIR/no_skill_validator.txt"
NO_SKILL_STATUS=$?
set -e
echo "$NO_SKILL_STATUS" > "$RESULTS_DIR/no_skill_validator.exit"

python3 "$ROOT_DIR/tests/benchmark/compare_skill_vs_no_skill.py" \
  --with-skill-dir "$ROOT_DIR/tests/captured_responses" \
  --no-skill-dir "$ROOT_DIR/tests/benchmark/no_skill" \
  --output-file "$RESULTS_DIR/comparison.json" \
  --contract-file "$ROOT_DIR/tests/benchmark/contract/v1.json"

python3 "$ROOT_DIR/tests/benchmark/generate_skill_vs_no_skill_report.py"
python3 "$ROOT_DIR/tests/benchmark/enforce_quality_gate.py" "$RESULTS_DIR/comparison.json"
