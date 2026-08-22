# Pipeline Design: {PIPELINE}

## Outcome and ownership

- Consumer/outcome: {CONSUMER_AND_DECISION}
- Owner/on-call: {OWNER}
- Source owner: {SOURCE_OWNER}
- Contract: {CONTRACT_PATH_OR_ID}

## SLO and recovery

| SLI | Target | Measurement point |
|---|---|---|
| Freshness | {TARGET} | {BOUNDARY} |

- RPO/RTO: {VALUES}
- Replay source/window: {SOURCE_AND_RETENTION}

## Data semantics

- Grain/key: {GRAIN_AND_KEY}
- Source update/delete semantics: {SEMANTICS}
- Event/effective/processing time: {TIME_MODEL}
- Write/publication model: {MODEL}

## Architecture and capacity

{Data-flow diagram plus steady, peak, growth, retention, and backfill assumptions.}

## Failure and correction

| Failure | Detection | Containment | Recovery | Proof |
|---|---|---|---|---|
| {Failure} | {Signal} | {Action} | {Replay/repair} | {Reconciliation} |

## Security, cost, and delivery

{Classification, access, retention/deletion, cost envelope, tests, rollout, rollback, and runbook.}
