---
title: "Data Quality"
description: "DQ rule types, SQL assertions, dbt tests, anomaly detection, quarantine patterns"
tags: [data-quality, dq, testing, great-expectations, dbt-tests, assertions]
related_templates:
  - ../templates/data_quality_report.md
  - ../templates/data_contract.yaml
  - ../templates/incident_postmortem.md
---

# Data Quality Playbook

> **Guiding principles:** Fail loud. Schema is a contract. Observability by default.
> Data quality is not a phase — it is a continuous, code-first discipline embedded in every pipeline.

---

## 1. DQ Rule Taxonomy

Classify every check before implementing it. This determines severity, placement in the pipeline, and failure action.

| Category | What It Checks | Example | Default Severity |
|---|---|---|---|
| **Freshness** | Data arrived on time relative to SLA | `MAX(loaded_at) < NOW() - INTERVAL '2 hours'` | Error |
| **Completeness** | Expected rows/values are present | Row count >= yesterday's count * 0.9; NOT NULL on required columns | Error |
| **Uniqueness** | No duplicate records on business key | `COUNT(*) = COUNT(DISTINCT order_id)` on fact_orders | Error |
| **Validity** | Values conform to domain rules | `order_status IN ('pending','confirmed','shipped','cancelled')` | Error |
| **Referential Integrity** | FK relationships are intact | Every `customer_id` in `fact_orders` exists in `dim_customers` | Error |
| **Consistency** | Cross-table/cross-system agreement | Row count in warehouse matches row count in source system | Warn |
| **Timeliness** | Events arrive in expected time windows | P99 event arrival latency < 5 minutes | Warn |
| **Distribution** | Statistical properties are stable | `AVG(order_amount)` within 2 stddev of rolling 7-day average | Warn |

---

## 2. Where to Place DQ Checks

DQ checks belong at every layer boundary. Failing late (at the mart) is worse than failing early (at raw).

```
[ Source ] --> raw --> staging --> curated --> mart --> consumers
                |          |           |         |
              Freshness  Validity   Referential  Distribution
              Row count  Uniqueness  Integrity   Anomaly
              Schema     Completeness            freshness re-check
              check
```

**Rule:** Gate each layer's downstream work on DQ passing for that layer. Do not load the mart if staging tests fail.

---

## 3. SQL Assertions

Use these patterns directly in Airflow tasks or as post-load validation steps. Adapt syntax for your specific warehouse (Snowflake, Redshift, Databricks, Postgres, etc.).

### Freshness Check

```sql
-- Fails if data is stale (loaded more than 2 hours ago)
SELECT
  MAX(loaded_at)                                                    AS latest_load,
  EXTRACT(EPOCH FROM (NOW() - MAX(loaded_at))) / 3600              AS hours_since_load
FROM orders
HAVING EXTRACT(EPOCH FROM (NOW() - MAX(loaded_at))) / 3600 > 2
-- Returns rows = stale. Zero rows = fresh.
```

### Row Count Bounds

```sql
-- Fails if today's load is less than 80% or more than 200% of yesterday's
WITH today AS (
  SELECT COUNT(*) AS cnt FROM orders
  WHERE order_date = CURRENT_DATE
),
yesterday AS (
  SELECT COUNT(*) AS cnt FROM orders
  WHERE order_date = CURRENT_DATE - INTERVAL '1 day'
)
SELECT
  today.cnt     AS today_count,
  yesterday.cnt AS yesterday_count,
  today.cnt::FLOAT / NULLIF(yesterday.cnt, 0) AS ratio
FROM today, yesterday
WHERE today.cnt::FLOAT / NULLIF(yesterday.cnt, 0) NOT BETWEEN 0.8 AND 2.0
```

### Uniqueness Check

```sql
-- Fails if there are duplicate order_ids for today
SELECT order_id, COUNT(*) AS occurrences
FROM orders
WHERE order_date = CURRENT_DATE
GROUP BY order_id
HAVING COUNT(*) > 1
```

