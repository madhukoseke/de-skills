---
title: "Cost Optimization"
description: "Credit/slot accounting, partition pruning verification, query attribution, reserved vs on-demand, storage tiers, small-file/compaction, retention as a cost lever, query-result caching"
tags: [cost, finops, partition-pruning, attribution, storage-tiers, compaction, retention, caching]
related_templates:
  - ../templates/sql_review.md
  - ../templates/spark_job_review.md
---

# Playbook 15 — Cost Optimization

> **Guiding principle:** Cost is a feature (W005).
> Every query and storage decision must consider compute and storage cost. Cost is not a quarterly review item — it is enforced at PR time the same way correctness is.

This playbook makes Principle W005 measurable. It assumes you accept that "the warehouse is fast and cheap" is a story product sells you, not a budget plan.

---

## 1. The four cost levers

Every data-platform invoice rolls up to one of four levers. Confusing them is why FinOps initiatives stall.

| Lever | What it costs | Who controls it |
|-------|---------------|-----------------|
| **Compute** | Per-query / per-second / per-credit billing for warehouse, Spark, streaming clusters | Query author + cluster sizer |
| **Storage** | $/GB-month for active tables, time-travel, replicas, backups | Schema author + retention policy owner |
| **I/O** | Bytes-scanned billing (BigQuery), egress charges, cross-region transfer | Query author + lineage owner |
| **Idle / overprovisioned capacity** | Always-on clusters, unused reservations, oversized warehouses | Platform team |

**Rule:** allocate cost to a **team / cost-center label** at every layer. If the invoice can't be split by team within ±5%, no other optimization is meaningful.

---

## 2. Attribution: tagging every query

```sql
-- Snowflake / BigQuery / Databricks all support session tags (or labels).
-- Set them at the start of every query.
ALTER SESSION SET QUERY_TAG = 'team=growth;project=funnel_revamp;dag=fact_orders';

-- Or via dbt models
{{ config(
    query_tag = 'team=growth;project=' ~ var('project_label')
) }}

-- Or via Spark
spark.conf.set("spark.databricks.cluster.profile", "team=growth")
spark.sparkContext.setLocalProperty("spark.job.description", "fact_orders nightly")
```

### Required tags

At minimum, every query must carry: `team`, `pipeline_id` (e.g., DAG name + task), `environment` (dev/staging/prod). Without these, INFORMATION_SCHEMA / billing exports can't roll up to anything actionable.

### Audit query

```sql
-- Find untagged spend in the last 30 days (BigQuery example; analogous queries exist for Snowflake / Databricks)
SELECT
  COALESCE(JSON_VALUE(labels, '$.team'), '_UNTAGGED_') AS team,
  COUNT(*)                                              AS query_count,
  SUM(total_bytes_billed) / POWER(10, 12)               AS tib_billed,
  SUM(total_slot_ms) / 1000 / 3600                      AS slot_hours
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY team
ORDER BY tib_billed DESC;
```

Run weekly. **If `_UNTAGGED_` is in the top 5, fix it before any other cost work.**

---

## 3. Partition pruning verification

A partitioned table that doesn't prune is just a table that costs more to write. Verify pruning before declaring victory.

```sql
-- Verification SQL (vendor-neutral pattern)
EXPLAIN
SELECT customer_id, SUM(total_amount)
FROM mart.fact_orders
WHERE order_date BETWEEN DATE '2026-04-01' AND DATE '2026-04-29'
GROUP BY customer_id;

-- Look for these signals in the plan:
--   Snowflake:    "partitions scanned: N of M"  (N << M)
--   BigQuery:     "partitionsScanned" / "totalPartitionsConsidered"  (or "partitions scanned: 29 / 365")
--   Databricks:   "PartitionFilters: [order_date >= ..., order_date <= ...]" + "PartitionsRead: 29"
--   Iceberg:      "partition stats: <subset>"
```

### Partition-pruning anti-patterns

