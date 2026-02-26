---
title: "Airflow Reliability"
description: "DAG reliability patterns: retries, idempotency, sensors, backfill"
tags: [airflow, composer, reliability, retries, idempotency]
related_templates:
  - ../templates/airflow_dag_review.md
  - ../templates/runbook.md
---

# Airflow Reliability Playbook

This playbook codifies production-tested patterns for building reliable Airflow DAGs on Cloud Composer. Every recommendation here ties back to the non-negotiable principles in [SKILL.md](../SKILL.md) — especially **Idempotency first**, **Retry with backoff**, **Fail loud**, and **Separation of concerns**.

---

## 1. Retry Strategy

> **Non-negotiable (Principle 6):** All external calls must use exponential backoff with jitter.

Every task that touches an external system (BigQuery, APIs, GCS, databases) must define retries explicitly. Never rely on Airflow's defaults.

### Standard retry configuration

```python
from datetime import timedelta

DEFAULT_TASK_ARGS = {
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=2),
}
```

Apply these as `default_args` on the DAG, then override per-task only when you have a concrete reason.

```python
from airflow import DAG

with DAG(
    dag_id="orders_daily_load",
    default_args=DEFAULT_TASK_ARGS,
    schedule_interval="@daily",
    catchup=False,
    tags=["orders", "tier-1"],
) as dag:
    ...
```

### When to override retries per task

| Scenario | Override | Reason |
|----------|----------|--------|
| Long-running BQ query (>1h) | `execution_timeout=timedelta(hours=4)` | Avoid premature kill |
| Flaky third-party API | `retries=5, retry_delay=timedelta(minutes=5)` | Longer backoff for unstable services |
| Cheap idempotent check | `retries=1, retry_delay=timedelta(seconds=30)` | Fast feedback, no need for long waits |
| Non-retryable operation (e.g., sending emails) | `retries=0` | Prevent duplicate side effects |

### What retries will NOT fix

Retries mask transient errors. They do not fix: bad SQL, missing permissions, schema drift, or exhausted quotas. If a task fails 3 times, it should stay failed and page someone — do not set `retries=10` to paper over a systemic issue.

---

## 2. Idempotency Patterns

> **Non-negotiable (Principle 1):** Every pipeline operation must produce the same result when re-run. Use MERGE or DELETE+INSERT, never bare INSERT for dimension/fact loads.

A task is idempotent if running it N times with the same inputs produces the same result as running it once. This is mandatory for safe retries, backfills, and manual re-runs.

### Pattern A: DELETE + INSERT (preferred for full-partition loads)

Best for fact tables where you reload an entire partition.

```python
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

delete_and_insert = BigQueryInsertJobOperator(
    task_id="load_orders_partition",
    configuration={
        "query": {
            "query": """
                -- Step 1: delete the target partition
                DELETE FROM `project.dataset.orders`
                WHERE order_date = '{{ ds }}';

                -- Step 2: insert fresh data for that date
                INSERT INTO `project.dataset.orders`
                SELECT *
                FROM `project.dataset.orders_staging`
                WHERE order_date = '{{ ds }}';
            """,
            "useLegacySql": False,
        }
    },
)
```

**Why this works:** If the task is retried or re-run for the same `ds`, the DELETE removes any partial or duplicate data before re-inserting.

### Pattern B: MERGE (preferred for SCD/dimension updates)

Best for slowly-changing dimensions or upsert patterns.

```python
merge_customers = BigQueryInsertJobOperator(
    task_id="merge_customers",
    configuration={
        "query": {
            "query": """
                MERGE `project.dataset.customers` AS target
                USING `project.dataset.customers_staging` AS source
                ON target.customer_id = source.customer_id
                WHEN MATCHED THEN
                    UPDATE SET
                        target.name = source.name,
                        target.email = source.email,
                        target.updated_at = source.updated_at
                WHEN NOT MATCHED THEN
                    INSERT (customer_id, name, email, created_at, updated_at)
                    VALUES (source.customer_id, source.name, source.email,
                            source.created_at, source.updated_at);
            """,
            "useLegacySql": False,
        }
    },
)
```

