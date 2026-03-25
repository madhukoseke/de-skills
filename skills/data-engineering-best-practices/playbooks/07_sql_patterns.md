---
title: "SQL Patterns for Data Engineering"
description: "Production SQL patterns for data engineers: window functions, idempotent DML, EXPLAIN plans, incremental loads, dialect portability, and anti-patterns"
tags: [sql, window-functions, idempotency, performance, snowflake, redshift, databricks, postgres, anti-patterns]
---

# Playbook 07 — SQL Patterns for Data Engineering

Covers: window functions, idempotent DML, query optimization with EXPLAIN, incremental load patterns, cross-dialect portability (Snowflake / Redshift / Databricks SQL / PostgreSQL), and common anti-patterns.

---

## 1. Idempotent DML (Non-Negotiable)

All warehouse writes must be idempotent. Running the same SQL twice must produce the same result.

### MERGE (upsert) — preferred for dimension/fact tables
```sql
-- Generic MERGE pattern (Snowflake / Databricks / BigQuery compatible)
MERGE INTO warehouse.dim_customers AS target
USING (
    SELECT
        customer_id,
        name,
        email,
        country_code,
        CURRENT_TIMESTAMP AS _updated_at
    FROM staging.stg_customers
) AS src
ON target.customer_id = src.customer_id
WHEN MATCHED AND (
    target.name         <> src.name    OR
    target.email        <> src.email   OR
    target.country_code <> src.country_code
) THEN UPDATE SET
    target.name         = src.name,
    target.email        = src.email,
    target.country_code = src.country_code,
    target._updated_at  = src._updated_at
WHEN NOT MATCHED THEN INSERT (customer_id, name, email, country_code, _updated_at)
    VALUES (src.customer_id, src.name, src.email, src.country_code, src._updated_at);
```

### DELETE + INSERT — for partition-scoped full refreshes
```sql
-- Delete the partition being reloaded, then insert (safe for partitioned tables)
BEGIN;

DELETE FROM warehouse.fact_orders
WHERE order_date = '{{ ds }}';  -- Airflow template variable

INSERT INTO warehouse.fact_orders (order_id, customer_id, total_amount, order_date)
SELECT
    order_id,
    customer_id,
    total_amount,
    order_date
FROM staging.stg_orders
WHERE order_date = '{{ ds }}';

COMMIT;
```

### TRUNCATE + INSERT — for full-refresh small tables only
```sql
-- Only acceptable for reference/lookup tables with < 1M rows
TRUNCATE TABLE warehouse.ref_country_codes;

INSERT INTO warehouse.ref_country_codes (code, name, region)
SELECT code, name, region FROM staging.stg_country_codes;
```

**Rule: Never use bare INSERT on tables that can receive duplicate runs.** This includes all fact tables, dimension tables, and any table written by a scheduled pipeline.

---

## 2. Window Functions

Window functions are essential for analytical patterns without self-joins.

### Ranking
```sql
-- ROW_NUMBER: unique rank per partition (deterministic with ORDER BY)
SELECT
    order_id,
    customer_id,
    order_date,
    total_amount,
    ROW_NUMBER() OVER (
        PARTITION BY customer_id
        ORDER BY order_date DESC
    ) AS rn_latest
FROM warehouse.fact_orders;

-- Use as subquery to get latest order per customer
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) AS rn
    FROM warehouse.fact_orders
) WHERE rn = 1;

-- RANK vs DENSE_RANK (for ties)
-- RANK: 1, 2, 2, 4  (gap after tie)
-- DENSE_RANK: 1, 2, 2, 3  (no gap)
SELECT
    product_id,
    revenue,
    RANK() OVER (ORDER BY revenue DESC)       AS rank_with_gap,
    DENSE_RANK() OVER (ORDER BY revenue DESC) AS rank_no_gap
FROM warehouse.fact_revenue;
```

### Running totals and moving averages
```sql
-- Running total (cumulative sum)
SELECT
    order_date,
    daily_revenue,
    SUM(daily_revenue) OVER (ORDER BY order_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_revenue
FROM warehouse.daily_revenue_summary;

-- 7-day moving average (current row + 6 preceding)
SELECT
    order_date,
    daily_revenue,
    AVG(daily_revenue) OVER (
        ORDER BY order_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS revenue_7d_avg
FROM warehouse.daily_revenue_summary;

-- Rolling count of distinct customers (approximation in most warehouses)
SELECT
    order_date,
    COUNT(DISTINCT customer_id) OVER (
        ORDER BY order_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) AS customers_30d_rolling  -- Note: COUNT DISTINCT in window is expensive
FROM warehouse.fact_orders;
```

