---
title: "BigQuery Modeling & Cost"
description: "Partition strategy, clustering, cost formulas, DDL patterns for BigQuery"
tags: [bigquery, partitioning, clustering, cost-optimization, schema-design]
related_templates:
  - ../templates/data_contract.yaml
---

# BigQuery Modeling & Cost

> **Core principles from SKILL.md:**
> - "Partition before cluster" — Always partition BigQuery tables first. Add clustering only after partitioning. Never cluster without partitioning.
> - "Cost is a feature" — Every BQ query and storage decision must consider cost.

---

## 1. Partition Strategy Decision Table

Choose partition type based on your query patterns and data characteristics.

| Partition Type | Best For | Pros | Cons |
|---|---|---|---|
| **Ingestion-time** (`_PARTITIONTIME`) | Streaming inserts, append-only logs where query filters by load date | Zero schema changes, automatic, works with streaming | Cannot backfill to specific partitions easily, partition != business date |
| **Column (DATE/TIMESTAMP)** | Event tables with a clear business date (e.g., `event_date`, `order_date`) | Partition pruning on business logic, backfill-friendly | Requires column in schema, column must not be nullable |
| **Column (DATETIME)** | Same as DATE/TIMESTAMP but source lacks timezone | Works when source has no TZ info | Less common, same constraints as DATE |
| **Integer range** | Tables keyed by numeric ID (e.g., `customer_id` ranges, `shard_id`) | Good for non-time-series data | Must define start, end, interval; harder to reason about pruning |

**Default choice:** Column-based partitioning on a DATE or TIMESTAMP field. Fall back to ingestion-time only when no reliable date column exists.

### Partition Limits

- Max **4,000 partitions** per table.
- For daily partitions, that is ~11 years of data. Plan retention accordingly.
- Queries that touch >2,000 partitions will be slower — redesign if you hit this.

---

## 2. Clustering Strategy

Clustering sorts data within each partition. BigQuery supports up to **4 clustering columns**.

### Column Order Rules

1. **Most frequently filtered column first.** Column order directly affects pruning efficiency.
2. **High-cardinality columns benefit more** (e.g., `user_id` before `status`).
3. **Columns used in JOINs** are strong candidates.
4. **Columns used in aggregations** (GROUP BY) benefit from clustering.

### When Clustering Helps

- Queries consistently filter on the same columns.
- Table is large (>1 GB). Below that, clustering overhead is not worth it.
- Used alongside partitioning (never cluster without partitioning).

### When Clustering Does NOT Help

- Queries use `SELECT *` with no filters.
- Filter columns change across queries (no consistent access pattern).
- Table is small (<1 GB) — BigQuery minimum block size negates benefits.

---

## 3. Cost Formulas

### On-Demand Pricing

```
query_cost = bytes_scanned * ($6.25 / 1,099,511,627,776)
```

Simplified: **$6.25 per TB scanned.** First 1 TB/month is free.

Quick reference:
| Data Scanned | Cost |
|---|---|
| 10 GB | $0.06 |
| 100 GB | $0.63 |
| 1 TB | $6.25 |
| 10 TB | $62.50 |

### Flat-Rate (Editions) Comparison

| Model | Best For | Break-Even Point |
|---|---|---|
| On-demand | Sporadic queries, dev/test | < ~50 TB/month scanned |
| Standard edition | Predictable workloads | > 50 TB/month scanned |
| Enterprise edition | Cross-region, advanced features | Organization-wide adoption |

**Rule of thumb:** If your monthly on-demand bill exceeds $10,000, evaluate editions.

### Storage Costs

| Storage Type | Cost/GB/month |
|---|---|
| Active (modified in last 90 days) | $0.02 |
| Long-term (untouched 90+ days) | $0.01 |

Long-term pricing is automatic — no action needed. Design tables so historical partitions are not rewritten unnecessarily.

---

## 4. DDL Patterns

### Partitioned + Clustered Table

```sql
CREATE TABLE IF NOT EXISTS `project.dataset.events`
(
  event_id        STRING NOT NULL,
  user_id         STRING NOT NULL,
  event_type      STRING NOT NULL,
  event_timestamp TIMESTAMP NOT NULL,
  event_date      DATE NOT NULL,
  payload         JSON,
  created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY event_date
CLUSTER BY user_id, event_type
OPTIONS (
  description = 'User behavioral events, partitioned daily',
  partition_expiration_days = 730,
  require_partition_filter = TRUE
);
```

> **Always set `require_partition_filter = TRUE`** on large tables. This prevents accidental full scans.

### CREATE TABLE AS SELECT (CTAS)

