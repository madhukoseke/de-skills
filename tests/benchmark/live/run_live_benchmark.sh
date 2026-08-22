#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
STAMP="$(date +"%Y%m%d_%H%M%S")"
RUN_DIR="${1:-$ROOT_DIR/tests/benchmark/live_runs/$STAMP}"
RESULTS_DIR="$RUN_DIR/results"
PROVIDER="${BENCHMARK_PROVIDER:-openai}"
DRY_RUN="${BENCHMARK_DRY_RUN:-0}"

mkdir -p "$RUN_DIR" "$RESULTS_DIR"

python3 "$ROOT_DIR/tests/validate_eval_contracts.py"

cmd=(
  python3 "$ROOT_DIR/tests/benchmark/live/run_live_benchmark.py"
  --provider "$PROVIDER"
  --out-dir "$RUN_DIR"
  --prompts-file "$ROOT_DIR/tests/benchmark/contract/v4.json"
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

echo "Live response collection complete for provider '$PROVIDER': $RUN_DIR"
echo "Blind and grade responses, then evaluate JSONL results with score_v4.py."
