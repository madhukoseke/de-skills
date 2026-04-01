# Live Benchmark (Contract On/Off)

This folder runs a live benchmark using the same prompts and same model in two modes:

1. with canonical contract loaded
2. without contract (generic assistant baseline)

## Inputs

- Prompt suite: `prompts_v2.json`
- Contract source: `skills/data-engineering-best-practices/SKILL.md`
- Contract: `tests/benchmark/contract/v2.json`

## Run

```bash
tests/benchmark/live/run_live_benchmark.sh
```

Requires:
- `OPENAI_API_KEY`
- optional `OPENAI_MODEL` (default: `gpt-5`)
- optional `BENCHMARK_PROVIDER` (default: `openai`)
- optional `BENCHMARK_MODEL` to override the provider-specific model env var
- optional `BENCHMARK_API_KEY` to override the provider-specific API key env var
- optional `BENCHMARK_DRY_RUN=1` to exercise the full wrapper without making API calls

Supported live providers:

- `openai`: set `BENCHMARK_PROVIDER=openai`, `OPENAI_API_KEY`, optionally `OPENAI_MODEL`
- `anthropic`: run `python3 tests/benchmark/live/run_live_benchmark.py --provider anthropic --model <model> --out-dir <dir>` with `ANTHROPIC_API_KEY`
- `gemini`: run `python3 tests/benchmark/live/run_live_benchmark.py --provider gemini --model <model> --out-dir <dir>` with `GEMINI_API_KEY`

Dry-run example:

```bash
BENCHMARK_PROVIDER=anthropic BENCHMARK_MODEL=claude-test BENCHMARK_DRY_RUN=1 \
  tests/benchmark/live/run_live_benchmark.sh
```

Dry-run mode exercises provider selection and artifact wiring, then exits before validator and benchmark scoring.

Provider metadata is versioned in `tests/benchmark/live/provider_matrix.json`.

## Outputs

Per run:

- `tests/benchmark/live_runs/<timestamp>/with_skill/*.md`
- `tests/benchmark/live_runs/<timestamp>/no_skill/*.md`
- `tests/benchmark/live_runs/<timestamp>/results/comparison.json`
- `tests/benchmark/live_runs/<timestamp>/skill_vs_no_skill_report.md`

## Notes

- Use this for real model comparison to reduce synthetic-baseline bias.
- Keep prompts and contract version aligned (`prompts_v2` with `contract/v2.json`).
- Keep provider-specific transport logic out of the contract itself.