```sql
CREATE OR REPLACE TABLE `project.dataset.daily_user_summary`
PARTITION BY summary_date
CLUSTER BY user_id
AS
SELECT
  DATE(event_timestamp) AS summary_date,
  user_id,
  COUNT(*) AS event_count,
  COUNT(DISTINCT event_type) AS distinct_events
FROM `project.dataset.events`
WHERE event_date >= '2025-01-01'
GROUP BY 1, 2;
```

### Materialized View

```sql
CREATE MATERIALIZED VIEW `project.dataset.mv_hourly_event_counts`
PARTITION BY event_date
CLUSTER BY event_type
OPTIONS (
  enable_refresh = TRUE,
  refresh_interval_minutes = 30
)
AS
SELECT
  event_date,
  event_type,
  TIMESTAMP_TRUNC(event_timestamp, HOUR) AS event_hour,
  COUNT(*) AS event_count
FROM `project.dataset.events`
GROUP BY 1, 2, 3;
```

### Scheduled Query (via DDL + BQ Scheduled Transfers)

```sql
-- Scheduled query: runs daily at 06:00 UTC via BQ scheduled transfers
CREATE OR REPLACE TABLE `project.dataset.daily_active_users`
PARTITION BY activity_date
CLUSTER BY platform
AS
SELECT
  event_date AS activity_date,
  user_id,
  MIN(event_timestamp) AS first_seen,
  MAX(event_timestamp) AS last_seen,
  COUNT(*) AS total_events
FROM `project.dataset.events`
WHERE event_date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
GROUP BY 1, 2;
```

---

## 5. Table Design Patterns

### Append-Only Events

Best for immutable event streams (clickstream, transactions, logs).

```sql
-- Insert new events; never update or delete
INSERT INTO `project.dataset.events`
  (event_id, user_id, event_type, event_timestamp, event_date, payload)
VALUES
  ('evt-123', 'usr-456', 'page_view', CURRENT_TIMESTAMP(), CURRENT_DATE(), JSON '{"page": "/home"}');
```

### SCD Type 2 (Slowly Changing Dimensions)

```sql
CREATE TABLE `project.dataset.dim_customer`
(
  customer_key    STRING NOT NULL,  -- surrogate key
  customer_id     STRING NOT NULL,  -- natural key
  name            STRING,
  email           STRING,
  tier            STRING,
  effective_from  DATE NOT NULL,
  effective_to    DATE,             -- NULL = current record
  is_current      BOOL NOT NULL DEFAULT TRUE,
  _loaded_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY effective_from
CLUSTER BY customer_id, is_current;
```

### Full-Refresh Snapshot

Use when source is small enough to reload entirely (<10 GB) or when CDC is unavailable.

```sql
CREATE OR REPLACE TABLE `project.dataset.dim_product`
PARTITION BY DATE(_loaded_at)
CLUSTER BY product_id
AS
SELECT
  *,
  CURRENT_TIMESTAMP() AS _loaded_at
FROM `project.staging.raw_products`;
```

### Incremental Load with MERGE

```sql
MERGE `project.dataset.fact_orders` AS target
USING `project.staging.new_orders` AS source
ON target.order_id = source.order_id
  AND target.order_date = source.order_date  -- partition pruning
WHEN MATCHED AND source.updated_at > target.updated_at THEN
  UPDATE SET
    status = source.status,
    total_amount = source.total_amount,
    updated_at = source.updated_at
WHEN NOT MATCHED THEN
  INSERT (order_id, customer_id, order_date, status, total_amount, created_at, updated_at)
  VALUES (source.order_id, source.customer_id, source.order_date, source.status,
          source.total_amount, source.created_at, source.updated_at);
```

> **Always include the partition column in the MERGE ON clause** to enable partition pruning. Without it, MERGE scans the entire target table.

---

## 6. Query Optimization

### Select Only What You Need

```sql
-- GOOD: scans only 3 columns
SELECT user_id, event_type, event_timestamp
FROM `project.dataset.events`
WHERE event_date = '2025-06-15';

-- BAD: scans all columns — costs 5-20x more
SELECT *
FROM `project.dataset.events`
WHERE event_date = '2025-06-15';
```

### Partition Pruning

```sql
-- GOOD: prunes to single partition
SELECT * FROM `project.dataset.events`
WHERE event_date = '2025-06-15';

-- GOOD: prunes to date range
SELECT * FROM `project.dataset.events`
WHERE event_date BETWEEN '2025-06-01' AND '2025-06-30';

-- BAD: function on partition column defeats pruning
SELECT * FROM `project.dataset.events`
WHERE EXTRACT(YEAR FROM event_date) = 2025;
```

### Ingestion-Time Partition Pruning

```sql
-- Use _PARTITIONTIME pseudo-column for ingestion-time partitioned tables
SELECT *
FROM `project.dataset.raw_logs`
WHERE _PARTITIONTIME >= '2025-06-01'
  AND _PARTITIONTIME < '2025-07-01';
```

