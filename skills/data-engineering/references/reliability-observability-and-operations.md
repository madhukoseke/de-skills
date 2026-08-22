# Reliability, Observability, and Operations

Last verified: 2026-08-22. Use current OpenLineage, OpenTelemetry, and platform documentation for implementation syntax.

Use this reference for data SLOs, telemetry, lineage, incidents, recovery, and disaster readiness.

## Define consumer-visible reliability

Choose SLIs from user outcomes:

- Freshness: proportion of expected data available within the target
- Completeness: proportion of expected intervals/records/entities present
- Correctness: proportion satisfying critical invariants or reconciliation
- Availability: proportion of valid requests/queries served within the window
- Latency: proportion of events/requests completed below a threshold

State numerator, denominator, measurement point, exclusions, target, window, and owner. Avoid 100% targets unless the business requirement and architecture truly justify the cost.

Use error-budget burn to prioritize and page. A single threshold breach can create alert fatigue; fast and slow burn windows distinguish acute incidents from gradual degradation.

## Instrument the path

Correlate these planes with dataset, job, run, contract, and code version:

- Metrics: counts, bytes, duration, lag, quality, cost, resource saturation
- Logs: structured diagnostic events without secrets or unnecessary sensitive values
- Traces: cross-service timing and dependency path
- Lineage: inputs, outputs, transformations, schema facets, run events
- Audit: access and administrative actions

Use [OpenLineage spec](https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md?plain=1) for interoperable job/run/dataset lineage when supported and [OpenTelemetry](https://opentelemetry.io/docs/specs/) for telemetry transport. A catalog graph inferred only from SQL text is not proof of what ran.

## Diagnose with evidence

1. State impact, affected consumers, interval, and current SLO burn.
2. Stabilize: stop harmful publication, isolate bad partitions, reduce load, or switch to known-good output.
3. Build a timeline from deploys, config/schema changes, source health, run state, and telemetry.
4. Test competing hypotheses with discriminating evidence.
5. Recover and reconcile before reopening publication.
6. Separate confirmed root cause from contributing factors and unknowns.

Do not label the first correlated change as root cause without a causal mechanism and evidence.

## Design recovery

Define RPO and RTO per consumer/data product, then map them to:

- Replay source and retention
- Checkpoints and commit metadata
- Backup scope and independence
- Restore order and dependency graph
- Regional/control-plane failure behavior
- Capacity for catch-up
- Credentials, keys, catalogs, and infrastructure definitions needed to rebuild

A backup that has not been restored is an assumption. Run restore drills and measure actual RPO/RTO, correctness, access, and consumer reconnection.

## Operate backlogs and degraded modes

Track lag in time, not only record count. Estimate catch-up:

`net catch-up rate = sustainable processing rate - incoming rate`

If net catch-up is non-positive, add safe capacity, reduce input, or change workload before promising recovery. Protect downstream quotas and critical live traffic during replay.

Publish degraded status when data is partial, delayed, or using a fallback. Define which consumers may continue and which must stop.

## Write useful postmortems

Use `../assets/incident-postmortem.md`. Include consumer impact, detection gap, timeline, causal graph, recovery and reconciliation evidence, what helped/hurt, and actions tied to owners and due dates. Prefer systemic controls over reminders to “be careful.”

## Operational readiness gate

Require measurable SLOs, alert-to-action mapping, correlated telemetry/lineage, runbook, replay source, capacity for recovery, backup/restore evidence, incident roles, consumer communication, and periodic retirement of stale alerts and dashboards.