### Referential Integrity

```sql
-- Finds order_items that reference non-existent orders
SELECT oi.order_item_id, oi.order_id
FROM order_items oi
LEFT JOIN orders o ON oi.order_id = o.order_id
WHERE o.order_id IS NULL
  AND oi.order_date = CURRENT_DATE
```

### NULL Check on Required Columns

```sql
-- Fails if any required column is NULL
SELECT
  SUM(CASE WHEN order_id    IS NULL THEN 1 ELSE 0 END) AS null_order_ids,
  SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS null_customer_ids,
  SUM(CASE WHEN order_date  IS NULL THEN 1 ELSE 0 END) AS null_order_dates,
  SUM(CASE WHEN total_amount IS NULL THEN 1 ELSE 0 END) AS null_amounts
FROM orders
WHERE order_date = CURRENT_DATE
HAVING
  SUM(CASE WHEN order_id    IS NULL THEN 1 ELSE 0 END) > 0
  OR SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) > 0
  OR SUM(CASE WHEN order_date  IS NULL THEN 1 ELSE 0 END) > 0
  OR SUM(CASE WHEN total_amount IS NULL THEN 1 ELSE 0 END) > 0
```

### Accepted Values

```sql
-- Fails if any order has an unexpected status
SELECT DISTINCT order_status
FROM orders
WHERE order_date = CURRENT_DATE
  AND order_status NOT IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')
```

### Implementing as an Airflow Task

```python
from airflow.providers.common.sql.operators.sql import SQLCheckOperator, SQLIntervalCheckOperator

check_freshness = SQLCheckOperator(
    task_id="check_orders_freshness",
    conn_id="warehouse_prod",
    sql="""
        SELECT MAX(loaded_at) > NOW() - INTERVAL '2 hours' AS is_fresh
        FROM orders
    """,
    # SQLCheckOperator fails if the query returns FALSE or 0 rows
)

check_no_duplicates = SQLCheckOperator(
    task_id="check_orders_no_duplicates",
    conn_id="warehouse_prod",
    sql="""
        SELECT COUNT(*) = COUNT(DISTINCT order_id) AS no_dups
        FROM orders
        WHERE order_date = '{{ ds }}'
    """,
)

check_row_count = SQLIntervalCheckOperator(
    task_id="check_row_count_vs_yesterday",
    conn_id="warehouse_prod",
    table="orders",
    days_back=-1,
    metrics_thresholds={"COUNT(*)": 1.5},  # today's count must be within 1.5x of yesterday's
)

load_orders >> [check_freshness, check_no_duplicates, check_row_count] >> load_mart
```

---

## 4. dbt Tests for Data Quality

### Built-in Generic Tests

```yaml
# models/marts/core/_core.yml
version: 2

models:
  - name: fact_orders
    columns:
      - name: order_id
        data_tests:
          - unique
          - not_null
      - name: customer_id
        data_tests:
          - not_null
          - relationships:
              to: ref('dim_customers')
              field: customer_id
      - name: order_status
        data_tests:
          - accepted_values:
              values: ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
      - name: total_amount
        data_tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: "total_amount >= 0"
```

### dbt-expectations Package (Statistical Checks)

Install:

```yaml
# packages.yml
packages:
  - package: calogica/dbt_expectations
    version: [">=0.10.0", "<0.11.0"]
  - package: dbt-labs/dbt_utils
    version: [">=1.0.0", "<2.0.0"]
```

Usage:

```yaml
- name: fact_orders
  data_tests:
    - dbt_expectations.expect_table_row_count_to_be_between:
        min_value: 1000
        max_value: 10000000
    - dbt_expectations.expect_table_row_count_to_equal_other_table:
        compare_model: ref('stg_orders')
        # mart row count == staging row count (no silent drops)

  columns:
    - name: order_date
      data_tests:
        - dbt_expectations.expect_column_values_to_be_between:
            min_value: "'2020-01-01'"
            max_value: "current_date()"
        - dbt_expectations.expect_column_values_to_not_be_null
    - name: total_amount
      data_tests:
        - dbt_expectations.expect_column_mean_to_be_between:
            min_value: 10
            max_value: 10000
            # flags if average order amount is wildly out of range
```

