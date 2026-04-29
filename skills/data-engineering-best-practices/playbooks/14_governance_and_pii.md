---
title: "Governance, PII, and Compliance"
description: "Data classification, PII masking, RBAC + RLS + CLS, audit logging, GDPR right-to-erasure, residency, and cross-border transfer"
tags: [governance, pii, gdpr, ccpa, rbac, rls, cls, masking, audit, retention, residency, compliance]
related_templates:
  - ../templates/data_contract.yaml
  - ../templates/incident_postmortem.md
---

# Playbook 14 — Governance, PII, and Compliance

> **Guiding principles:** Schema is a contract (W004). Environments must be code-identical (W010). Test at every layer (W011).
> Governance is not a separate stack you bolt on. It is enforced at the same boundaries as your data contract — every breaking change to access, retention, or PII handling is a contract change.

This playbook covers the governance controls that should run as code alongside your pipelines. Vendor-neutral patterns; specific governance planes (Unity Catalog, Polaris, Snowflake Horizon, BigQuery IAM, OpenMetadata, Atlan) implement most of these the same way under the hood.

---

## 1. Data Classification

Every column and every dataset must carry a classification level. Treat it as required metadata in the data contract.

| Class | Examples | Default handling |
|-------|----------|------------------|
| **Public** | Product catalog, marketing landing pages | No restrictions |
| **Internal** | Aggregated revenue, headcount by region | Authenticated employees |
| **Confidential** | Customer purchase history, employee comp | Need-to-know within company |
| **Restricted** | PII, PHI, payment card data, credentials | Strict need-to-know + audit + masking by default |

### PII subcategory taxonomy

| Subcategory | Examples | Sensitivity | Typical handling |
|-------------|----------|-------------|------------------|
| Direct identifier | name, email, phone, government_id, account_number | Highest | Tokenize at ingest; never raw in mart |
| Quasi-identifier | birth_date, ZIP, gender, employer | High | Mask at staging or apply k-anonymity at mart |
| Sensitive attribute | health condition, sexual orientation, religion, political affiliation | Highest | Encrypt + access-logged |
| Behavioral | clickstream, GPS trace, watch history | Medium-high | Pseudonymize via stable hash |
| Financial | card number, IBAN, balance, transaction_amount | High (PCI scope) | Tokenize; store last-4 only |
| Health (PHI) | diagnoses, prescriptions, lab values | Highest (HIPAA) | Encrypted; access logged; consent-keyed |
| Children's data | any of the above for users <13 (US <16 EU) | Highest (COPPA, GDPR) | Stricter consent + retention rules |

**Rule:** if you can't say which subcategory a column is, treat it as PII — direct identifier — until proven otherwise.

---

## 2. Encoding governance in the data contract

Extend `data_contract.yaml` (template at [`../templates/data_contract.yaml`](../templates/data_contract.yaml)) with retention and governance blocks. The contract becomes the source of truth that policy engines and CI gates consume.

```yaml
# === Schema (existing) ===
schema:
  fields:
    - name: customer_email
      type: VARCHAR
      pii: true
      pii_category: email
      classification: restricted
      tags: [pii, gdpr-art6.1.b]    # legal-basis tagging where applicable

# === Retention ===
retention:
  period_days: 1095                 # default 3 years
  hard_delete_after: 1825           # legal max — 5 years
  legal_hold: false                 # set true only on counsel request
  basis: "contractual; SLA + analytics; reviewed annually"
  deletion_method: "overwrite + vacuum"   # vs soft tombstone

# === Governance ===
governance:
  classification: restricted
  masking_policy: "tokenize_email_v2"     # named policy in your masking layer
  encryption_at_rest: aes-256-gcm-cmek    # vendor key vs CMEK
  encryption_in_transit: tls-1.2-min
  audit_log_dataset: "audit.data_access_log"
  data_residency: "EU"                    # ISO 3166 country or region code
  cross_border_transfer: "none"           # or list adequacy mechanisms (SCCs, BCRs)
  consent_keyed: true                     # row-level consent column required
  consent_column: "consent_lawful_basis"

# === Subject Rights (GDPR / CCPA) ===
subject_rights:
  right_to_erasure: true
  right_to_access: true
  right_to_portability: true
  identifiable_by:                  # which columns make this dataset linkable to a subject
    - customer_id
    - customer_email
  erasure_strategy: "tombstone_and_purge"  # see §6
```

