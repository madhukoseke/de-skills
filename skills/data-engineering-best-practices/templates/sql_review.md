---
title: "SQL Review"
description: "Template for reviewing SQL queries and DML scripts for correctness, idempotency, performance, and dialect portability"
tags: [sql, review, template, idempotency, performance]
---

# SQL Review Template

Fill in all sections. Used by SQL mode and PR_REVIEW mode. Referenced by `playbooks/07_sql_patterns.md`.

---

## Review Summary

**Query / script name:** <!-- e.g., fact_orders_daily_load.sql -->
**PR / branch:** <!-- Link or branch name -->
**Reviewer:** <!-- Your name -->
**Date:** <!-- YYYY-MM-DD -->
**Target warehouse:** <!-- Snowflake | Redshift | Databricks | PostgreSQL | other -->
**Query type:** <!-- SELECT | INSERT | MERGE | DELETE+INSERT | TRUNCATE+INSERT | DDL -->

---

## Checklist

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | DML is idempotent (MERGE or DELETE+INSERT, no bare INSERT) | <!-- PASS / FAIL / N-A --> | |
| 2 | No `SELECT *` — explicit column list | <!-- PASS / FAIL / WARN --> | |
| 3 | Partition filter present on large table queries | <!-- PASS / FAIL / N-A --> | |
| 4 | No correlated subqueries on large scans | <!-- PASS / FAIL / WARN / N-A --> | |
| 5 | `NOT IN` replaced with `NOT EXISTS` or `LEFT JOIN ... WHERE IS NULL` | <!-- PASS / FAIL / N-A --> | |
| 6 | Division uses `NULLIF(denominator, 0)` guard | <!-- PASS / FAIL / N-A --> | |
| 7 | JOIN conditions use matching types (no implicit cast) | <!-- PASS / FAIL / WARN --> | |
| 8 | `ORDER BY` has unique tiebreak for deterministic results | <!-- PASS / FAIL / N-A --> | |
| 9 | Window frames use explicit `ROWS BETWEEN` | <!-- PASS / FAIL / N-A --> | |
| 10 | Row count / assertion check follows the load | <!-- PASS / FAIL / WARN --> | |
| 11 | EXPLAIN run — no full table scans on tables > 100M rows | <!-- PASS / FAIL / WARN --> | |
| 12 | SQL uses portable syntax where multi-warehouse support is needed | <!-- PASS / FAIL / N-A --> | |
| 13 | Date literals are type-explicit (not string comparisons to timestamps) | <!-- PASS / FAIL / WARN --> | |
| 14 | `DISTINCT` used only when necessary (not masking duplicates) | <!-- PASS / FAIL / WARN --> | |
| 15 | SCD Type 2 logic closes previous record before inserting new | <!-- PASS / FAIL / N-A --> | |

---

## Query Details

### Tables accessed

| Table | Estimated size | Access pattern | Filter used? |
|-------|---------------|----------------|--------------|
| | | <!-- full scan / partition filter / index scan --> | <!-- Y / N --> |

### EXPLAIN summary

```
Paste key lines from EXPLAIN / EXPLAIN ANALYZE output:
- Scan type (full / partition-pruned / index)
- Join type (hash / nested loop / merge)
- Estimated vs actual rows (if ANALYZE used)
- Spill or memory warnings
```

**Estimated bytes / rows scanned:** <!-- e.g., 2.1 TB / 800M rows -->
**Estimated query cost (dry-run if available):** <!-- e.g., $0.12 at $2.50/TB -->

---

## Findings

### FAIL Items (must resolve before merge)

<!-- List each FAIL with explanation and fix -->

1.

### WARN Items (should address or document)

<!-- List each WARN -->

1.

### Suggestions (non-blocking)

1.

---

## Cost Impact

**Query runs:** <!-- how often (daily / per-event / on-demand) -->
**Estimated monthly compute cost:** <!-- runs/month × cost/run -->
**Storage delta (if DDL or new table):** <!-- +/- GB -->

---

## Recommendation

<!-- APPROVE | REQUEST_CHANGES | COMMENT -->

**Decision:**

**Rationale:**

---

## Next Steps

1. <!-- Action item for SQL author or reviewer -->
2.