### Pattern C: Partition overwrite (BigQuery native)

Use `WRITE_TRUNCATE` disposition against a partition-decorated table.

```python
load_partition = BigQueryInsertJobOperator(
    task_id="load_events_partition",
    configuration={
        "load": {
            "sourceUris": ["gs://bucket/events/{{ ds }}/*.parquet"],
            "destinationTable": {
                "projectId": "my-project",
                "datasetId": "raw",
                "tableId": "events${{ ds_nodash }}",
            },
            "sourceFormat": "PARQUET",
            "writeDisposition": "WRITE_TRUNCATE",
        }
    },
)
```

**Key point:** The `${{ ds_nodash }}` partition decorator ensures only that specific partition is overwritten.

### Anti-pattern: bare INSERT

```python
# NEVER DO THIS for dimension or fact loads
INSERT INTO `project.dataset.orders`
SELECT * FROM staging WHERE order_date = '{{ ds }}';
```

If retried, this duplicates data. There is no safe recovery without manual intervention.

---

## 3. Sensor Best Practices

Sensors wait for external conditions. Misconfigured sensors are the number-one cause of Composer worker pool exhaustion.

### Standard sensor configuration

```python
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.providers.google.cloud.sensors.gcs import GCSObjectExistenceSensor

wait_for_upstream = ExternalTaskSensor(
    task_id="wait_for_upstream_dag",
    external_dag_id="upstream_dag",
    external_task_id="final_task",
    poke_interval=300,          # 5 minutes between checks
    timeout=7200,               # fail after 2 hours
    mode="reschedule",          # FREE THE WORKER SLOT between pokes
    soft_fail=False,            # True only if downstream can run without this
    execution_delta=timedelta(hours=1),
)

wait_for_file = GCSObjectExistenceSensor(
    task_id="wait_for_landing_file",
    bucket="data-landing",
    object="orders/{{ ds }}/orders.parquet",
    poke_interval=300,
    timeout=10800,              # 3 hours
    mode="reschedule",
)
```

### Sensor mode decision

| Mode | Behavior | Use When |
|------|----------|----------|
| `poke` | Holds the worker slot, sleeps between pokes | Very short expected waits (<5 min), lightweight checks |
| `reschedule` | Releases the worker slot, re-schedules after `poke_interval` | **Default choice.** Any wait >5 min, any production sensor |

**Rule:** Always use `mode="reschedule"` unless you have a specific, documented reason for `poke`. A DAG with five `poke`-mode sensors each waiting 2 hours will hold five worker slots doing nothing — that is five slots not available for actual work.

### soft_fail usage

Set `soft_fail=True` only when downstream tasks can meaningfully proceed without the sensor's condition being met. Common case: optional enrichment data that has a fallback.

```python
wait_for_enrichment = GCSObjectExistenceSensor(
    task_id="wait_for_optional_enrichment",
    bucket="enrichment-data",
    object="geo/{{ ds }}/geo_lookup.csv",
    poke_interval=600,
    timeout=3600,
    mode="reschedule",
    soft_fail=True,  # downstream handles missing enrichment gracefully
)
```

---

## 4. Task Dependency Patterns

### trigger_rule usage

The default `trigger_rule="all_success"` is correct for most tasks. Override only in these cases:

```python
from airflow.utils.trigger_rule import TriggerRule

# Run cleanup regardless of upstream success/failure
cleanup_task = BashOperator(
    task_id="cleanup_temp_files",
    bash_command="gsutil -m rm -r gs://bucket/tmp/{{ ds }}/",
    trigger_rule=TriggerRule.ALL_DONE,  # runs after all upstreams finish
)

# Run notification on any failure
notify_on_failure = PythonOperator(
    task_id="notify_failure",
    python_callable=send_slack_alert,
    trigger_rule=TriggerRule.ONE_FAILED,
)
```

| trigger_rule | Use Case |
|--------------|----------|
| `all_success` | Default. Task needs all inputs. |
| `all_done` | Cleanup, resource deallocation. Must run regardless. |
| `one_failed` | Alert/notification tasks. |
| `none_failed` | Skip-aware: runs if nothing failed (skipped is OK). |
| `all_failed` | Fallback paths only. Rare. |

