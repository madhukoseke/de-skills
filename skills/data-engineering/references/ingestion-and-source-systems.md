# Ingestion and Source Systems

Use this reference for APIs, databases, CDC, event sources, object storage, and partner files.

## Start from source semantics

Inspect how the source represents identity, updates, deletes, transactions, ordering, and time. Record whether reads are snapshots, pages over a changing result set, append-only events, mutable rows, or log positions.

Never infer extraction safety from the connector name. Validate:

- Stable primary or business key
- Update and delete representation
- Source timezone and timestamp precision
- Transaction/snapshot boundary
- Pagination stability and rate limits
- Historical retention and replay availability
- Schema and enum change behavior
- Expected source load and maintenance windows

## Select an extraction pattern

| Source | Default | Use another pattern when |
|---|---|---|
| SaaS/API | Cursor or updated-at incremental with overlap | No stable cursor, hard deletes, or full snapshot is cheaper and safe |
| OLTP database | Incremental query or CDC | Log access, sub-minute latency, deletes, or fan-out justify CDC |
| Files | Manifest-driven immutable landing | Producer overwrites names or cannot supply checksums/manifests |
| Event broker | Consumer groups plus retained replay | Source requires request/response or stateful snapshot bootstrap |
| Small reference data | Versioned full snapshot | Change volume or consumers require row-level history |

Prefer a boring batch pull over CDC when the freshness target allows it and deletes can be reconciled safely.

## Make API ingestion recoverable

- Persist cursor, watermark, page token, and extraction interval with the run record.
- Use a stable sort key and an overlap window for timestamp watermarks; deduplicate by source key and source update version.
- Distinguish retryable timeouts/rate limits from authentication, validation, and permanent not-found failures.
- Honor server retry hints and bound retries by the job’s deadline and side-effect semantics.
- Store response metadata sufficient to prove completeness: request interval, page count, record count, cursor, checksum where feasible.
- Reconcile periodically against source counts or snapshots because an incremental API can omit hard deletes.

## Protect operational databases

- Agree on read replicas, isolation level, indexes, query timeout, batch size, and extraction window with the source owner.
- Avoid unbounded scans, long snapshots, and fan-out queries on primaries.
- For CDC, monitor log retention, connector lag, snapshot progress, schema history, and source storage pressure.
- Capture database position and transaction metadata. Preserve before/after images only as required by downstream semantics and policy.
- Define bootstrap plus catch-up so the snapshot and log stream neither miss nor double-count the boundary.

## Process files as immutable deliveries

Require a manifest when business completeness matters. Include producer, logical dataset, delivery ID, expected files, sizes, checksums, row counts when available, schema/contract version, generation time, and completeness marker.

Land first, validate second, publish third. Do not let discovery of a filename imply that the file is complete. Quarantine malformed deliveries without hiding successfully received raw bytes.

Use content or delivery identity to make reprocessing safe. Define policy for duplicate names with different content.

## Apply CDC correctly

Choose and document:

- Snapshot mode and cutover position
- Key and ordering scope
- Insert/update/delete and tombstone semantics
- DDL compatibility behavior
- Transaction grouping requirements
- Sink application model
- Replay source and retained history

At-least-once capture with an idempotent or version-aware sink is often simpler than end-to-end transactions. A `MERGE` is one possible sink mechanism, not the definition of correctness; append-only versioned history, transactional replacement, and key-constrained inserts can also be correct.

## Validate ingestion

Reconcile at the strongest affordable level:

1. Delivery/file/page counts
2. Source and landed row counts by bounded interval
3. Key coverage and duplicate rate
4. Aggregate totals or checksums by partition
5. Sampled row-level comparison
6. Delete/update propagation

Publish only after the chosen completeness boundary and contract checks pass or after an explicitly documented degraded-mode decision.

## Operational evidence

Emit source position or interval, records and bytes read/written/rejected, API calls and throttles, extraction lag, duplicate rate, schema version, destination commit ID, duration, and run ID. Name the source owner and escalation path in the runbook.