### LAG / LEAD — period-over-period comparisons
```sql
SELECT
    order_date,
    daily_revenue,
    LAG(daily_revenue, 1) OVER (ORDER BY order_date)  AS prev_day_revenue,
    LAG(daily_revenue, 7) OVER (ORDER BY order_date)  AS prev_week_revenue,
    -- % change vs previous day
    ROUND(
        100.0 * (daily_revenue - LAG(daily_revenue, 1) OVER (ORDER BY order_date))
             / NULLIF(LAG(daily_revenue, 1) OVER (ORDER BY order_date), 0),
        2
    ) AS pct_change_daily
FROM warehouse.daily_revenue_summary
ORDER BY order_date;
```

### NTILE — percentile buckets
```sql
-- Segment customers into revenue quartiles
SELECT
    customer_id,
    total_revenue,
    NTILE(4) OVER (ORDER BY total_revenue DESC) AS revenue_quartile
    -- 1 = top 25%, 4 = bottom 25%
FROM warehouse.dim_customers_revenue;
```

### FIRST_VALUE / LAST_VALUE
```sql
-- First order date per customer (partition boundary)
SELECT
    order_id,
    customer_id,
    order_date,
    FIRST_VALUE(order_date) OVER (
        PARTITION BY customer_id
        ORDER BY order_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS first_order_date,
    LAST_VALUE(order_date) OVER (
        PARTITION BY customer_id
        ORDER BY order_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS last_order_date
FROM warehouse.fact_orders;
```

---

## 3. Incremental Load Patterns

### Watermark-based incremental (append-only tables)
```sql
-- Load only new rows since last run
-- :last_loaded_at is passed as a parameter from Airflow/dbt
INSERT INTO warehouse.fact_events (event_id, user_id, event_type, occurred_at)
SELECT
    event_id,
    user_id,
    event_type,
    occurred_at
FROM staging.stg_events
WHERE occurred_at > :last_loaded_at
  AND occurred_at <= CURRENT_TIMESTAMP;
```

### Partition-based incremental (date-partitioned tables)
```sql
-- Load the target date partition (idempotent via DELETE+INSERT)
-- Called from Airflow with {{ ds }} = execution date
DELETE FROM warehouse.fact_orders WHERE order_date = '{{ ds }}';

INSERT INTO warehouse.fact_orders
SELECT * FROM staging.stg_orders WHERE order_date = '{{ ds }}';
```

### High-water mark tracking table
```sql
-- Track last loaded offset per pipeline
CREATE TABLE IF NOT EXISTS meta.pipeline_watermarks (
    pipeline_name   VARCHAR(200) PRIMARY KEY,
    last_loaded_at  TIMESTAMP NOT NULL,
    last_run_rows   INTEGER,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Update after successful load
INSERT INTO meta.pipeline_watermarks (pipeline_name, last_loaded_at, last_run_rows)
VALUES ('stg_events_load', CURRENT_TIMESTAMP, :rows_inserted)
ON CONFLICT (pipeline_name) DO UPDATE SET
    last_loaded_at = EXCLUDED.last_loaded_at,
    last_run_rows  = EXCLUDED.last_run_rows,
    updated_at     = CURRENT_TIMESTAMP;
```

---

## 4. Query Optimization with EXPLAIN

Always run EXPLAIN (or equivalent) before deploying queries that scan > 100M rows.

### Snowflake
```sql
EXPLAIN USING TABULAR
SELECT customer_id, SUM(total_amount)
FROM fact_orders
WHERE order_date >= '2024-01-01'
GROUP BY customer_id;
-- Look for: "TableScan" bytes scanned, "Filter" partition pruning, "HashAgg" vs "SortAgg"
```

### Redshift
```sql
EXPLAIN
SELECT customer_id, SUM(total_amount)
FROM fact_orders
WHERE order_date >= '2024-01-01'
GROUP BY customer_id;
-- Look for: DS_DIST_ALL (broadcast), DS_DIST_NONE (co-located), Seq Scan (full scan bad)
-- Check: SVL_QUERY_REPORT for actual execution stats
```