### BranchPythonOperator

Use branching when a DAG must take mutually exclusive paths based on runtime conditions.

```python
from airflow.operators.python import BranchPythonOperator
from airflow.operators.empty import EmptyOperator

def choose_load_strategy(**context):
    """Route to full or incremental load based on execution date."""
    ds = context["ds"]
    # Full load on 1st of month, incremental otherwise
    if ds.endswith("-01"):
        return "full_load"
    return "incremental_load"

branch = BranchPythonOperator(
    task_id="choose_strategy",
    python_callable=choose_load_strategy,
)

full_load = BigQueryInsertJobOperator(task_id="full_load", ...)
incremental_load = BigQueryInsertJobOperator(task_id="incremental_load", ...)
join = EmptyOperator(task_id="join", trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)

branch >> [full_load, incremental_load] >> join
```

**Important:** The task after a branch must use `trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS` (or `NONE_FAILED`) to avoid being skipped.

---

## 5. Backfill Guidance

### Design for `{{ ds }}` from day one

> **Non-negotiable (Principle 1):** Idempotency enables safe backfill. If your DAG is not idempotent, it cannot be backfilled.

Every SQL query, file path, and API call in a task must be parameterized with the logical execution date — not `CURRENT_DATE()` or `datetime.now()`.

```python
# CORRECT: uses Airflow-templated execution date
query = """
    SELECT * FROM `project.dataset.events`
    WHERE event_date = '{{ ds }}'
"""

# WRONG: uses wall-clock time, breaks backfill
query = """
    SELECT * FROM `project.dataset.events`
    WHERE event_date = CURRENT_DATE()
"""
```

### catchup decision tree

```
Should Airflow auto-create runs for past dates when the DAG is unpaused?
│
├── YES (catchup=True):
│   - DAG is fully idempotent
│   - Each run processes exactly one logical date
│   - Order of run completion doesn't matter
│   - Example: daily partition load from immutable source
│
└── NO (catchup=False):
    - DAG has side effects (sends emails, triggers external jobs)
    - DAG processes "latest" data regardless of schedule
    - Running old dates would cause confusion or waste
    - Example: ML model retraining, notification DAGs
```

### Running a backfill

```bash
# Backfill a specific date range
airflow dags backfill \
    --start-date 2025-01-01 \
    --end-date 2025-01-15 \
    --reset-dagruns \
    orders_daily_load
```

**Key flags:**
- `--reset-dagruns`: Clear existing state for those dates (safe because tasks are idempotent).
- Never backfill without `--reset-dagruns` unless you know prior runs were clean.
- Limit parallelism with `--max-active-runs` on the DAG to avoid overwhelming BQ or APIs during large backfills.

---

## 6. Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|-------------|-------------|-----|
| Bare `INSERT INTO` for loads | Duplicates on retry/backfill | DELETE+INSERT or MERGE |
| `poke` mode on long-wait sensors | Holds worker slots for hours | Use `mode="reschedule"` |
| `retries=0` on external calls | Transient errors cause pipeline failure | Use standard retry config with backoff |
| `retries=10` to mask a real bug | Delays failure detection, wastes resources | Fix the root cause, keep `retries=3` |
| Hardcoded dates in SQL | Breaks backfill, not idempotent | Use `{{ ds }}` / `{{ ds_nodash }}` templating |
| `datetime.now()` in tasks | Non-deterministic, breaks backfill | Use `{{ ts }}` or `context["execution_date"]` |
| Mega-DAG with 100+ tasks | Slow to parse, hard to debug, blocks scheduler | Split into domain-specific DAGs linked by sensors |
| Business logic in DAG file | Violates separation of concerns, untestable | Extract to SQL files or Python modules |
| `depends_on_past=True` globally | Blocks all backfills if one run fails | Use only on specific tasks that truly need it |
| Storing secrets in DAG code | Security risk, leaks in logs/UI | Use Airflow Connections + Secret Manager backend |
| `trigger_rule="all_done"` everywhere | Silently proceeds past failures | Use `all_done` only for cleanup tasks |
| No `execution_timeout` on tasks | Zombie tasks hold resources indefinitely | Set explicit timeout on every task |

