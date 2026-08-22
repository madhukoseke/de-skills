# Backfill Plan: {DATA_PRODUCT} {INTERVAL}

## Purpose and authority

- Reason/incident/change: {REASON}
- Owner and approver: {PEOPLE}
- Exact source/target/interval: {SCOPE}
- Frozen code/config/contract versions: {VERSIONS}

## Capacity and isolation

{Bytes/rows, target duration, required rate, quotas, live workload headroom, batching, throttling, and write isolation.}

## Execution

1. Capture baseline counts/aggregates and current publication pointer.
2. Run one bounded canary interval.
3. Reconcile and approve expansion.
4. Process checkpointed batches with stop conditions.
5. Reconcile complete scope and publish/switch atomically.

## Gates

| Gate | Pass condition | Evidence | Approver |
|---|---|---|---|
| Canary | {Condition} | {Artifact} | {Owner} |

## Rollback and cleanup

{Switchback/restore/forward repair, partial output cleanup, checkpoint retention, consumer notification, and final audit.}