### Singular Tests for Complex Logic

```sql
-- tests/assert_no_revenue_before_order.sql
-- Revenue recognition date must not precede the order date
SELECT
  f.order_id,
  f.order_date,
  r.recognition_date
FROM {{ ref('fact_orders') }} f
JOIN {{ ref('fact_revenue') }} r ON f.order_id = r.order_id
WHERE r.recognition_date < f.order_date
```

---

## 5. Great Expectations Integration

Use Great Expectations when:
- You need rich HTML documentation of your DQ suite
- You are validating data from multiple sources with different rules
- You want checkpoint-based validation that integrates with existing pipelines

### Checkpoint Pattern

```python
# great_expectations/checkpoints/orders_checkpoint.yaml

name: orders_daily_checkpoint
config_version: 1.0
class_name: Checkpoint
run_name_template: "%Y-%m-%d-orders-daily"

validations:
  - batch_request:
      datasource_name: warehouse_datasource
      data_connector_name: default_inferred_data_connector
      data_asset_name: orders
      data_connector_query:
        index: -1  # most recent partition
    expectation_suite_name: orders.critical

action_list:
  - name: store_validation_result
    action:
      class_name: StoreValidationResultAction
  - name: update_data_docs
    action:
      class_name: UpdateDataDocsAction
  - name: send_slack_notification_on_failure
    action:
      class_name: SlackNotificationAction
      slack_webhook: "${SLACK_WEBHOOK_URL}"
      notify_on: failure
```

### Calling from Airflow

```python
from airflow.operators.bash import BashOperator

run_ge_checkpoint = BashOperator(
    task_id="run_great_expectations_checkpoint",
    bash_command="great_expectations checkpoint run orders_daily_checkpoint",
    env={"SLACK_WEBHOOK_URL": "{{ var.value.slack_webhook_url }}"},
)

load_orders >> run_ge_checkpoint >> load_mart
```

---

## 6. Anomaly Detection

Statistical anomaly detection catches issues that threshold-based checks miss (e.g., a gradual drift that never crosses a hard limit).

### Simple Z-Score in SQL

```sql
-- Detects if today's order count is anomalous vs rolling 30-day baseline
WITH daily_counts AS (
  SELECT
    order_date,
    COUNT(*) AS order_count
  FROM orders
  WHERE order_date >= CURRENT_DATE - INTERVAL '31 days'
  GROUP BY order_date
),
stats AS (
  SELECT
    AVG(order_count)    AS mean_count,
    STDDEV(order_count) AS stddev_count
  FROM daily_counts
  WHERE order_date < CURRENT_DATE  -- exclude today from baseline
),
today AS (
  SELECT order_count FROM daily_counts WHERE order_date = CURRENT_DATE
)
SELECT
  today.order_count,
  stats.mean_count,
  stats.stddev_count,
  ABS(today.order_count - stats.mean_count) / NULLIF(stats.stddev_count, 0) AS z_score
FROM today, stats
WHERE ABS(today.order_count - stats.mean_count) / NULLIF(stats.stddev_count, 0) > 3.0
-- z_score > 3 = anomaly (>3 standard deviations from mean)
```

### Emitting DQ Metrics for Alerting

```python
def emit_dq_result(metric_store, table: str, check_name: str, passed: bool):
    """Record DQ pass/fail to your observability system (Datadog, Prometheus, etc.)."""
    metric_store.gauge(
        metric="data_quality.check_result",
        value=1 if passed else 0,
        tags=[f"table:{table}", f"check:{check_name}"],
    )
```

Alert when any DQ check fails using your observability platform's alerting policy.

---

## 7. Quarantine Pattern