### Databricks SQL / Spark
```sql
EXPLAIN FORMATTED
SELECT customer_id, SUM(total_amount)
FROM fact_orders
WHERE order_date >= '2024-01-01'
GROUP BY customer_id;
-- Look for: PartitionFilters (partition pruning active), Exchange (shuffle indicator)
-- Check: Query Profile in Databricks UI for skew and spill
```

### PostgreSQL
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT customer_id, SUM(total_amount)
FROM fact_orders
WHERE order_date >= '2024-01-01'
GROUP BY customer_id;
-- Look for: Seq Scan (add index), Hash Join vs Nested Loop (large tables need Hash Join)
-- actual rows vs estimated rows — large discrepancy → stale statistics (ANALYZE)
```

### Key things to look for in any EXPLAIN plan
| Signal | Meaning | Action |
|--------|---------|--------|
| Full table scan on large table | Missing partition filter or index | Add partition filter / index |
| Row estimate >> actual | Stale statistics | Run ANALYZE / UPDATE STATISTICS |
| Nested loop join on > 1M rows | Should be hash join | Check join key types; update planner settings |
| Spill to disk | Insufficient memory for sort/hash | Increase warehouse size or reduce data volume |
| Broadcast join on large table | Right table too large to broadcast | Repartition or increase broadcast threshold |
| Sequential scan on filter column | No index | Add index; for warehouses, sort/cluster key |

---

## 5. Dialect Portability

Write SQL that is portable across warehouses when possible. Use these equivalents:

| Operation | Snowflake | Redshift | Databricks SQL | PostgreSQL |
|-----------|-----------|----------|----------------|------------|
| Current timestamp | `CURRENT_TIMESTAMP` | `CURRENT_TIMESTAMP` | `CURRENT_TIMESTAMP` | `NOW()` |
| Date truncation | `DATE_TRUNC('day', ts)` | `DATE_TRUNC('day', ts)` | `DATE_TRUNC('day', ts)` | `DATE_TRUNC('day', ts)` |
| String concat | `||` or `CONCAT()` | `||` or `CONCAT()` | `||` or `CONCAT()` | `||` or `CONCAT()` |
| Safe division | `DIV0(a, b)` | `NULLIF(b,0)` | `NULLIF(b,0)` | `NULLIF(b,0)` |
| Regex match | `REGEXP_LIKE(col, 'pat')` | `col ~ 'pat'` | `col RLIKE 'pat'` | `col ~ 'pat'` |
| JSON extraction | `col:field` / `GET_PATH` | `JSON_EXTRACT_PATH_TEXT` | `col:field` / `get_json_object` | `col->>'field'` |
| Array contains | `ARRAY_CONTAINS(val, col)` | `col @> ARRAY[val]` | `array_contains(col, val)` | `val = ANY(col)` |
| Approximate count | `APPROX_COUNT_DISTINCT` | `APPROXIMATE COUNT(DISTINCT)` | `approx_count_distinct` | `approx_count_distinct` (ext) |
| Table sample | `SAMPLE (10 ROWS)` | `TABLESAMPLE (10 PERCENT)` | `TABLESAMPLE (10 PERCENT)` | `TABLESAMPLE BERNOULLI (10)` |

### Portability rules
1. Avoid warehouse-specific syntax (Snowflake's `:` JSON path, Redshift's `DISTKEY`) in shared SQL libraries.
2. Use `COALESCE` not `NVL` or `IFNULL` — `COALESCE` is ANSI SQL.
3. Use `CASE WHEN … THEN … END` not `IIF()` or `DECODE()`.
4. Use `NULLIF(expr, 0)` for safe division, not warehouse-specific safe divide functions.
5. Store dialect-specific queries in named profiles / adapters — never inline dialect detection in queries.

---

## 6. Row-Count and Assertion Patterns

Every load task must validate row counts. Embed assertions in the pipeline.

```sql
-- Row count sanity check (run after INSERT, before commit)
SELECT
    COUNT(*)                                         AS total_rows,
    SUM(CASE WHEN order_id IS NULL THEN 1 ELSE 0 END) AS null_order_id,
    SUM(CASE WHEN total_amount < 0 THEN 1 ELSE 0 END)  AS negative_amounts,
    COUNT(DISTINCT order_date)                          AS distinct_dates
FROM warehouse.fact_orders
WHERE order_date = '{{ ds }}';

