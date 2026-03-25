---
title: "Spark Job Review"
description: "Template for reviewing PySpark/Scala Spark jobs for correctness, performance, idempotency, and testability"
tags: [spark, pyspark, review, template, performance, delta, iceberg]
---

# Spark Job Review Template

Fill in all sections. Used by SPARK mode and PR_REVIEW mode. Referenced by `playbooks/08_spark_patterns.md`.

---

## Review Summary

**Job name:** <!-- e.g., orders_daily_transform -->
**PR / branch:** <!-- Link or branch name -->
**Reviewer:** <!-- Your name -->
**Date:** <!-- YYYY-MM-DD -->
**Runtime:** <!-- Databricks | EMR | Dataproc | standalone cluster -->
**Table format:** <!-- Delta | Iceberg | Hudi | Parquet | other -->
**Trigger:** <!-- Batch (Airflow/cron) | Streaming (Spark Structured Streaming) -->

---

## Checklist

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | AQE is enabled (`spark.sql.adaptive.enabled=true`) | <!-- PASS / FAIL / WARN --> | |
| 2 | No `df.collect()` on large DataFrames | <!-- PASS / FAIL / N-A --> | |
| 3 | Python UDFs replaced with built-in `pyspark.sql.functions` where possible | <!-- PASS / FAIL / WARN / N-A --> | |
| 4 | Explicit schema provided on read (no schema inference in production) | <!-- PASS / FAIL / WARN --> | |
| 5 | Output partition strategy matches query access patterns | <!-- PASS / FAIL / WARN --> | |
| 6 | Write is idempotent (MERGE, `overwrite` with `partitionOverwriteMode=dynamic`, or Delta MERGE) | <!-- PASS / FAIL --> | |
| 7 | Streaming query has `checkpointLocation` set | <!-- PASS / FAIL / N-A --> | |
| 8 | Broadcast joins used for small lookup tables | <!-- PASS / FAIL / WARN / N-A --> | |
| 9 | Skew mitigation in place for known hot keys | <!-- PASS / FAIL / WARN / N-A --> | |
| 10 | No business logic in Airflow DAG file; logic is in the Spark job | <!-- PASS / FAIL / N-A --> | |
| 11 | `cache()` used only for DataFrames read 2+ times in same job | <!-- PASS / FAIL / WARN --> | |
| 12 | Job accepts `--date` / `--partition` argument (no hardcoded dates) | <!-- PASS / FAIL --> | |
| 13 | Delta `OPTIMIZE` and `VACUUM` scheduled for the target table | <!-- PASS / FAIL / WARN / N-A --> | |
| 14 | Unit tests exist for transform functions (pytest + local SparkSession) | <!-- PASS / FAIL / WARN --> | |
| 15 | Idempotency test verifies row count unchanged on re-run | <!-- PASS / FAIL / WARN --> | |

---

## Job Configuration

```
SparkSession config:
  spark.sql.adaptive.enabled:
  spark.sql.shuffle.partitions:
  spark.executor.memory:
  spark.executor.cores:
  spark.dynamicAllocation.enabled:

Table format / write mode:
Input partitioning:
Output partitioning:
Checkpoint location (if streaming):
```

---

## Data Flow

```
Source(s):
  -
  -

Transformations (summary):
  -
  -

Sink(s):
  -
```

---

## Performance Analysis

| Metric | Value | Notes |
|--------|-------|-------|
| Input data size | | |
| Output data size | | |
| Shuffle read size | | |
| Max task duration | | |
| Skew ratio (max / median task duration) | | |
| Spill to disk | <!-- Y / N --> | |
| Estimated cluster cost per run | | |

---

## Findings

### FAIL Items (must resolve before merge)

1.

### WARN Items (should address or document)

1.

### Suggestions (non-blocking)

1.

---

## Recommendation

<!-- APPROVE | REQUEST_CHANGES | COMMENT -->

**Decision:**

**Rationale:**

---

## Next Steps

1.
2.
