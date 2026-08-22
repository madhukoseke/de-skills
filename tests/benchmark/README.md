# Benchmark v4

The active contract is `contract/v4.json`: 48 scenarios across twelve lifecycle
domains. Each case declares required evidence and forbidden behavior; independent
graders then score ten 1–5 dimensions. `score_v4.py` combines those results with
critical-failure, activation, reference-count, token, and no-skill measurements.

Run the offline contract checks through `../run_e2e_harness.sh`. Live evaluation
must use identical scenario prompts and model snapshots for v6, the archived v5
contract, and no-skill. Randomize labels before independent grading and record
grader calibration. Publish the raw run metadata, exclusions, aggregate scores,
confidence intervals, and unresolved failures.

The historical v3 scripts and captured responses are retained solely to reproduce
the v5 baseline. They are not active v6 quality gates.