**Rule:** every dataset with `classification: restricted` or any `pii: true` column must have populated `retention` + `governance` + `subject_rights` blocks before it can be promoted past staging.

---

## 3. Masking strategies

Masking is the most-misused tool in the governance kit. Pick the one that matches the consumer's actual need.

| Strategy | Reversible? | Preserves value distribution | Use when |
|----------|:-----------:|:----------------------------:|----------|
| **Redaction** (`***`) | No | No | Logs / dumps; consumer doesn't need the value |
| **Truncation** (last 4 digits) | No | Partial | Customer service; matching but not leaking |
| **Hashing** (SHA-256 + salt) | No | No (cardinality preserved) | Joining across systems without exposing identity |
| **Tokenization** | Yes (with vault) | No | Consumer needs to round-trip; no analytics on the masked value |
| **Format-preserving encryption (FPE)** | Yes (with key) | Yes (length + alphabet) | Legacy systems that validate format |
| **Generalization / k-anonymity** | No | Aggregate | Aggregated marts; ZIP → first 3 digits |
| **Differential privacy noise** | No | Statistical only | Public release of aggregates |
| **Synthetic data** | No | Yes (modeled) | Dev/staging environments — never use raw prod data |

### Where to mask

```
[ Source ] ──▶ raw  ──▶  staging  ──▶  curated  ──▶  mart  ──▶  consumers
                │            │            │            │
              tokenize     hash         generalize    enforce CLS
              direct       quasi-       quasi-        + RLS
              identifiers  identifiers  identifiers   on PII columns
```

**Rule:** mask **as early as possible** for the strongest classification. Direct identifiers tokenized at ingest; quasi-identifiers hashed at staging; generalization at the mart. The mart layer should never need to apply tokenization — that's a sign your raw layer is leaky.

### dbt example: column-level masking via macros

```sql
-- macros/mask_pii.sql
{% macro mask_email(col_name) -%}
  CASE
    WHEN session_user() IN (SELECT username FROM utils.pii_authorized_readers)
      THEN {{ col_name }}
    ELSE CONCAT(SUBSTRING({{ col_name }}, 1, 1), '***@', SPLIT_PART({{ col_name }}, '@', 2))
  END
{%- endmacro %}

-- models/marts/core/dim_customers.sql
SELECT
  customer_id,
  {{ mask_email('email') }} AS email,
  {{ dbt_utils.surrogate_key(['email_lower']) }} AS email_hash_id
FROM {{ ref('stg_customers') }}
```

Most modern warehouses also have native masking policies (Snowflake `MASKING POLICY`, BigQuery dynamic data masking, Databricks Unity Catalog column masks, Redshift dynamic data masking). Prefer warehouse-native when you can — it survives ad-hoc queries that bypass dbt.

---

## 4. Access control: RBAC, RLS, CLS

Three layers, each non-negotiable for any restricted dataset.

### RBAC (role-based, table-level)

```sql
-- Example: vendor-neutral SQL idiom; map to your warehouse's role model
CREATE ROLE pii_analyst;
CREATE ROLE pii_engineer;

GRANT SELECT ON SCHEMA mart.core TO pii_analyst;
GRANT SELECT, INSERT, UPDATE ON SCHEMA staging.core TO pii_engineer;

-- Service identities, not human users, for pipelines
CREATE ROLE pipeline_load_orders;
GRANT INSERT ON TABLE staging.stg_orders TO pipeline_load_orders;
```

**Rules:**
- Service identities authenticate via short-lived tokens (OIDC / IAM federation), not static keys.
- No human user has direct write access to mart tables — only pipeline service identities.
- Role grants are managed in code (Terraform / Pulumi / dbt grants) — never via console.

### RLS (row-level security)

```sql
-- Example pattern: tenant_id-scoped row access
CREATE ROW ACCESS POLICY tenant_isolation
  ON mart.fact_orders
  AS (tenant_id = SESSION_CONTEXT('tenant_id', 'NONE'));

-- Or via authorized views (BigQuery / Postgres)
CREATE VIEW mart.fact_orders_per_tenant AS
SELECT * FROM mart.fact_orders
WHERE tenant_id = current_setting('app.current_tenant');
```

