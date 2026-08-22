# Live evaluation

`run_live_benchmark.py` executes benchmark v4 prompts against v6, the immutable
v5 Git baseline, and no skill using the same provider and model. Full Git history
must be available. API keys and model IDs are supplied by
the operator; current examples and verification dates are in
`integrations/providers.yaml`.

Live outputs are evidence inputs, not self-certifying scores. Convert blinded
grader and deterministic results to the JSONL fields accepted by `score_v4.py`,
then compare v6, v5, and no-skill runs. Never commit credentials or raw sensitive
prompt content.
