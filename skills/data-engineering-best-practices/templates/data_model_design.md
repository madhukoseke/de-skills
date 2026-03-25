---
title: "Data Model Design"
description: "Template for designing and reviewing dimensional models, Data Vault entities, or OBT designs"
tags: [data-modeling, kimball, data-vault, obt, schema, template]
---

# Data Model Design Template

Fill in all sections. Used by DATA_MODELING mode and DESIGN mode. Referenced by `playbooks/09_data_modeling.md`.

---

## Design Summary

**Model name / domain:** <!-- e.g., mart.fact_orders or Orders domain -->
**Modeling paradigm:** <!-- Kimball (star schema) | Data Vault 2.0 | OBT | Medallion/Lakehouse -->
**Layer:** <!-- staging | intermediate | mart | raw_vault | business_vault -->
**Designer:** <!-- Your name -->
**Date:** <!-- YYYY-MM-DD -->
**Data contract version:** <!-- e.g., 1.0.0 -->

---

## Business Requirements

**Primary use cases:**
<!-- Bulleted list of analytics questions this model must answer -->
1.
2.

**Primary consumers:**
<!-- BI tool, downstream dbt models, API, ML feature store -->
1.

**Grain:** <!-- The lowest level of detail — e.g., "one row per order line item" -->

**SLA:** <!-- e.g., data available by 08:00 UTC daily -->

---

## Dimensional Model (Kimball)

*(Fill if paradigm = Kimball; skip otherwise)*

### Fact table

| Column | Type | Description | PK/FK | Additive? |
|--------|------|-------------|-------|-----------|
| | | | | |

**Grain:** <!-- repeat grain statement -->
**Partitioned by:** <!-- e.g., order_date -->

### Dimension tables

| Dimension | Key Columns | SCD Type | Key Attributes |
|-----------|-------------|----------|----------------|
| dim_customers | customer_sk (SK), customer_id (BK) | Type 2 | name, email, tier, country |
| dim_date | date_sk | Type 0 | year, month, quarter, is_weekend |
| | | | |

---

## Data Vault Entities

*(Fill if paradigm = Data Vault 2.0; skip otherwise)*

| Entity Type | Name | Business Key(s) | Source System(s) |
|-------------|------|----------------|-----------------|
| Hub | hub_customer | customer_id | salesforce, erp |
| Link | link_order_customer | order_hk, customer_hk | ecommerce |
| Satellite | sat_customer_details | customer_hk + load_date | salesforce |

---

## Schema Definition

```sql
-- Paste proposed DDL here
```

---

## SCD Design

| Attribute | SCD Type | Rationale |
|-----------|----------|-----------|
| customer_tier | Type 2 | Historical tier affects revenue attribution |
| email | Type 1 | Current value only; history not needed for analytics |
| birth_date | Type 0 | Immutable |

---

## Lineage

```
Sources:
  -
  -

Transformations:
  -

Output:
  -

Downstream consumers:
  -
```

---

## Schema Checklist

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | One grain per table (no mixing) | <!-- PASS / FAIL --> | |
| 2 | Surrogate key defined for all dimension tables | <!-- PASS / FAIL / N-A --> | |
| 3 | Natural/business key preserved for debugging | <!-- PASS / FAIL --> | |
| 4 | Audit columns present (`_loaded_at`, `_source`) | <!-- PASS / FAIL --> | |
| 5 | SCD Type 2 columns present if tracking history | <!-- PASS / FAIL / N-A --> | |
| 6 | Date dimension used (no raw date math in fact joins) | <!-- PASS / FAIL / N-A --> | |
| 7 | Naming follows `snake_case` convention | <!-- PASS / FAIL --> | |
| 8 | Data contract updated with new schema | <!-- PASS / FAIL --> | |
| 9 | Breaking changes follow versioned migration process | <!-- PASS / FAIL / N-A --> | |
| 10 | No EAV or `SELECT *` patterns | <!-- PASS / FAIL --> | |

---

## Estimated Storage

| Table | Rows/day | Retention | Estimated size |
|-------|---------|-----------|----------------|
| | | | |

---

## Recommendation

**Decision:** <!-- APPROVE | REQUEST_CHANGES | COMMENT -->

**Rationale:**

---

## Next Steps

1.
2.
