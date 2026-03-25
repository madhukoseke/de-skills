# Live Benchmark (Skill On/Off)

This folder runs a live benchmark using the same prompts and same model in two modes:

1. with skill contract loaded
2. without skill contract (generic assistant baseline)

## Inputs

- Prompt suite: `prompts_v1.json`
- Skill source: `skills/data-engineering-best-practices/SKILL.md`
- Contract: `tests/benchmark/contract/v1.json`

## Run

```bash
tests/benchmark/live/run_live_benchmark.sh
```

Requires:
- `OPENAI_API_KEY`
- optional `OPENAI_MODEL` (default: `gpt-5`)

## Outputs

Per run:

- `tests/benchmark/live_runs/<timestamp>/with_skill/*.md`
- `tests/benchmark/live_runs/<timestamp>/no_skill/*.md`
- `tests/benchmark/live_runs/<timestamp>/results/comparison.json`
- `tests/benchmark/live_runs/<timestamp>/skill_vs_no_skill_report.md`

## Notes

- Use this for real model comparison to reduce synthetic-baseline bias.
- Keep prompts and contract version aligned (`prompts_v1` with `contract/v1.json`).
