# Contracts, Quality, and Testing

Last verified: 2026-08-22. The bundled contract profile targets ODCS 3.1.0.

Use this reference for data contracts, schema evolution, quality controls, test design, and reconciliation.

## Contract published boundaries

A contract is an agreement between producer and consumers, not a schema dump. Include:

- Identity, purpose, status, version, owner, support
- Logical and physical schema, grain, keys, meanings, time semantics
- Quality properties and enforcement location
- Freshness, availability, correctness, and support objectives
- Security classification, access, retention, deletion, residency
- Source/lineage and authoritative definitions
- Compatibility and deprecation policy
- Infrastructure endpoints without credentials

Use `../assets/data-contract.odcs.yaml` and validate it with `../scripts/validate_contract.py`.

## Classify changes by consumer impact

Evaluate more than syntax:

- Additive optional fields may still break positional readers, strict serializers, `SELECT *`, or cost assumptions.
- Renames/removals, narrowed types, key/grain changes, semantic changes, timezone changes, reduced history, and stricter nullability are usually breaking.
- Widened types may be technically compatible but break precision or downstream tools.
- Quality/SLO/security changes can be contract changes even when schema is unchanged.

For breaking changes, publish a new version, identify consumers through runtime/catalog evidence, provide a dual-read or dual-write window where appropriate, reconcile old and new, communicate a deadline, and verify retirement.

## Place quality controls by consequence

| Failure consequence | Default disposition |
|---|---|
| Corrupts critical aggregate or regulated output | Stop publication and page according to SLO |
| Isolatable bad records with valid remainder | Quarantine records, publish explicit degraded status |
| Early warning with no current consumer impact | Alert/ticket with trend and owner |
| Informational profiling | Record metric; do not page |

Quality dimensions include completeness, uniqueness, validity, consistency, referential integrity, freshness, volume, distribution, and reconciliation. Define thresholds from business tolerance and observed variability—not round numbers copied from another table.

## Test behavior at the right layer

- Unit: pure transformation and edge cases
- Contract: producer/consumer compatibility and boundary schema
- Integration: actual database, object store, broker, or realistic compatible substitute
- End to end: deployment package, orchestration, state, and publication path on bounded data
- Operational: replay, backfill, rollback, restore, rate limit, and degraded dependency

Test the negative path. A pipeline that produces expected rows once has not proven retry, partial failure, duplicate, late data, deletion, or correction behavior.

## Reconcile independently

Use controls that do not repeat the same bug as the transformation:

1. Source/destination counts by closed interval
2. Key coverage and duplicate comparison
3. Independent aggregates for money or other critical measures
4. Hash/checksum by partition or key range
5. Sampled record comparison with stratification
6. Delete and update propagation
7. Consumer-visible query or API validation

Record reconciliation inputs, query/code version, tolerance, result, and disposition. Define who can waive a failure and for how long.

## Test incremental and historical behavior

Cover empty target, initial load, no-op rerun, update, duplicate input, late event, hard delete, schema addition, interruption before/after commit, overlapping schedules, backfill overlapping normal runs, and full rebuild.

Use production-shaped synthetic or masked data. Do not copy sensitive production data into lower environments without policy and controls.

## Review gate

Require a named owner and consumers, explicit grain/keys/semantics, compatible change classification, risk-based quality dispositions, tests for state and failure, independent reconciliation, and evidence that contract validation passes.