---

## 7. Connection and Secret Management

> **Non-negotiable:** Never store credentials in DAG code, environment variables, or GCS files accessible to the DAG.

### Use Cloud Composer's Secret Manager backend

```python
# In Composer environment config (Terraform or Console):
# AIRFLOW__SECRETS__BACKEND=airflow.providers.google.cloud.secrets.secret_manager.CloudSecretManagerBackend
# AIRFLOW__SECRETS__BACKEND_KWARGS={"project_id": "my-project", "connections_prefix": "airflow-conn", "variables_prefix": "airflow-var"}

# In DAG code — just reference the connection ID
from airflow.hooks.base import BaseHook

conn = BaseHook.get_connection("salesforce_api")
api_key = conn.password  # pulled from Secret Manager at runtime
```

### Connection naming conventions

Use a consistent prefix scheme so connections are discoverable:

| Pattern | Example | Contains |
|---------|---------|----------|
| `{system}_{environment}` | `bigquery_prod` | Service account JSON or OAuth |
| `{system}_api_{name}` | `stripe_api_prod` | API key, base URL |
| `{db}_{instance}_{env}` | `postgres_orders_prod` | Host, port, user, password |

### Rotating secrets

Pair Secret Manager with DAG-level connection testing. Add a lightweight connection-check task at the DAG start:

```python
def verify_connections(**context):
    """Fail fast if critical connections are misconfigured."""
    for conn_id in ["bigquery_prod", "salesforce_api_prod"]:
        conn = BaseHook.get_connection(conn_id)
        if not conn:
            raise ValueError(f"Connection {conn_id} not found")

check_conns = PythonOperator(
    task_id="verify_connections",
    python_callable=verify_connections,
    retries=0,  # no point retrying a missing connection
)
```

---

## 8. DAG Design Rules

### One DAG = one pipeline concept

A DAG should represent one logical data flow. Split by domain, not by convenience.

```
GOOD:
  orders_daily_load       (ingests orders)
  orders_daily_transform  (transforms orders)
  customers_daily_sync    (syncs customers)

BAD:
  everything_daily        (loads orders, transforms customers, sends reports, trains ML model)
```

Use `ExternalTaskSensor` or dataset-aware scheduling (Airflow 2.4+) to link DAGs.

### File layout

```
dags/
├── orders/
│   ├── orders_daily_load.py        # DAG definition only
│   ├── sql/
│   │   ├── delete_orders.sql
│   │   ├── insert_orders.sql
│   │   └── quality_checks.sql
│   └── utils/
│       └── validations.py          # reusable Python logic
├── customers/
│   ├── customers_daily_sync.py
│   └── sql/
│       └── merge_customers.sql
└── common/
    ├── default_args.py             # shared retry config
    ├── callbacks.py                # shared alert callbacks
    └── constants.py                # project IDs, dataset names
```

> **Non-negotiable (Principle 8):** SQL stays in SQL files. Python logic stays in Python modules. The DAG file is orchestration glue only.

### Tagging

Tag every DAG for filtering in the Airflow UI:

```python
with DAG(
    dag_id="orders_daily_load",
    tags=["orders", "tier-1", "daily", "bigquery"],
    ...
) as dag:
```

Use tier tags (`tier-1`, `tier-2`, `tier-3`) to indicate SLA priority.

---

## 9. Monitoring and Alerting

> **Non-negotiable (Principle 7):** Every pipeline must emit row counts in/out, execution duration, data freshness timestamp. Alert on anomalies, not just failures.

### on_failure_callback

Define a callback at the DAG level so every task failure triggers an alert:

