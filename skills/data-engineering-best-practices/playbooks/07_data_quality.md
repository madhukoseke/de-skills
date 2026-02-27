---
title: "Data Quality"
description: "DQ rule types, BQ SQL assertions, dbt tests, Great Expectations, anomaly detection, quarantine patterns"
tags: [data-quality, dq, testing, great-expectations, dbt-tests, assertions, bigquery]
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
| **Freshness** | Data arrived on time relative to SLA | `MAX(loaded_at) < NOW() - INTERVAL 2 HOUR` | Error |
| **Completeness** | Expected rows/values are present | Row count >= yesterday's count * 0.9; NOT NULL on required columns | Error |
| **Uniqueness** | No duplicate records on business key | `COUNT(*) = COUNT(DISTINCT order_id)` on fact_orders | Error |
| **Validity** | Values conform to domain rules | `order_status IN ('pending','confirmed','shipped','cancelled')` | Error |
| **Referential Integrity** | FK relationships are intact | Every `customer_id` in `fact_orders` exists in `dim_customers` | Error |
| **Consistency** | Cross-table/cross-system agreement | Row count in BQ matches row count in source system | Warn |
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

## 3. BigQuery SQL Assertions

Use these patterns directly in Airflow tasks or as post-load validation steps.

### Freshness Check

```sql
-- Fails if data is stale (loaded more than 2 hours ago)
SELECT
  MAX(loaded_at) AS latest_load,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(loaded_at), HOUR) AS hours_since_load
FROM `project.dataset.orders`
HAVING TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(loaded_at), HOUR) > 2
-- Returns rows = stale. Zero rows = fresh.
```

### Row Count Bounds

```sql
-- Fails if today's load is less than 80% or more than 200% of yesterday's
WITH today AS (
  SELECT COUNT(*) AS cnt FROM `project.dataset.orders`
  WHERE order_date = CURRENT_DATE()
),
yesterday AS (
  SELECT COUNT(*) AS cnt FROM `project.dataset.orders`
  WHERE order_date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
)
SELECT
  today.cnt AS today_count,
  yesterday.cnt AS yesterday_count,
  SAFE_DIVIDE(today.cnt, yesterday.cnt) AS ratio
FROM today, yesterday
WHERE SAFE_DIVIDE(today.cnt, yesterday.cnt) NOT BETWEEN 0.8 AND 2.0
```

### Uniqueness Check

```sql
-- Fails if there are duplicate order_ids for today
SELECT order_id, COUNT(*) AS occurrences
FROM `project.dataset.orders`
WHERE order_date = CURRENT_DATE()
GROUP BY order_id
HAVING COUNT(*) > 1
```

### Referential Integrity

```sql
-- Finds order_items that reference non-existent orders
SELECT oi.order_item_id, oi.order_id
FROM `project.dataset.order_items` oi
LEFT JOIN `project.dataset.orders` o ON oi.order_id = o.order_id
WHERE o.order_id IS NULL
  AND oi.order_date = CURRENT_DATE()
```

### NULL Check on Required Columns

```sql
-- Fails if any required column is NULL
SELECT
  COUNTIF(order_id IS NULL) AS null_order_ids,
  COUNTIF(customer_id IS NULL) AS null_customer_ids,
  COUNTIF(order_date IS NULL) AS null_order_dates,
  COUNTIF(total_amount IS NULL) AS null_amounts
FROM `project.dataset.orders`
WHERE order_date = CURRENT_DATE()
HAVING
  null_order_ids > 0
  OR null_customer_ids > 0
  OR null_order_dates > 0
  OR null_amounts > 0
```

### Accepted Values

```sql
-- Fails if any order has an unexpected status
SELECT DISTINCT order_status
FROM `project.dataset.orders`
WHERE order_date = CURRENT_DATE()
  AND order_status NOT IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')
```

### Implementing as an Airflow Task

```python
from airflow.providers.google.cloud.operators.bigquery import BigQueryCheckOperator

check_freshness = BigQueryCheckOperator(
    task_id="check_orders_freshness",
    sql="""
        SELECT TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(loaded_at), HOUR) < 2 AS is_fresh
        FROM `project.dataset.orders`
    """,
    use_legacy_sql=False,
    # BigQueryCheckOperator fails if the query returns FALSE or 0 rows
)

check_no_duplicates = BigQueryCheckOperator(
    task_id="check_orders_no_duplicates",
    sql="""
        SELECT COUNT(*) = COUNT(DISTINCT order_id) AS no_dups
        FROM `project.dataset.orders`
        WHERE order_date = '{{ ds }}'
    """,
    use_legacy_sql=False,
)

load_orders >> [check_freshness, check_no_duplicates] >> load_mart
```

For row-count interval checks, use `BigQueryIntervalCheckOperator`:

```python
from airflow.providers.google.cloud.operators.bigquery import BigQueryIntervalCheckOperator

check_row_count = BigQueryIntervalCheckOperator(
    task_id="check_row_count_vs_yesterday",
    table="project.dataset.orders",
    days_back=-1,
    metrics_thresholds={"COUNT(*)": 1.5},  # today's count must be within 1.5x of yesterday's
    use_legacy_sql=False,
)
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

### Checkpoint Pattern (GCS backend + BigQuery datasource)

```python
# great_expectations/checkpoints/orders_checkpoint.yaml

name: orders_daily_checkpoint
config_version: 1.0
class_name: Checkpoint
run_name_template: "%Y-%m-%d-orders-daily"