-- Fail if counts are outside acceptable bounds (raise in application layer)
-- E.g., in Python after running assertion SQL:
assert total_rows > 10_000, f"Expected > 10K rows, got {total_rows}"
assert null_order_id == 0, f"Found {null_order_id} NULL order_ids"
assert negative_amounts == 0, f"Found {negative_amounts} negative amounts"
```

### Row count comparison across runs
```sql
-- Compare today's load vs yesterday's
WITH today AS (
    SELECT COUNT(*) AS cnt FROM warehouse.fact_orders WHERE order_date = CURRENT_DATE
),
yesterday AS (
    SELECT COUNT(*) AS cnt FROM warehouse.fact_orders WHERE order_date = CURRENT_DATE - 1
)
SELECT
    today.cnt        AS today_count,
    yesterday.cnt    AS yesterday_count,
    ROUND(100.0 * (today.cnt - yesterday.cnt) / NULLIF(yesterday.cnt, 0), 2) AS pct_change
FROM today, yesterday;
-- Alert if pct_change < -20 or > 50 (configurable bounds)
```

---

## 7. SCD Type 2 (Slowly Changing Dimensions)

```sql
-- SCD Type 2 MERGE pattern
-- Closes the current record, inserts a new one for changed attributes
MERGE INTO warehouse.dim_customers AS target
USING (
    SELECT
        customer_id,
        name,
        email,
        country_code,
        CURRENT_TIMESTAMP AS valid_from
    FROM staging.stg_customers
) AS src
ON target.customer_id = src.customer_id
   AND target.is_current = TRUE
WHEN MATCHED AND (
    target.name         <> src.name    OR
    target.email        <> src.email   OR
    target.country_code <> src.country_code
) THEN UPDATE SET
    target.valid_to   = CURRENT_TIMESTAMP,
    target.is_current = FALSE
WHEN NOT MATCHED THEN INSERT (
    customer_id, name, email, country_code,
    valid_from, valid_to, is_current
) VALUES (
    src.customer_id, src.name, src.email, src.country_code,
    src.valid_from, NULL, TRUE
);

-- Insert new version for changed records (second pass)
INSERT INTO warehouse.dim_customers (customer_id, name, email, country_code, valid_from, valid_to, is_current)
SELECT
    src.customer_id, src.name, src.email, src.country_code,
    CURRENT_TIMESTAMP, NULL, TRUE
FROM staging.stg_customers src
JOIN warehouse.dim_customers tgt
    ON tgt.customer_id = src.customer_id
    AND tgt.is_current = FALSE
    AND tgt.valid_to >= CURRENT_TIMESTAMP - INTERVAL '1 minute';
    -- The second join condition catches records just closed in the MERGE above
```

---

## 8. Anti-Patterns

| Anti-Pattern | Impact | Fix |
|-------------|--------|-----|
| `SELECT *` in production queries | Schema changes break downstream; excess bytes scanned | Explicit column list |
| Bare `INSERT` without idempotency | Duplicates on rerun | Use MERGE or DELETE+INSERT |
| Non-deterministic `ORDER BY` without unique tiebreak | Different results each run | Add primary key as final ORDER BY tiebreak |
| Correlated subquery inside large scan | O(n²) complexity | Rewrite as JOIN or window function |
| `NOT IN (subquery)` with NULLs | Returns zero rows silently when subquery has NULLs | Use `NOT EXISTS` or `LEFT JOIN ... WHERE IS NULL` |
| Division without null guard | Divide-by-zero kills query | Wrap denominator in `NULLIF(denominator, 0)` |
| Implicit type casting in JOIN | Full table scan, index bypass | Explicit `CAST()` on both sides or fix schema |
| `DISTINCT` as a crutch | Masks underlying duplicate root cause | Fix the source of duplicates instead |
| `HAVING COUNT(*) > 0` | Equivalent to no filter; intent unclear | Remove or replace with meaningful threshold |
| String date comparisons (`'2024-01-01'` vs TIMESTAMP) | Implicit cast, partition pruning bypassed | Use explicit `DATE '2024-01-01'` or `CAST` |
| Unbounded window without `ROWS BETWEEN` | `RANGE BETWEEN` default causes incorrect results for duplicate ORDER BY values | Always specify frame explicitly |
| Large cross join (`FROM a, b`) | Cartesian product if join condition typo | Always use explicit `JOIN ... ON` |