```sql
-- ❌ Prevents pruning: function on the partition column
WHERE DATE(loaded_at) = '2026-04-29'

-- ✅ Prunes
WHERE loaded_at >= TIMESTAMP '2026-04-29 00:00:00'
  AND loaded_at <  TIMESTAMP '2026-04-30 00:00:00'

-- ❌ Implicit cast prevents pruning
WHERE order_date = '2026-04-29'    -- order_date is DATE, RHS is STRING

-- ✅ Same type both sides
WHERE order_date = DATE '2026-04-29'

-- ❌ Subquery hides the predicate
WHERE order_date IN (SELECT max_date FROM date_lookup)

-- ✅ Materialize the subquery first or use a static predicate
WITH bounds AS (SELECT MAX(order_date) AS max_date FROM date_lookup)
SELECT ... WHERE order_date >= (SELECT max_date FROM bounds)
```

### CI gate: assert pruning on flagged queries

```python
# Pseudocode for a CI check that runs EXPLAIN on every dbt model and asserts pruning
# Reject the PR if a model marked `requires_pruning: true` doesn't prune.
def assert_partition_pruning(model: str, plan: dict, pruning_threshold: float = 0.1) -> None:
    partitions_scanned = plan["partitions_scanned"]
    total_partitions = plan["total_partitions"]
    ratio = partitions_scanned / total_partitions
    if ratio > pruning_threshold:
        raise SystemExit(
            f"Model {model} scanned {ratio:.0%} of partitions "
            f"({partitions_scanned} / {total_partitions}); threshold {pruning_threshold:.0%}"
        )
```

---

## 4. Reserved capacity vs on-demand

| Mode | When to use | Watch-out |
|------|-------------|-----------|
| On-demand | Spiky workloads (<40% of weekly hours active); exploration | Ungated cost; surprise bills |
| Reserved (1y) | ≥60% baseline load you can name 12 months out | Can't easily downsize; new workloads land on top |
| Reserved (3y) | Load you've measured for ≥6 months and is structurally permanent | Multi-year lock-in; pricing changes pass you by |
| Spot / preemptible | Backfills, batch ML training, anything restartable | No SLA; orchestrate with retries |
| Auto-scale serverless | Bursty, latency-sensitive, hard-to-predict | Per-query premium; tune carefully on hot paths |

**Rule of thumb:** size reservations to your **P50 hourly usage**, not P95 — let on-demand absorb the peaks. Reserving to P95 wastes 30-40% of the reservation off-peak.

### Identifying a candidate for reservation

```sql
-- Hourly compute usage for the last 30 days; bucket by p50 / p95 / p99
WITH hourly AS (
  SELECT
    DATE_TRUNC('hour', start_time) AS hour_bucket,
    SUM(slot_ms) / 1000 / 3600     AS slot_hours
  FROM compute_billing_export
  WHERE start_time >= CURRENT_TIMESTAMP - INTERVAL '30 days'
  GROUP BY 1
)
SELECT
  PERCENTILE_CONT(slot_hours, 0.5)  WITHIN GROUP (ORDER BY slot_hours) AS p50,
  PERCENTILE_CONT(slot_hours, 0.95) WITHIN GROUP (ORDER BY slot_hours) AS p95,
  PERCENTILE_CONT(slot_hours, 0.99) WITHIN GROUP (ORDER BY slot_hours) AS p99,
  AVG(slot_hours)                                                       AS mean_hourly
FROM hourly;
```

If `p50 / p99 > 0.5`, the workload is steady → reserve P50 + a buffer; let p99 hit on-demand.

---

## 5. Storage tiers and lifecycle

Most warehouses and lakes have 2-4 tiers; the rate ratio between hot and archive is typically 5-20×.

| Tier | Typical $/GB-mo | Retrieval | Use for |
|------|-----------------|-----------|---------|
| Hot / standard | $0.020–0.030 | Immediate | Active marts, last 30-90 days of facts |
| Warm / nearline | $0.010–0.015 | Seconds | 90 days–1 year, occasional analytics |
| Cold / coldline | $0.004–0.007 | Minutes | 1-7 years, regulatory archive |
| Archive / glacier | $0.001–0.003 | Hours | >7 years, audit-only retention |

### Lifecycle rules (vendor-neutral)

```yaml
# bucket-lifecycle.yaml — pattern, syntax differs per cloud
rules:
  - id: orders-tier-down
    prefix: "raw/orders/"
    transitions:
      - days_after: 30
        to: NEARLINE
      - days_after: 365
        to: COLDLINE
      - days_after: 2555         # 7 years
        to: ARCHIVE
    expiration:
      days_after: 3650           # 10 years — match the contract's hard_delete_after
```

### Time-travel as a cost lever