validations:
  - batch_request:
      datasource_name: bigquery_datasource
      data_connector_name: default_inferred_data_connector
      data_asset_name: project.dataset.orders
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

### Simple Z-Score in BQ

```sql
-- Detects if today's order count is anomalous vs rolling 30-day baseline
WITH daily_counts AS (
  SELECT
    order_date,
    COUNT(*) AS order_count
  FROM `project.dataset.orders`
  WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 31 DAY)
  GROUP BY order_date
),
stats AS (
  SELECT
    AVG(order_count) AS mean_count,
    STDDEV(order_count) AS stddev_count
  FROM daily_counts
  WHERE order_date < CURRENT_DATE()  -- exclude today from baseline
),
today AS (
  SELECT order_count FROM daily_counts WHERE order_date = CURRENT_DATE()
)
SELECT
  today.order_count,
  stats.mean_count,
  stats.stddev_count,
  SAFE_DIVIDE(ABS(today.order_count - stats.mean_count), stats.stddev_count) AS z_score
FROM today, stats
WHERE SAFE_DIVIDE(ABS(today.order_count - stats.mean_count), stats.stddev_count) > 3.0
-- z_score > 3 = anomaly (>3 standard deviations from mean)
```

### Cloud Monitoring Custom Metric for DQ Alerts

```python
from google.cloud import monitoring_v3
import time

def emit_dq_metric(project_id: str, table: str, check_name: str, passed: bool):
    """Emit a DQ pass/fail metric to Cloud Monitoring."""
    client = monitoring_v3.MetricServiceClient()
    series = monitoring_v3.TimeSeries()
    series.metric.type = "custom.googleapis.com/data_quality/check_result"
    series.metric.labels["table"] = table
    series.metric.labels["check"] = check_name
    series.resource.type = "global"

    point = monitoring_v3.Point()
    point.value.bool_value = passed
    point.interval.end_time.seconds = int(time.time())
    series.points = [point]

    client.create_time_series(
        name=f"projects/{project_id}",
        time_series=[series]
    )
```

Alert when any DQ check fails using a Cloud Monitoring alerting policy with threshold on `check_result = false`.

---

## 7. PII Detection with Cloud DLP

For any table where PII classification is uncertain, scan before applying data contract classifications.

### Trigger a DLP Inspection Job from Airflow

```python
from airflow.providers.google.cloud.operators.dlp import CloudDLPCreateDLPJobOperator

dlp_scan = CloudDLPCreateDLPJobOperator(
    task_id="dlp_scan_new_table",
    project_id="my-project",
    inspect_job={
        "storage_config": {
            "big_query_options": {
                "table_reference": {
                    "project_id": "my-project",
                    "dataset_id": "raw_customers",
                    "table_id": "profiles",
                }
            }
        },
        "inspect_config": {
            "info_types": [
                {"name": "EMAIL_ADDRESS"},
                {"name": "PHONE_NUMBER"},
                {"name": "CREDIT_CARD_NUMBER"},
                {"name": "US_SOCIAL_SECURITY_NUMBER"},
                {"name": "PERSON_NAME"},
            ],
            "min_likelihood": "LIKELY",
        },
        "actions": [
            {
                "save_findings": {
                    "output_config": {
                        "table": {
                            "project_id": "my-project",
                            "dataset_id": "dlp_results",
                            "table_id": "pii_findings",
                        }
                    }
                }
            }
        ],
    },
)
```

Use DLP findings to update the `pii` and `pii_category` fields in the data contract.

---

## 8. Quarantine Pattern

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
CREATE TABLE IF NOT EXISTS `project.raw_orders.orders__quarantine`
(
  quarantine_id     STRING NOT NULL DEFAULT GENERATE_UUID(),
  quarantined_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  source_table      STRING NOT NULL,
  failure_reason    STRING NOT NULL,
  raw_record        JSON NOT NULL,         -- original bad row serialized as JSON
  batch_id          STRING,
  resolved          BOOL NOT NULL DEFAULT FALSE,
  resolved_at       TIMESTAMP,
  resolution_note   STRING
)
PARTITION BY DATE(quarantined_at)
CLUSTER BY source_table, resolved;
```

### Writing to Quarantine in Airflow

```python
def route_bad_rows(**context):
    """After a DQ check, move failing rows to quarantine."""
    ds = context["ds"]
    hook = BigQueryHook(gcp_conn_id="bigquery_prod")

    # Move bad rows to quarantine
    hook.run(f"""
        INSERT INTO `project.raw_orders.orders__quarantine`
          (source_table, failure_reason, raw_record, batch_id)
        SELECT
          'raw_orders.orders',
          'duplicate_order_id',
          TO_JSON_STRING(t),
          '{ds}'
        FROM `project.raw_orders.orders` t
        WHERE order_date = '{ds}'
          AND order_id IN (
            SELECT order_id
            FROM `project.raw_orders.orders`
            WHERE order_date = '{ds}'
            GROUP BY order_id HAVING COUNT(*) > 1
          )
    """)

    # Delete bad rows from main table
    hook.run(f"""
        DELETE FROM `project.raw_orders.orders`
        WHERE order_date = '{ds}'
          AND order_id IN (
            SELECT order_id FROM `project.raw_orders.orders__quarantine`
            WHERE DATE(quarantined_at) = '{ds}'
              AND source_table = 'raw_orders.orders'
          )
    """)
```

---

## 9. DQ Failure Decision Matrix

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
