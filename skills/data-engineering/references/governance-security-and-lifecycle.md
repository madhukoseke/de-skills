# Governance, Security, and Data Lifecycle

Last verified: 2026-08-22. Legal requirements vary by jurisdiction; obtain qualified review for binding interpretations.

Use this reference for governance, privacy, security, metadata, master/reference data, retention, deletion, and ownership.

## Classify before distributing

Classify datasets and fields by confidentiality, identifiability, regulatory scope, business criticality, and integrity/availability impact. Classification should drive controls rather than exist only as catalog labels.

At minimum record owner, steward, purpose, lawful/approved use, sensitivity, residency, retention, access policy, masking/tokenization, encryption, audit, deletion path, and downstream restrictions.

## Apply layered access controls

- Authenticate workloads and people with short-lived identity where available.
- Authorize by least privilege and separate read, write, administer, and policy roles.
- Use row/column policies or governed views when subsets differ by role or region.
- Keep secrets and encryption keys outside code and data contracts.
- Log access to sensitive datasets and protect audit logs from tampering.
- Recertify access and remove stale service identities.

Masking is not anonymization. Tokenized, hashed, or redacted data may remain identifiable through linkage or reversibility.

## Minimize data

Collect and retain only fields and history needed for declared purposes. Prefer irreversible aggregation or deletion when detailed data no longer has value. Avoid propagating sensitive columns into every layer “in case they are needed.”

Use safe synthetic or approved masked data in lower environments. Preserve referential and distribution properties required for testing without exposing original values.

## Engineer retention and deletion

Map each contract to business retention, legal hold, regulatory minimum/maximum, backup retention, time travel, caches, extracts, indexes, vector stores, and logs. Automate enforcement and produce evidence.

For subject or entity deletion:

1. Resolve identifiers through an approved identity map.
2. Propagate tombstone/delete intent through every derived system.
3. Prevent deleted data from reappearing during replay/backfill.
4. Handle immutable backups through expiry, key destruction, or documented exception.
5. Verify completion and audit without retaining the deleted sensitive payload.

## Govern metadata and lineage

Keep business definition, technical schema, owner, contract, SLO, classification, lineage, usage, quality, and cost discoverable. Prefer automated runtime metadata plus reviewed business context.

Catalog presence is not ownership. Measure unanswered support requests, stale contracts, unknown consumers, and failed access recertification.

## Manage master and reference data

Define authoritative sources, survivorship, matching, stewardship, versioning, distribution, and correction. Separate globally governed identifiers/definitions from domain-local attributes where appropriate.

Never merge entities solely from fuzzy similarity without confidence thresholds, review paths, and reversibility. Preserve source identifiers and match provenance.

## Govern change

Use contracts and lineage to identify affected consumers before schema, semantic, security, retention, or SLO changes. Record approval and exception expiry for high-risk changes. Security controls should fail closed when bypass would expose restricted data, while non-security metadata gaps may use time-bounded remediation.

## Review gate

Require purpose and owner, field-level classification, least privilege, secrets isolation, encryption, audit, retention/deletion propagation, non-production policy, residency/transfer controls, lineage, consumer impact, and evidence that automated controls actually run.