When a DQ check fails, do not silently drop bad rows or halt the entire pipeline. Quarantine them.

```
[ Source ] --> raw --> [DQ checks] --> PASS --> staging --> mart
                               |
                               FAIL
                               |
                         Quarantine table
                         (raw_{source}__quarantine)
                               |
                         Alert: Slack + PagerDuty
                         Manual review + replay
```

### Quarantine Table DDL

```sql
CREATE TABLE IF NOT EXISTS raw_orders__quarantine
(
  quarantine_id     VARCHAR    NOT NULL DEFAULT gen_random_uuid(),
  quarantined_at    TIMESTAMP  NOT NULL DEFAULT NOW(),
  source_table      VARCHAR    NOT NULL,
  failure_reason    VARCHAR    NOT NULL,
  raw_record        JSONB      NOT NULL,  -- original bad row serialized as JSON
  batch_id          VARCHAR,
  resolved          BOOLEAN    NOT NULL DEFAULT FALSE,
  resolved_at       TIMESTAMP,
  resolution_note   VARCHAR
);
```

### Writing to Quarantine in Airflow

```python
def route_bad_rows(**context):
    """After a DQ check, move failing rows to quarantine."""
    ds   = context["ds"]
    hook = PostgresHook(postgres_conn_id="warehouse_prod")

    # Move bad rows to quarantine — use parameters dict, never f-string into SQL
    hook.run(
        """
        INSERT INTO raw_orders__quarantine
          (source_table, failure_reason, raw_record, batch_id)
        SELECT
          'raw_orders',
          'duplicate_order_id',
          row_to_json(t),
          %(ds)s
        FROM raw_orders t
        WHERE order_date = %(ds)s
          AND order_id IN (
            SELECT order_id
            FROM raw_orders
            WHERE order_date = %(ds)s
            GROUP BY order_id HAVING COUNT(*) > 1
          )
        """,
        parameters={"ds": ds},
    )

    # Delete bad rows from main table
    hook.run(
        """
        DELETE FROM raw_orders
        WHERE order_date = %(ds)s
          AND order_id IN (
            SELECT order_id FROM raw_orders__quarantine
            WHERE DATE(quarantined_at) = %(ds)s
              AND source_table = 'raw_orders'
          )
        """,
        parameters={"ds": ds},
    )
```

---

## 8. DQ Failure Decision Matrix

| Check Type | Severity | Failure Action |
|---|---|---|
| Freshness check (data > 2h late) | Error | Halt downstream tasks. Page on-call. |
| Primary key uniqueness | Error | Quarantine duplicates. Halt mart load. |
| NOT NULL on required columns | Error | Quarantine NULL rows. Halt mart load. |
| Referential integrity | Error | Quarantine orphan rows. Warn on-call. |
| Row count deviation > 20% | Error | Halt. Page. Investigate before proceeding. |
| Row count deviation 5-20% | Warn | Alert Slack. Proceed. Monitor next run. |
| Distribution anomaly (z > 3) | Warn | Alert Slack. Proceed. Create investigation ticket. |
| Accepted values (new unknown value) | Warn | Alert. Proceed. Update contract if value is valid. |
| Cross-system consistency drift | Warn | Log. Proceed. Schedule reconciliation. |

---

## Quick Reference Checklist: Data Quality

Before any table enters production without DQ gates:

- [ ] Freshness check defined and scheduled
- [ ] Row count check (absolute minimum and deviation from previous run)
- [ ] NOT NULL test on all primary and business key columns
- [ ] Uniqueness test on primary key
- [ ] Referential integrity tests for all FK columns pointing to dimension tables
- [ ] Accepted values test on any enum/status column
- [ ] Quarantine table exists for the pipeline's raw layer
- [ ] DQ failures trigger alerts (not just silent log entries)
- [ ] DQ checks run in CI against sample data before production deploy
- [ ] DQ rules are documented in the data contract `quality` section

See the filled template at [../templates/data_quality_report.md](../templates/data_quality_report.md).
