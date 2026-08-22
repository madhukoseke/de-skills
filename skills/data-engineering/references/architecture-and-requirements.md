# Architecture and Requirements

Use this reference for `DESIGN`, architecture review, platform selection, and capacity planning.

## Frame the decision

Define the consumer-visible outcome before drawing components:

| Concern | Required question | Useful measure |
|---|---|---|
| Consumer | Which decision, product, model, or service uses the data? | Named consumer and owner |
| Correctness | Which errors are intolerable, detectable, or repairable? | Reconciliation tolerance, invariant |
| Time | How fresh must data be, and from which clock? | p95 freshness or latency SLO |
| Scale | What are steady, peak, growth, and backfill loads? | rows/s, bytes/day, concurrency |
| Recovery | How much loss and downtime are acceptable? | RPO, RTO, replay window |
| Governance | What sensitivity, retention, residency, and access apply? | Classification and policy IDs |
| Operations | Who owns, deploys, pages, and repairs the system? | Team, runbook, escalation |
| Economics | What budget and marginal cost shape the design? | Cost/run, cost/TB, monthly ceiling |

Do not accept “real time,” “high scale,” or “exactly once” without measurable definitions.

## Choose the processing shape

1. Use a single scheduled batch when the freshness SLO is comfortably longer than source extraction plus processing plus validation.
2. Use micro-batch when consumers need frequent updates but per-event state or response is unnecessary.
3. Use streaming when downstream value depends on event-level latency, continuous state, or immediate reaction.
4. Use CDC for database changes when log access, snapshot semantics, delete handling, and source impact are understood.
5. Add separate speed and batch paths only when one path cannot satisfy both latency and correction needs; prefer one replayable event log and one transformation definition.

Model the latency budget end to end:

`source availability + extraction + queueing + processing + validation + publication <= consumer freshness SLO`

## Design the data flow

For every boundary record:

- Producer and consumer
- Dataset, event, or file identity and grain
- Contract version and compatibility policy
- Delivery and ordering semantics
- Event, ingestion, processing, and publication timestamps
- Quality gate and failure disposition
- Retention and replay source
- Lineage/run identifier

Prefer immutable raw capture when source replay is expensive or impossible. Do not confuse “raw” with ungoverned: apply encryption, access, retention, and inventory from ingestion.

## Size before selecting products

Calculate at least:

- Daily logical bytes = records/day × average serialized bytes
- Peak ingest = average events/s × measured or explicit peak multiplier
- Retained physical bytes = daily logical bytes × retention days × compression factor × replication factor
- Backfill rate = historical bytes / allowed backfill duration
- Concurrent work = scheduled overlap + retry amplification + backfill + interactive demand

Apply headroom explicitly. Start with 30–50% when uncertainty is high, then replace assumptions with measurements. Include metadata, indexes, small-file overhead, checkpoints, replicas, time travel, and failed-attempt cost.

Use `../scripts/estimate_capacity.py` for repeatable arithmetic.

## Compare alternatives

Score meaningful options against weighted requirements rather than listing product features. Include:

- Correctness and semantic fit
- Latency and throughput at peak
- Recovery and replay
- Operational skill and on-call burden
- Security and governance integration
- Interoperability and exit cost
- Total cost at steady state and backfill
- Migration complexity and reversibility

Reject an option when it violates a hard constraint even if its weighted score is high.

## Design failure first

Walk through:

- Source unavailable, rate-limited, or returning partial pages
- Duplicate, late, reordered, malformed, or schema-incompatible input
- Worker crash after side effect but before checkpoint
- Sink unavailable or partially committed
- Bad code or contract deployed
- Backfill overlapping normal processing
- Upstream correction or deletion
- Regional or control-plane outage

For each, define detection, containment, retry or replay, reconciliation, operator action, and proof of recovery.

## Architecture review gate

A design is not ready until it states the consumer and owner, contract and grain, SLO/RPO/RTO, capacity assumptions, normal and failure flows, security classification, cost envelope, validation strategy, rollout, rollback, and decommission path.
