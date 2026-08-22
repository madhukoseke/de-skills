# Orchestration and Delivery

Last verified: 2026-08-22. Check orchestrator syntax and lifecycle policy against official documentation.

Use this reference for Airflow, Dagster, Prefect, schedulers, CI/CD, deployment, backfills, and rollback.

## Keep orchestration declarative

Orchestration should express dependencies, schedules/events, resources, retries, concurrency, SLAs, and observable boundaries. Put business transformations in independently runnable SQL, dbt models, Python modules, or jobs.

Design tasks around independently retryable commits. A task should either produce no published change or a complete, identifiable commit.

## Choose an orchestrator from operating model

Compare scheduling/event needs, asset awareness, dynamic mapping, state model, backfill ergonomics, deployment model, isolation, observability, ecosystem, multi-tenancy, and team skill. Do not migrate orchestrators to solve transformation-code or ownership problems.

For [Apache Airflow](https://airflow.apache.org/docs/), keep DAG import free of network/database work, use logical data intervals rather than wall-clock time, bound sensors/deferrable waits, pool scarce resources, and test DAG loading plus dependency structure.

## Design retries from semantics

Classify failures:

- Transient and retryable: timeout, rate limit, temporary unavailability
- Data/contract: malformed input, missing key, incompatible schema
- Code/configuration: syntax, permissions, missing dependency
- Capacity/quota: memory, concurrency, storage, account quota

Retry only transient operations whose side effects are safe or protected by idempotency/versioning. Use bounded exponential backoff with jitter and a deadline aligned to the SLO. Route permanent failures immediately with actionable evidence.

## Make schedules and backfills compatible

Parameterize reads and writes by logical interval, contract/version, and run identity. Avoid `now()` when the intended value is the scheduled interval. Define how late upstream data reopens or corrects a closed interval.

For a backfill:

1. Freeze code/config/contract versions.
2. Inventory intervals, data volume, quotas, dependencies, and consumer impact.
3. Choose write isolation: parallel target, partition replacement, or versioned commit.
4. Throttle against production headroom.
5. Reconcile each unit and checkpoint progress.
6. Publish/switch only after aggregate reconciliation.
7. Preserve rollback and cleanup evidence.

Use `../assets/backfill-plan.md` for consequential backfills.

## Build a delivery pipeline

Validate in increasing realism:

- Static/schema/format checks
- Unit and contract tests
- Integration tests with bounded services
- Compile/plan/DAG-load checks
- Ephemeral or isolated end-to-end run
- Dry run or shadow output
- Canary by partition, tenant, topic, or consumer
- Reconciliation and SLO observation
- Progressive rollout and automatic/manual rollback

Promote one immutable artifact across environments while supplying environment-specific configuration and credentials externally. “Code-identical” does not mean configuration-identical.

## Define rollback honestly

Code rollback does not undo data already written. Specify separately:

- Compute/orchestrator rollback
- Schema compatibility rollback
- Data restore or forward repair
- Consumer pointer/view switchback
- Reprocessing required after rollback

Prefer expand/migrate/contract for breaking schema changes. Keep old readers/writers until compatibility evidence and the deprecation window complete.

## Observe the control plane

Track queue delay, schedule delay, task/job duration, retries, failure classification, pool/quota saturation, interval coverage, data freshness, publication commit, and backfill progress. Correlate orchestration run ID with transformation and dataset lineage IDs.

## Review gate

Require logical-time correctness, safe side effects, classified retries, bounded concurrency, deployment artifact identity, validation stages, data-aware rollback, backfill plan, alert ownership, and removal/decommission of obsolete schedules.
