#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
STAMP="$(date +"%Y%m%d_%H%M%S")"
RUN_DIR="${1:-$ROOT_DIR/tests/benchmark/live_runs/$STAMP}"
RESULTS_DIR="$RUN_DIR/results"
PROVIDER="${BENCHMARK_PROVIDER:-openai}"
DRY_RUN="${BENCHMARK_DRY_RUN:-0}"

mkdir -p "$RUN_DIR" "$RESULTS_DIR"

python3 "$ROOT_DIR/tests/benchmark/verify_contract.py"

cmd=(
  python3 "$ROOT_DIR/tests/benchmark/live/run_live_benchmark.py"
  --provider "$PROVIDER"
  --out-dir "$RUN_DIR"
  --prompts-file "$ROOT_DIR/tests/benchmark/live/prompts_v3.json"
)

if [[ -n "${BENCHMARK_MODEL:-}" ]]; then
  cmd+=(--model "$BENCHMARK_MODEL")
fi

if [[ -n "${BENCHMARK_API_KEY:-}" ]]; then
  cmd+=(--api-key "$BENCHMARK_API_KEY")
fi

if [[ "$DRY_RUN" == "1" ]]; then
  cmd+=(--dry-run)
fi

"${cmd[@]}"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Live benchmark dry run complete for provider '$PROVIDER': $RUN_DIR"
  exit 0
fi

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
  --contract-file "$ROOT_DIR/tests/benchmark/contract/v3.json"

python3 "$ROOT_DIR/tests/benchmark/generate_skill_vs_no_skill_report.py" \
  --comparison-file "$RESULTS_DIR/comparison.json" \
  --no-skill-validator-file "$RESULTS_DIR/no_skill_validator.txt" \
  --out-file "$RUN_DIR/skill_vs_no_skill_report.md"

python3 "$ROOT_DIR/tests/benchmark/enforce_quality_gate.py" "$RESULTS_DIR/comparison.json"

echo "Live benchmark complete for provider '$PROVIDER': $RUN_DIR"