Every modern lakehouse format (Delta, Iceberg, Hudi) and warehouse (Snowflake, BigQuery) has time-travel / fail-safe storage that retains every overwritten version. Default windows are often longer than you need.

| Concern | Default | Recommendation |
|---------|---------|----------------|
| Snowflake Time Travel + Fail-safe | 1d + 7d | Set `DATA_RETENTION_TIME_IN_DAYS` per table; 1d for staging, 7d for marts unless contract requires more |
| Iceberg snapshots | All | `expire_snapshots` weekly; keep at most 30d for non-mart tables |
| Delta Lake versions | All | `VACUUM RETAIN 168 HOURS` (7d) on staging; longer only on contract-pinned tables |
| BigQuery time travel | 7d | Free for first 7d; downgrade staging tables to 0d if you don't need it |

**Rule:** every table's retention configuration must match the data contract `retention.period_days`. A 3-year retention contract on a 7-day-time-travel table is fine; a 7-day retention with `RETAIN 30 DAYS VACUUM` is silently retaining 4× longer than authorized.

---

## 6. Small files & compaction

The single biggest hidden cost on lakehouse storage. A 10 GB table with 100K small parquet files is 10× more expensive to scan than the same data in 100 well-sized files, plus 100× the metadata overhead.

### Detect

```sql
-- Iceberg: query the files metadata table
SELECT
  COUNT(*) AS file_count,
  AVG(file_size_in_bytes) / POWER(10, 6) AS avg_mb,
  MIN(file_size_in_bytes) / POWER(10, 6) AS min_mb,
  MAX(file_size_in_bytes) / POWER(10, 6) AS max_mb
FROM mart.fact_orders.files;

-- Delta Lake
DESCRIBE DETAIL mart.fact_orders;
-- Look at numFiles vs sizeInBytes.
```

**Health rule:** target average file size 128–512 MB. Below 64 MB average → schedule compaction.

### Compact

```sql
-- Iceberg
CALL my_catalog.system.rewrite_data_files(
  table => 'mart.fact_orders',
  options => map('target-file-size-bytes', '536870912')   -- 512 MB
);

-- Delta Lake
OPTIMIZE mart.fact_orders ZORDER BY (customer_id);

-- Hudi
-- Run async compaction service or hoodie-compactor on schedule
```

Schedule compaction nightly for hot marts, weekly for warm. The job is idempotent and cheap relative to the savings on every subsequent read.

---

## 7. Retention as the most underused lever

A 1 TB table dropped to 30-day retention from 7-year retention is a 99% cost reduction on that table — bigger than most query optimizations combined. Yet most teams default to "keep forever" and only review when an invoice surprises someone.

### Retention review every contract change

When a `data_contract.yaml` is created or modified, the reviewer must answer:

1. What is the **business question** that requires data older than 90 days? Name it.
2. Does the **legal mandate** require longer than the business question?
3. Does **storage tiering** (cold/archive) satisfy the legal mandate at lower cost?
4. Is the data **derivable** from a longer-retention upstream? If yes, drop this table's retention.

### Cost-of-retention calculator (back-of-envelope)

```
annual_cost ≈ daily_size_gb × 365 × storage_rate_per_gb_month × 12
            + (time_travel_window_days × daily_size_gb × storage_rate_per_gb_month × 12 / 30)
```

Run this per-table at PR time and surface in the SQL review (template at [`../templates/sql_review.md`](../templates/sql_review.md)).

---

## 8. Query-result caching

Most warehouses cache identical queries (Snowflake 24h, BigQuery 24h, Databricks Photon). The cache is invalidated on any write to the underlying tables.

### Cache-friendly patterns

- **Stable mart, frequent dashboard query** → high hit rate; don't churn the mart unnecessarily.
- **Stable input, parameterized dashboard query** → use bind parameters or session variables, not string interpolation; cache key matches.
- **Time-bounded dashboard ("last 30 days")** → use a static logical date that updates daily, not `CURRENT_DATE - 30` literally; otherwise every minute the cache key shifts.

### Anti-pattern

```sql
-- ❌ Cache misses every minute as CURRENT_TIMESTAMP changes
SELECT ... WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'

-- ✅ Cache key is stable for the day
SELECT ... WHERE created_at > DATE_TRUNC('day', CURRENT_DATE) - INTERVAL '24 hours'
```

