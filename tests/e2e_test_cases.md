# Behavioral evaluation contract

Benchmark v4 is authoritative:

- `tests/benchmark/contract/v4.json` contains 48 cases across twelve lifecycle domains.
- `tests/evals/trigger_cases.json` contains 40 should-trigger and 40 should-not-trigger prompts.
- `tests/benchmark/score_v4.py` combines deterministic, blinded expert, context,
  token, trigger, critical-failure, and baseline measurements.

Legacy v5 captured responses remain only as a comparison corpus. They are not the
v6 acceptance oracle and are not validated by the offline harness.
