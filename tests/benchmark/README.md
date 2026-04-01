# Skill vs No-Skill Benchmark

This benchmark compares skill-guided responses with a generic baseline for the same use-case suite in `tests/validate_captured_responses.py` (`CASE_CHECKS`).

## Contract (Locked v2)

- Active contract: `tests/benchmark/contract/v2.json`
- Current contract size: 30 cases (`TC-E2E-001`..`TC-E2E-030`)
- Contract is verified by `tests/benchmark/verify_contract.py`

### Change policy

Contract v2 is immutable for:
- case IDs
- rubric dimensions/weights
- default gate thresholds

If any of the above changes:
1. Create a new contract file (for example `v3.json`)
2. Update scripts/docs to point to the new version
3. Record change in `CHANGELOG.md`

## Local Run (Captured Baseline)

```bash
tests/benchmark/run_skill_vs_no_skill.sh
```

This pipeline runs:
1. contract verification
2. validator checks for `tests/captured_responses` and `tests/benchmark/no_skill`
3. comparison scoring (`comparison.json`)
4. report generation (`skill_vs_no_skill_report.md`)
5. quality gate enforcement

## Live Run (Same Model, Contract On/Off)

Requires the API key and model env vars for the selected provider.

```bash
tests/benchmark/live/run_live_benchmark.sh
```

Common options:

- `BENCHMARK_PROVIDER=openai|anthropic|gemini`
- `BENCHMARK_MODEL=<provider-model>`
- `BENCHMARK_API_KEY=<override-key>`
- `BENCHMARK_DRY_RUN=1`

Outputs are written to:
- `tests/benchmark/live_runs/<timestamp>/with_skill`
- `tests/benchmark/live_runs/<timestamp>/no_skill`
- `tests/benchmark/live_runs/<timestamp>/results/comparison.json`
- `tests/benchmark/live_runs/<timestamp>/skill_vs_no_skill_report.md`

Live prompts are versioned at:
- `tests/benchmark/live/prompts_v2.json`

The live runner uses the canonical contract from `skills/data-engineering-best-practices/SKILL.md` and ships provider-specific transport adapters without changing the benchmark contract.

Provider transport metadata lives in:
- `tests/benchmark/live/provider_matrix.json`
- `tests/benchmark/live/providers/`

## Quality Gate Thresholds

Default thresholds are sourced from contract v2 and can be overridden via env vars:

- `BENCHMARK_MIN_WITH_SKILL_PASS_RATE`
- `BENCHMARK_MIN_WITH_SKILL_REQUIRED_COVERAGE`
- `BENCHMARK_MIN_WITH_SKILL_RUBRIC_TOTAL`
- `BENCHMARK_MIN_RUBRIC_DELTA_VS_BASELINE`

## Rubric (0-5 each, weighted to 100)

Dimensions (v2):
- `correctness`
- `safety`
- `actionability`
- `cost_awareness`
- `testability`
- `formatting_compliance`
- `clarification_quality`
- `prompt_injection_resilience`

Weights are defined in:
- `tests/benchmark/contract/v2.json`