**Rules:**
- Multi-tenant tables MUST have RLS at the warehouse layer, never trust the BI tool to scope.
- `dev` / `staging` row-policies are identical to `prod` — never relax for testing (W010).
- Test row policies in CI with a synthetic tenant matrix.

### CLS (column-level security)

```sql
-- Snowflake-style masking policy applied to multiple tables
CREATE MASKING POLICY pii_email_mask AS (val STRING) RETURNS STRING ->
  CASE
    WHEN CURRENT_ROLE() IN ('PII_ANALYST', 'COMPLIANCE_AUDITOR') THEN val
    ELSE REGEXP_REPLACE(val, '(.)[^@]+(@.*)', '\\1***\\2')
  END;

ALTER TABLE mart.dim_customers MODIFY COLUMN email
  SET MASKING POLICY pii_email_mask;
```

**Rule:** CLS is the **last** layer of defense — assume RBAC will be misconfigured at least once. CLS limits the blast radius.

---

## 5. Audit logging

Every read of a restricted dataset must produce a structured audit log entry. Most warehouses do this natively; the rule is that the log must be **queryable** and **retained**.

```sql
-- Minimum schema for an access-audit log
CREATE TABLE audit.data_access_log (
  event_id          VARCHAR     PRIMARY KEY,
  event_time        TIMESTAMP   NOT NULL,
  actor_principal   VARCHAR     NOT NULL,    -- user or service identity
  actor_ip          VARCHAR,
  query_id          VARCHAR     NOT NULL,
  query_text_hash   VARCHAR     NOT NULL,    -- SHA-256 of normalized SQL
  dataset           VARCHAR     NOT NULL,
  rows_returned     BIGINT,
  bytes_scanned     BIGINT,
  classification    VARCHAR,                  -- restricted / confidential / ...
  pii_columns_read  ARRAY,                    -- list of column names
  consent_check     BOOLEAN
);

-- Retention: keep audit logs at least 1 year; longer if regulated
```

**Rules:**
- Audit log dataset is itself classified `restricted` and read-restricted to compliance roles.
- Audit log is **append-only** — never enable UPDATE/DELETE except by purge job tied to retention policy.
- Quarterly audit: random-sample 20 access events and trace the legal basis for each. If the basis isn't documented in the contract, that's an incident.

---

## 6. Right-to-erasure (GDPR Art. 17 / CCPA §1798.105)

The single hardest governance requirement to retrofit. Bake it in from day one.

### Strategy A: Tombstone-and-purge (recommended for warehouses)

1. **Receive request.** Compliance team posts to a queue with `subject_id`.
2. **Tombstone immediately.** Insert into `audit.erasure_requests`. Soft-delete from all marts: `UPDATE mart.* SET deleted_at = NOW() WHERE customer_id = $1` and `WHERE customer_email = $1`.
3. **Verify completeness.** Run a join across the catalog plane: `SELECT dataset FROM catalog.lineage WHERE identifies($subject_id)`. Every dataset must report tombstoned rows.
4. **Purge after grace window.** After T+30 days (or contractual minimum), run hard-delete: `DELETE FROM raw.* WHERE customer_id = $1`. Vacuum / OPTIMIZE to reclaim storage.
5. **Re-derive marts.** dbt `--full-refresh` of any incremental mart that may have referenced the subject.

### Strategy B: Crypto-erasure (recommended for data lakes / large parquet)

1. Encrypt PII columns with a per-subject key.
2. To erase, **destroy the key**.
3. Cipher text remains in storage but is unrecoverable.

Faster than rewriting petabytes of parquet; works with object-locked / immutable storage. Requires per-subject key management (KMS).

### Pipeline implications

| Pipeline pattern | Erasure considerations |
|------------------|------------------------|
| Append-only event log | Plan for crypto-erasure or full-rewrite — can't selective-delete events without breaking exactly-once invariants |
| SCD Type 2 | Erasure must propagate to *every* historical version; otherwise old `dbt_valid_to` rows leak |
| Backups & DR | Documented exception period; longer than primary, must be enumerated to subject |
| Streaming (Kafka topics) | Use compacted topics + tombstone records; non-compacted topics are not erasable, plan accordingly |
| ML feature stores | Online store: per-subject delete API; offline store: full re-train at next cycle |
| Embedding stores | Vector DB delete by ID + re-index; document the latency |

**Rule:** every data product's runbook must answer "if a subject requests erasure on Monday, by what time on Tuesday is it complete?" If you can't answer in seconds, the system isn't compliant — it's just untested.

