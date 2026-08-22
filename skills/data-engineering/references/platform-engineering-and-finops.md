# Platform Engineering, FinOps, and Modernization

Last verified: 2026-08-22. Recheck service capabilities and pricing before a purchase or migration decision.

Use this reference for internal data platforms, self-service, tenancy, infrastructure, cost control, quotas, and modernization.

## Build a paved road, not a mandatory maze

A data platform should reduce repeated cognitive and operational work. Standardize interfaces and evidence:

- Repository/project bootstrap
- Identity, secrets, network, and policy
- Contract and catalog registration
- Deployment and environment promotion
- Observability, lineage, SLO, and cost attribution
- Safe backfill/replay and incident workflow
- Golden examples and escape-hatch process

Measure time to first production dataset, deployment lead time, failed changes, recovery time, policy compliance, platform adoption, and support burden.

## Design tenancy and isolation

Define control-plane and data-plane boundaries, workload identities, network access, compute pools/queues, storage namespaces, quotas, priority, noisy-neighbor protection, and billing attribution. Separate production and non-production blast radii.

Do not solve every team boundary with a separate platform account/project if shared governance and operations become unmanageable. Do not centralize so far that one team can exhaust or alter another team’s workloads.

## Treat infrastructure and policy as code

Version infrastructure, roles, policies, schemas, and deployment configuration. Promote immutable artifacts with environment-specific parameters. Require plan/diff review, policy checks, secrets scanning, drift detection, and rollback/rebuild procedures.

Manual emergency changes need an incident record, expiry, and reconciliation back to code.

## Attribute cost before optimizing

Tag or otherwise map compute, storage, queries, streams, egress, and shared platform cost to team, product, environment, and workload. Allocate shared costs with a transparent rule; do not optimize an unowned bill.

Examine:

- Scanned/shuffled bytes and pruning
- Idle/always-on compute and concurrency shape
- Failed/retried work
- Storage copies, snapshots, time travel, small files, and retention
- Egress and cross-region transfer
- Backfill and development environments
- Reservation/commitment utilization

Optimize unit economics and SLO attainment, not simply monthly spend. A cheaper system that misses critical freshness or consumes excessive engineering time is not cheaper.

## Plan capacity and quotas

Budget normal peak, failure amplification, retries, catch-up, backfill, maintenance, and growth. Monitor headroom and quota saturation. Use workload priorities so recovery and critical publication can proceed during contention.

## Modernize incrementally

Use `../assets/migration-plan.md` and define:

1. Current contracts, consumers, SLOs, costs, incidents, and unsupported risks
2. Target outcomes and explicit non-goals
3. Compatibility and data movement plan
4. Thin vertical pilot with representative scale and failure modes
5. Dual-run/shadow period with independent reconciliation
6. Consumer cutover cohorts and rollback triggers
7. Freeze/retirement criteria, archival, access removal, and cost shutdown

Avoid “lift and shift” that reproduces obsolete operational constraints without benefit, and avoid simultaneous tool, model, ownership, and contract changes unless the risk is intentionally accepted.

## Evaluate build versus buy

Compare differentiated need, integration, compliance, operational staffing, roadmap control, exit/export, variable and fixed cost, and failure ownership. Include migration and decommissioning cost. Prefer managed components for undifferentiated operations when contracts and exit paths remain acceptable.

## Review gate

Require a platform product owner, user journeys, service boundaries, isolation and quotas, policy-as-code, cost attribution, SLOs, escape hatch, migration/reconciliation, decommissioning, and evidence that the paved road is simpler than bypassing it.