```python
from airflow.providers.slack.hooks.slack_webhook import SlackWebhookHook

def alert_on_failure(context):
    """Send structured Slack alert on task failure."""
    task_instance = context["task_instance"]
    dag_id = context["dag"].dag_id
    task_id = task_instance.task_id
    execution_date = context["execution_date"].isoformat()
    log_url = task_instance.log_url
    exception = context.get("exception", "Unknown")

    message = (
        f":rotating_light: *Task Failed*\n"
        f"*DAG:* `{dag_id}`\n"
        f"*Task:* `{task_id}`\n"
        f"*Execution Date:* `{execution_date}`\n"
        f"*Error:* `{str(exception)[:200]}`\n"
        f"*Log:* {log_url}"
    )

    hook = SlackWebhookHook(slack_webhook_conn_id="slack_alerts")
    hook.send(text=message)

DEFAULT_TASK_ARGS = {
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=2),
    "on_failure_callback": alert_on_failure,
}
```

### SLA misses

Set SLAs on critical DAGs to detect when runs take longer than expected:

```python
with DAG(
    dag_id="orders_daily_load",
    default_args=DEFAULT_TASK_ARGS,
    sla_miss_callback=alert_on_sla_miss,
    ...
) as dag:

    critical_task = BigQueryInsertJobOperator(
        task_id="load_orders",
        sla=timedelta(hours=1),  # must complete within 1 hour
        ...
    )
```

### Data quality assertions (Fail loud)

> **Non-negotiable (Principle 3):** Silent data loss is worse than a failed run.

Add validation tasks after every load step:

```python
def validate_row_counts(**context):
    """Assert loaded row count is within expected bounds."""
    ds = context["ds"]
    hook = BigQueryHook(gcp_conn_id="bigquery_prod")
    result = hook.get_first(
        f"SELECT COUNT(*) FROM `project.dataset.orders` WHERE order_date = '{ds}'"
    )
    row_count = result[0]

    if row_count == 0:
        raise ValueError(f"Zero rows loaded for {ds} — possible upstream issue")

    # Log for observability (Principle 7)
    context["task_instance"].xcom_push(key="row_count", value=row_count)
    print(f"Loaded {row_count:,} rows for {ds}")

validate = PythonOperator(
    task_id="validate_row_counts",
    python_callable=validate_row_counts,
)

load_orders >> validate >> downstream_tasks
```

### Custom metrics with Cloud Monitoring

Push pipeline metrics to Cloud Monitoring for dashboards and alerting beyond Airflow:

```python
from google.cloud import monitoring_v3
import time

def emit_metric(project_id, metric_type, value, labels=None):
    """Push a custom metric to Cloud Monitoring."""
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    series = monitoring_v3.TimeSeries()
    series.metric.type = f"custom.googleapis.com/airflow/{metric_type}"
    series.resource.type = "global"
    if labels:
        for k, v in labels.items():
            series.metric.labels[k] = v

    point = monitoring_v3.Point()
    point.value.int64_value = value
    now = time.time()
    point.interval.end_time.seconds = int(now)
    series.points = [point]

    client.create_time_series(name=project_name, time_series=[series])

# Usage in a task:
emit_metric("my-project", "rows_loaded", row_count, {"dag": "orders_daily_load", "table": "orders"})
```

---

## Quick Reference: DAG Review Checklist

Before merging any DAG, verify:

- [ ] `default_args` includes retry config with exponential backoff
- [ ] Every task has an `execution_timeout`
- [ ] All loads use DELETE+INSERT, MERGE, or WRITE_TRUNCATE (no bare INSERT)
- [ ] All SQL uses `{{ ds }}` templating, not `CURRENT_DATE()`
- [ ] Sensors use `mode="reschedule"` with reasonable `timeout`
- [ ] `on_failure_callback` is set for alerting
- [ ] No credentials or secrets in DAG code
- [ ] SQL is in separate `.sql` files, not inline strings (unless trivial)
- [ ] DAG has meaningful tags including tier level
- [ ] Row count or data quality check exists after load steps
- [ ] `catchup` flag is set intentionally (not left to default)
- [ ] DAG file parses in <30 seconds (no heavy imports at module level)

See the full template at [../templates/airflow_dag_review.md](../templates/airflow_dag_review.md).