---

## 7. Data residency & cross-border transfer

If your contract declares `data_residency: EU` (or any region), the pipeline must enforce it at three layers:

| Layer | Control |
|-------|---------|
| Storage | Bucket / dataset region pinned; geo-redundancy stays in-region |
| Compute | Warehouse / Spark cluster in same region; cross-region reads disabled |
| Transit | Replication to other regions only via documented adequacy mechanism (SCCs, BCRs, adequacy decision) |

Cross-border transfer to a country without an adequacy decision requires either explicit consent (rarely viable for analytics) or contractual safeguards. **Document the legal mechanism in the contract** — if transfer mechanism is `none`, the pipeline must fail-closed any cross-region read.

---

## 8. CI gates that enforce governance

```yaml
# .github/workflows/governance.yml (example, vendor-neutral)
- name: Validate data contracts have required governance fields
  run: |
    python3 tools/validate_contracts.py \
      --require classification \
      --require retention.period_days \
      --require-when 'classification: restricted' subject_rights.right_to_erasure

- name: Validate masking macro coverage
  run: |
    python3 tools/check_pii_masking.py \
      --contracts contracts/ \
      --models dbt/models/marts/

- name: Validate RLS policies committed for multi-tenant tables
  run: |
    python3 tools/check_rls.py --contracts contracts/

- name: Validate dev/staging row-policies match prod
  run: |
    python3 tools/check_environment_parity.py --policies policies/

- name: Validate residency declarations consistent with bucket regions
  run: |
    python3 tools/check_residency.py --contracts contracts/ --terraform infra/
```

These checks should be required PR checks; treat a governance-CI failure with the same urgency as a test failure.

---

## 9. Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Mask only at the BI layer | Anyone with SQL access bypasses it | Mask at warehouse via CLS; BI layer is convenience only |
| One PII boolean, no subcategory | Can't apply differentiated handling | Subcategory taxonomy (§1) — direct vs quasi vs sensitive |
| "We'll do erasure manually" | Won't scale; regulatory deadline missed | Tombstone-and-purge or crypto-erasure as code (§6) |
| Audit log writes are best-effort | Compliance gap; can't prove access denial | Audit-log writes are part of the access path; if they fail, the read fails |
| Restricted dataset has no retention period | Storage grows without bound; legal exposure increases | `retention.period_days` is required; CI fails the merge without it |
| dev/staging uses real PII | A leak in dev is a leak | Synthetic data for non-prod; or row-anonymized snapshots |
| Service identity reused across pipelines | Audit log says "etl_user" — useless | One identity per pipeline; principle of least privilege |
| Masking macro renamed without `versions:` | Old views silently expose unmasked data | Treat masking policies as contracted artifacts; version them like dbt models |
| Cross-border replication "for backup convenience" | Violates residency if not contractually authorized | Backups follow same residency rules; document and enforce |
| Per-environment row policy differences ("dev needs more access") | Drift; W010 violation; the dev shortcut becomes the prod incident | Same row policy in every environment; access differs only via service-identity grants |

---

## Quick Reference Checklist: Governance & PII

Before any dataset with restricted classification or any `pii: true` column reaches production:

- [ ] Classification populated for every column
- [ ] PII subcategory populated for every `pii: true` column
- [ ] Masking strategy chosen per subcategory and applied at the right layer (W004)
- [ ] RBAC at the schema/table level + RLS for multi-tenant + CLS for direct identifiers
- [ ] Audit log dataset configured; access path fails closed if audit write fails
- [ ] Retention `period_days` and `hard_delete_after` set in contract
- [ ] `subject_rights.right_to_erasure` set with a strategy (tombstone-and-purge or crypto-erasure)
- [ ] Erasure runbook tested end-to-end with a synthetic subject in staging
- [ ] Residency declared; storage region, compute region, and transit mechanism aligned
- [ ] dev/staging row-level policies identical to prod (W010); synthetic or anonymized data only
- [ ] Governance CI gates pass on PRs that touch contracts or masking macros
- [ ] Quarterly access audit: random-sample 20 events and verify documented legal basis

See the data contract template at [`../templates/data_contract.yaml`](../templates/data_contract.yaml) and post-incident pattern at [`../templates/incident_postmortem.md`](../templates/incident_postmortem.md).
