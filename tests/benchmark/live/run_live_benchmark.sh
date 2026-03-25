#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
STAMP="$(date +"%Y%m%d_%H%M%S")"
RUN_DIR="${1:-$ROOT_DIR/tests/benchmark/live_runs/$STAMP}"
RESULTS_DIR="$RUN_DIR/results"

mkdir -p "$RUN_DIR" "$RESULTS_DIR"

python3 "$ROOT_DIR/tests/benchmark/verify_contract.py"

python3 "$ROOT_DIR/tests/benchmark/live/run_live_benchmark.py" \
  --out-dir "$RUN_DIR" \
  --prompts-file "$ROOT_DIR/tests/benchmark/live/prompts_v1.json"

python3 "$ROOT_DIR/tests/validate_captured_responses.py" \
  --responses-dir "$RUN_DIR/with_skill" \
  > "$RESULTS_DIR/with_skill_validator.txt"
echo $? > "$RESULTS_DIR/with_skill_validator.exit"

set +e
python3 "$ROOT_DIR/tests/validate_captured_responses.py" \
  --responses-dir "$RUN_DIR/no_skill" \
  > "$RESULTS_DIR/no_skill_validator.txt"
NO_SKILL_STATUS=$?
set -e
echo "$NO_SKILL_STATUS" > "$RESULTS_DIR/no_skill_validator.exit"

python3 "$ROOT_DIR/tests/benchmark/compare_skill_vs_no_skill.py" \
  --with-skill-dir "$RUN_DIR/with_skill" \
  --no-skill-dir "$RUN_DIR/no_skill" \
  --output-file "$RESULTS_DIR/comparison.json" \
  --contract-file "$ROOT_DIR/tests/benchmark/contract/v1.json"

python3 "$ROOT_DIR/tests/benchmark/generate_skill_vs_no_skill_report.py" \
  --comparison-file "$RESULTS_DIR/comparison.json" \
  --no-skill-validator-file "$RESULTS_DIR/no_skill_validator.txt" \
  --out-file "$RUN_DIR/skill_vs_no_skill_report.md"

python3 "$ROOT_DIR/tests/benchmark/enforce_quality_gate.py" "$RESULTS_DIR/comparison.json"

echo "Live benchmark complete: $RUN_DIR"