### Approximate Aggregations

```sql
-- Use APPROX_COUNT_DISTINCT for large-scale cardinality estimates (~2% error, much cheaper)
SELECT
  event_date,
  APPROX_COUNT_DISTINCT(user_id) AS approx_unique_users
FROM `project.dataset.events`
WHERE event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1;
```

---

## 7. Anti-Patterns

| Anti-Pattern | Cost Impact | Fix |
|---|---|---|
| `SELECT *` on wide tables | 5-20x overspend | List only required columns |
| No partition filter on partitioned table | Full table scan | Set `require_partition_filter = TRUE` |
| Function wrapping partition column in WHERE | Defeats pruning | Use raw column comparisons |
| Clustering without partitioning | No pruning benefit | Always partition first, then cluster |
| Updating every row to change one column | Rewrites all partitions, resets long-term pricing | Update only affected partitions |
| JOINing large tables without partition filter | Cross-product of all partitions | Filter both sides of JOIN on partition key |
| Storing denormalized JSON blobs in STRING | Scans entire blob per query | Use STRUCT/nested fields or separate columns |
| Using MERGE without partition key in ON clause | Full target scan | Include partition column in ON clause |
| Creating too many small tables | Metadata overhead, no long-term pricing benefit | Use partitions within fewer tables |
| Scheduling hourly queries on daily-partitioned tables | 24x the cost | Match query frequency to partition granularity |

---

## 8. Materialized Views vs Scheduled Queries

Use this decision tree:

```
Is the aggregation supported by MV syntax?
├─ NO  → Use scheduled query
└─ YES
    ├─ Does the base table receive streaming inserts?
    │   └─ YES → Materialized view (auto-refreshes, reads from streaming buffer)
    ├─ Is query latency critical (<5 sec)?
    │   └─ YES → Materialized view (automatic rewrite, zero-maintenance)
    └─ Is output used as a source for further transformations?
        ├─ YES → Scheduled query (writes a real table, no MV restrictions)
        └─ NO  → Materialized view (lower cost, auto-maintained)
```

| Criteria | Materialized View | Scheduled Query |
|---|---|---|
| Maintenance | Auto-refresh | Manual schedule |
| Cost | Free storage for MV, queries rewritten to use it | Charged per execution |
| Flexibility | Limited SQL subset (no UNION, no non-deterministic functions) | Full SQL |
| Freshness | Near real-time (with streaming) | Depends on schedule |
| Downstream use | Best for direct BI queries | Best for pipeline intermediate tables |

---

## 9. Naming Conventions

### Datasets

```
<domain>_<layer>        # e.g., marketing_raw, marketing_staging, marketing_mart
<domain>_<environment>  # only if separate projects per env are not used
```

### Tables

```
<entity_type>_<entity>  # e.g., fact_orders, dim_customer, stg_raw_events
```

| Prefix | Meaning | Example |
|---|---|---|
| `raw_` | Ingested as-is from source | `raw_stripe_payments` |
| `stg_` | Staged/cleaned, 1:1 with source | `stg_stripe_payments` |
| `int_` | Intermediate transformation | `int_payments_joined` |
| `fact_` | Fact table (events, transactions) | `fact_order_items` |
| `dim_` | Dimension table (entities) | `dim_customer` |
| `agg_` | Pre-aggregated table | `agg_daily_revenue` |
| `mv_` | Materialized view | `mv_hourly_event_counts` |
| `rpt_` | Reporting/BI-facing table | `rpt_monthly_kpis` |

### Columns

- Use `snake_case` exclusively. No camelCase, no PascalCase.
- Suffix date/time columns: `_date`, `_at`, `_timestamp` (e.g., `created_at`, `order_date`).
- Boolean columns: prefix with `is_`, `has_`, `should_` (e.g., `is_active`, `has_subscription`).
- Foreign keys: `<referenced_entity>_id` (e.g., `customer_id`, `product_id`).
- Metadata columns: prefix with `_` (e.g., `_loaded_at`, `_source_file`, `_batch_id`).

---

## Quick Reference Checklist

Before deploying any BigQuery table to production:

- [ ] Partition column chosen (prefer business date over ingestion-time)
- [ ] Clustering columns match primary query filter pattern (up to 4)
- [ ] `require_partition_filter = TRUE` set on tables > 10 GB
- [ ] `partition_expiration_days` set if data has a retention policy
- [ ] Estimated monthly cost calculated using `bytes_scanned * $6.25/TB`
- [ ] No `SELECT *` in scheduled or materialized queries
- [ ] MERGE statements include partition column in ON clause
- [ ] Table and column names follow naming conventions
- [ ] Data contract YAML exists (see `../templates/data_contract.yaml`)
