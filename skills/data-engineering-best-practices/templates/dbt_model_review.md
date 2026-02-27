---
title: "dbt Model Review"
description: "Template for reviewing dbt model quality, tests, cost, and lineage"
tags: [dbt, model-review, template, analytics-engineering]
---

# dbt Model Review Template

Fill in all sections. Used by DBT mode and PR_REVIEW mode. Referenced by `playbooks/06_dbt_patterns.md`.

---

## Review Summary

**Model name:** <!-- e.g., fact_orders -->
**PR / branch:** <!-- Link or branch name -->
**Reviewer:** <!-- Your name -->
**Date:** <!-- YYYY-MM-DD -->
**Layer:** <!-- staging | intermediate | mart -->
**Materialization:** <!-- view | table | incremental | ephemeral | snapshot -->

---

## Checklist

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Uses `ref()` / `source()` — no hardcoded table paths | <!-- PASS / FAIL / WARN / N-A --> | |
| 2 | Column-level tests defined in schema YAML (at minimum: `unique` + `not_null` on PK) | <!-- PASS / FAIL / WARN / N-A --> | |
| 3 | Source freshness configured for any new source | <!-- PASS / FAIL / WARN / N-A --> | |
| 4 | Materialization is appropriate for the layer | <!-- PASS / FAIL / WARN / N-A --> | |
| 5 | Incremental model includes partition filter in `is_incremental()` block | <!-- PASS / FAIL / N-A --> | |
| 6 | `on_schema_change` is set (prefer `append_new_columns`) | <!-- PASS / FAIL / N-A --> | |
| 7 | `unique_key` defined for incremental models | <!-- PASS / FAIL / N-A --> | |
| 8 | No `SELECT *` — explicit column list | <!-- PASS / FAIL / WARN / N-A --> | |
| 9 | No business logic in staging models | <!-- PASS / FAIL / N-A --> | |
| 10 | Model has a description in schema YAML | <!-- PASS / FAIL / WARN --> | |
| 11 | `dbt test` passes in CI | <!-- PASS / FAIL --> | |
| 12 | Data contract updated if mart schema changed | <!-- PASS / FAIL / N-A --> | |
| 13 | No hardcoded project/dataset IDs | <!-- PASS / FAIL --> | |
| 14 | `dbt compile` succeeds without errors | <!-- PASS / FAIL --> | |
| 15 | Column names follow `snake_case` convention | <!-- PASS / FAIL / WARN --> | |

---

## Model Details

### Materialization Config

```
Materialization:
Partition field:
Partition type: (DAY / HOUR / MONTH)
Cluster columns:
Unique key:
on_schema_change:
```

### Source Tables

| Source | Table / Model | Relationship |
|--------|---------------|--------------|
| <!-- `ref('stg_orders')` --> | | |
| <!-- `source('raw', 'customers')` --> | | |

### Output Table

| Field | BQ Dataset | Table Name |
|-------|-----------|------------|
| Destination | | |

### Tests Defined

| Column | Test Type | Severity |
|--------|-----------|----------|
| | `unique` | error |
| | `not_null` | error |
| | | |

---

## Findings

### FAIL Items (must resolve before merge)

<!-- List each FAIL with explanation and suggested fix -->

1.

### WARN Items (should address or document)

<!-- List each WARN with explanation -->

1.

### Suggestions (non-blocking)

<!-- Optional improvements that would not block merge -->

1.

---

## Cost Impact

**Materialization type:** <!-- view | table | incremental -->

For `table` or `incremental` materializations:
- Estimated table size: <!-- e.g., 50 GB -->
- Estimated monthly storage cost: <!-- size * $0.02/GB -->
- Estimated query cost for downstream consumers: <!-- bytes_scanned * $6.25/TB -->

For `incremental` models:
- Estimated rows processed per run: <!-- -->
- Estimated bytes scanned per run (from BQ dry-run): <!-- -->

---

## Lineage

```
Input models / sources:
  -
  -

Output model:
  -

Downstream consumers:
  -
```

---

## Recommendation

<!-- APPROVE | REQUEST_CHANGES | COMMENT -->

**Decision:**

**Rationale:**

---

## Next Steps

1. <!-- Action item for author or reviewer -->
2.
