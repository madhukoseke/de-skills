# Streaming and Distributed Systems

Last verified: 2026-08-22. Verify product APIs against official specifications and documentation.

Use this reference for event-driven systems, brokers, stateful processing, CDC streams, and delivery guarantees.

## Prove streaming is required

Quantify the consumer value of latency below the feasible batch interval. Include the cost of always-on compute, state, ordering, schema governance, replay, on-call, and dual batch/stream definitions. If consumers act hourly, a reliable 15-minute micro-batch is usually better than an event-by-event system.

## Define event semantics

Every event contract should state:

- Event identity and business meaning
- Aggregate or ordering key
- Producer timestamp and timezone
- Schema/contract version
- Source transaction or log position when relevant
- Whether the event is a fact, command, snapshot, or change envelope
- Allowed lateness and correction behavior
- PII classification and retention

Events are immutable observations. Corrections should be new events or versioned state transitions, not silent mutation of history.

## Design partitions and ordering

Ordering is normally guaranteed only within a partition. Choose a key that preserves the smallest required ordering scope while distributing peak traffic. Detect hot keys and quantify skew before fixing partition count.

Capacity inputs include peak records/s, peak bytes/s, producer batching, replication, consumer fan-out, retention, partition throughput, recovery catch-up, and reassignment headroom. More partitions increase parallelism but also metadata, open connections, checkpoint state, and rebalancing cost.

## Choose delivery guarantees end to end

- At-most-once accepts loss to avoid duplicates.
- At-least-once is a practical default when consumers are idempotent or version-aware.
- Exactly-once claims are scoped to specific boundaries and failure assumptions; they do not automatically cover external side effects.

Document where acknowledgement occurs and what happens if a process fails immediately before or after it. Use transactional writes, idempotency keys, source offsets stored with sink commits, or deduplication windows as the actual semantics require.

## Handle event time and state

Separate event time from processing time. Define watermark policy from observed lateness distribution and business correction needs. A watermark bounds state and determines when results are considered complete; it does not prove late data never arrives.

When source lateness can exceed a serving-latency SLO, define two SLIs instead of
pretending one clock can satisfy both: acceptance-to-publication latency for valid,
sequence-complete input, and event-time completeness after the allowed-lateness
window. Expose incomplete or provisional state to consumers explicitly.

Stateful jobs need:

- Stable state key and schema
- Checkpoint interval and durable location
- State TTL tied to lateness and business windows
- Upgrade/migration policy
- Restore and rescale test
- Metrics for state size, checkpoint duration/failure, and backpressure

## Design replay and correction

Retain a replayable source long enough for RPO, incident recovery, and model changes—or preserve immutable raw events elsewhere. Version transformation logic and sinks so replay does not mix incompatible results.

Throttle replay against downstream quotas and normal traffic. Reconcile before advancing consumer-visible pointers. For large corrections, write a parallel version and switch atomically rather than mutating live results in place.

## Use dead-letter handling selectively

A dead-letter stream is appropriate when an individual record can be isolated without invalidating the aggregate and when ownership, replay, alerting, retention, and sensitive-data controls exist. Do not use a DLQ to hide systemic contract failures or broken code; stop or quarantine the affected publication boundary instead.

## Observe the stream

Track producer error/latency, broker throughput, partition skew, consumer lag in time and records, watermark delay, out-of-order/late rate, duplicate rate, deserialize failures, state size, checkpoint health, backpressure, sink commit latency, and end-to-end freshness.

Alert from consumer impact and burn rate. A growing backlog with ample freshness budget is not the same incident as low lag with corrupt output.

## Review gate

Require measurable latency value, event contract, ordering scope, peak/catch-up sizing, delivery boundary, late-data policy, replay plan, state restore test, schema compatibility, sensitive-data controls, and end-to-end SLO evidence.
