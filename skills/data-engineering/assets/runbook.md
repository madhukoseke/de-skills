# Runbook: {DATA_PRODUCT_OR_PIPELINE}

## Service facts

- Owner/on-call: {OWNER}
- Consumers and SLO: {LINKS}
- Contract/catalog/lineage: {LINKS}
- Source and output: {IDENTIFIERS}
- Deploy/code version lookup: {METHOD}

## Triage

1. Confirm consumer impact and affected interval.
2. Check current publication pointer/commit and stop harmful publication if needed.
3. Inspect source health, queue/orchestrator state, transformation, quality, and sink.
4. Correlate deploy/config/schema changes with run and lineage IDs.

## Known symptoms

| Symptom | Evidence to collect | Safe mitigation | Escalate to |
|---|---|---|---|
| {Symptom} | {Metrics/log/query} | {Action} | {Owner} |

## Recovery and validation

{Replay/backfill command or workflow, throttles, checkpoints, reconciliation, consumer notification, and rollback.}

## Safety

{Approval-required actions, exact targets, data repair constraints, credentials, and stop conditions.}
