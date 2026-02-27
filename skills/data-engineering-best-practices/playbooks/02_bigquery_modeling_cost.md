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

## 10. BigLake: External Tables with Fine-Grained Access

BigLake bridges BigQuery's security model onto external data in GCS, S3, or Azure Blob — without copying data into BQ.

### When to Use BigLake

- Data lives in GCS (Parquet, ORC, Avro) but you need BQ column-level security on it.
- You have cross-cloud data (AWS S3, Azure Blob) and need to query it from BigQuery.
- You want to apply row/column access policies without running a BQ load job.
- You are building an open table format lakehouse (Iceberg / Hudi / Delta) and need BQ as a query engine.

### BigLake Table DDL

```sql
-- External table backed by GCS Parquet files, with BQ column-level access
CREATE OR REPLACE EXTERNAL TABLE `project.dataset.orders_biglake`
WITH CONNECTION `us.my-biglake-connection`
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://my-bucket/orders/year=*/month=*/day=*/*.parquet'],
  hive_partition_uri_prefix = 'gs://my-bucket/orders/',
  require_hive_partition_filter = TRUE
);
```

### BigLake vs BQ Native Table: Decision

| Factor | BQ Native Table | BigLake External Table |
|---|---|---|
| Query performance | Best | ~2-3x slower (no BQ storage optimization) |
| Storage cost | BQ pricing ($0.02/GB active) | Only GCS cost ($0.02/GB standard) |
| Column-level security | Yes | Yes (key advantage of BigLake over plain external tables) |
| Streaming inserts | Yes | No |
| Materialized views | Yes | No |
| Best for | High-frequency queries, streaming | Archive, infrequent access, cross-cloud federation |

### BigLake + Iceberg (Open Table Format)

For teams building a lakehouse with open table formats:

```sql
-- Create a managed Iceberg table via BigLake
CREATE TABLE `project.dataset.orders_iceberg`
(
  order_id STRING NOT NULL,
  customer_id STRING NOT NULL,
  order_date DATE NOT NULL,
  total_amount NUMERIC
)
CLUSTER BY customer_id
WITH CONNECTION `us.my-biglake-connection`
OPTIONS (
  file_format = 'PARQUET',
  table_format = 'ICEBERG',
  storage_uri = 'gs://my-bucket/iceberg/orders/'
);
```

---

## 11. Dataplex: Data Governance and Lineage

Dataplex is GCP's unified data governance service. Use it for data cataloging, lineage tracking, data quality at scale, and cross-project metadata management.

### Dataplex Concepts

| Concept | Description | Analogous To |
|---|---|---|
| **Lake** | Top-level organizational unit for a data domain | A data domain (e.g., "Sales", "Finance") |
| **Zone** | Logical grouping within a lake (raw, curated) | A BQ dataset or GCS prefix tier |
| **Asset** | An actual GCS bucket or BQ dataset attached to a zone | The actual data resource |
| **Data Scan** | Automated data quality and profiling job | Great Expectations checkpoint |
| **Entry** | A cataloged metadata record for a table, file, or dataset | Dataplex catalog entry |

### Setting Up a Dataplex Lake via Terraform

```hcl
resource "google_dataplex_lake" "sales_lake" {
  name     = "sales-lake"
  location = "us-central1"
  project  = var.project_id

  metastore {
    service = "projects/${var.project_id}/locations/us-central1/services/my-metastore"
  }

  labels = {
    environment = var.environment
    domain      = "sales"
  }
}

resource "google_dataplex_zone" "raw_zone" {
  name         = "raw-zone"
  lake         = google_dataplex_lake.sales_lake.name
  location     = "us-central1"
  project      = var.project_id
  type         = "RAW"

  resource_spec {
    location_type = "SINGLE_REGION"
  }
}

resource "google_dataplex_zone" "curated_zone" {
  name         = "curated-zone"
  lake         = google_dataplex_lake.sales_lake.name
  location     = "us-central1"
  project      = var.project_id
  type         = "CURATED"

  resource_spec {
    location_type = "SINGLE_REGION"
  }
}

resource "google_dataplex_asset" "orders_dataset" {
  name          = "orders-bq-asset"
  lake          = google_dataplex_lake.sales_lake.name
  dataplex_zone = google_dataplex_zone.curated_zone.name
  location      = "us-central1"
  project       = var.project_id

  resource_spec {
    name = "projects/${var.project_id}/datasets/mart_sales"
    type = "BIGQUERY_DATASET"
  }
}
```

### Dataplex Data Quality Scans

Run automated DQ scans on BQ tables without writing custom SQL:

```hcl
resource "google_dataplex_datascan" "orders_dq_scan" {
  location = "us-central1"
  project  = var.project_id
  data_scan_id = "orders-dq-scan"

  data {
    resource = "//bigquery.googleapis.com/projects/${var.project_id}/datasets/mart_sales/tables/fact_orders"
  }

  execution_spec {
    trigger {
      schedule {
        cron = "0 7 * * *"  # daily at 7am UTC
      }
    }
  }

  data_quality_spec {
    rules {
      column    = "order_id"
      dimension = "UNIQUENESS"
      non_null_expectation {}
    }
    rules {
      column    = "order_id"
      dimension = "UNIQUENESS"
      uniqueness_expectation {}
    }
    rules {
      column    = "total_amount"
      dimension = "VALIDITY"
      range_expectation {
        min_value       = "0"
        strict_min_enabled = true
      }
    }
    rules {
      dimension = "FRESHNESS"
      table_condition_expectation {
        sql_expression = "MAX(loaded_at) > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)"
      }
    }
  }
}
```

### Lineage Tracking

Dataplex automatically captures lineage for:
- BigQuery jobs (queries, scheduled queries)
- DataForm executions
- dbt + dbt-dataplex plugin

For custom lineage (Airflow tasks, Cloud Run extractors), emit lineage events via the Lineage API:

```python
from google.cloud.datacatalog.lineage_v1 import LineageClient, Process, Run, LineageEvent, EventLink, EntityReference
from datetime import datetime, timezone

def emit_lineage(project_id: str, source_table: str, target_table: str, job_name: str):
    client = LineageClient()

    process = client.create_process(
        parent=f"projects/{project_id}/locations/us",
        process=Process(display_name=job_name),
    )
    run = client.create_run(
        parent=process.name,
        run=Run(
            display_name=f"{job_name}-{datetime.now(timezone.utc).date()}",
            start_time=datetime.now(timezone.utc),
        ),
    )
    client.create_lineage_event(
        parent=run.name,
        lineage_event=LineageEvent(
            links=[
                EventLink(
                    source=EntityReference(fully_qualified_name=f"bigquery:{source_table}"),
                    target=EntityReference(fully_qualified_name=f"bigquery:{target_table}"),
                )
            ],
            start_time=datetime.now(timezone.utc),
        ),
    )
```

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