---

## 9. Spark / lakehouse compute tuning

For heavy Spark work, the cost knobs are different (and detailed in [`08_spark_patterns.md`](08_spark_patterns.md)). Quick reminders here:

| Knob | Typical cost impact |
|------|---------------------|
| `spark.sql.shuffle.partitions` too high | Coordinator overhead, small files | Start at `total_shuffle_data_gb * 8`; let AQE coalesce down |
| Disabled AQE | Stuck plans on skew | `spark.sql.adaptive.enabled = true` (default in 3.x) |
| Photon / vectorized engine off | 2-5× slower on most workloads | Enable on all clusters that support it |
| Always-on cluster for ad-hoc | Idle cost | Auto-terminate after 30-60 min idle |
| Wide rows + few columns selected | Reads everything | Enforce explicit column projection at staging |

---

## 10. CI gates for cost

```yaml
# .github/workflows/cost.yml (example)
- name: Reject untagged dbt models
  run: |
    python3 tools/check_query_tags.py --models dbt/models/

- name: Reject SQL without partition pruning on flagged tables
  run: |
    python3 tools/explain_and_assert_pruning.py --threshold 0.1 \
      --tables tools/cost_critical_tables.yaml

- name: Reject contracts with retention > 1 year and no storage_tiering rule
  run: |
    python3 tools/check_retention_tiering.py --contracts contracts/

- name: Estimate query cost for changed dbt models
  run: |
    python3 tools/dbt_cost_estimate.py --base origin/main --head HEAD \
      --max-cost-delta-usd 50

- name: Compaction backlog
  run: |
    python3 tools/check_compaction_backlog.py --max-small-files 5000 \
      --tables tools/lakehouse_tables.yaml
```

A 5-minute CI cost gate catches 80% of the regressions that would otherwise land in next month's invoice.

---

## 11. Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| `SELECT *` in production queries | Scans every column; defeats columnar pruning | Explicit column list; one of the cheapest wins |
| No `team` / `pipeline_id` query tags | Can't attribute costs; FinOps work blocked | Required tags at session start; CI rejects untagged |
| Function on partition column in `WHERE` | No pruning; full table scan | Partition column on the LHS, literal on RHS |
| Reserve capacity at P95 instead of P50 | 30-40% reservation waste off-peak | Reserve P50; let on-demand absorb peaks |
| 7-day time-travel on staging tables | Pays for retention nobody needs | Set `RETENTION = 0d` on staging; `7d` on marts |
| Compaction "we'll do it later" | Small-file death spiral; queries slow over months | Nightly compaction job; alert when avg file size < 64 MB |
| Default lifecycle = "keep hot forever" | Storage cost compounds | Lifecycle rules tied to contract `retention.period_days` |
| Identical query runs ad-hoc 100×/day | Each pays full compute; cache invalidates often | Materialize the result; query the materialization from BI |
| `CURRENT_TIMESTAMP - INTERVAL` in dashboards | Cache key changes by the second | Truncate to day; cache reuse is free money |
| Always-on dev cluster sized for prod | Idle credits lost overnight + weekends | Auto-terminate; right-size dev separately |
| Cost shown only in monthly review | Surprise bills; no PR-time pressure | CI gate (§10) makes cost a merge-time consideration |

---

## Quick Reference Checklist: Cost Optimization

Before merging any change that adds compute or storage:

- [ ] Query tags include `team`, `pipeline_id`, `environment` (W005)
- [ ] EXPLAIN shows partition pruning on tables with `requires_pruning: true`
- [ ] Reservation strategy reviewed if this adds to baseline (≥60% of weekly hours)
- [ ] Storage tier transitions defined; lifecycle rules match contract retention
- [ ] Time-travel / version retention bounded; aligned with contract
- [ ] Compaction job exists for any new lakehouse table
- [ ] Query-result cache friendly (stable cache keys, parameterized predicates)
- [ ] Auto-terminate enabled on any new cluster; idle SLA set
- [ ] Cost-delta estimate attached to PR for any new mart or schedule change
- [ ] Quarterly retention review: every dataset's `retention.period_days` justified by a named business question

See the SQL review template at [`../templates/sql_review.md`](../templates/sql_review.md) and Spark job review at [`../templates/spark_job_review.md`](../templates/spark_job_review.md).
