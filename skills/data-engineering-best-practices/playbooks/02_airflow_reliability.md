---
title: "Airflow Reliability"
description: "DAG reliability patterns: retries, idempotency, sensors, backfill"
tags: [airflow, reliability, retries, idempotency]
related_templates:
  - ../templates/airflow_dag_review.md
  - ../templates/runbook.md
---

# Airflow Reliability Playbook

This playbook codifies production-tested patterns for building reliable Airflow DAGs. Every recommendation here ties back to the non-negotiable principles in [SKILL.md](../SKILL.md) — especially **Idempotency first**, **Retry with backoff**, **Fail loud**, and **Separation of concerns**.

---

## 1. Retry Strategy

> **Non-negotiable (Principle 6):** All external calls must use exponential backoff with jitter.

Every task that touches an external system (warehouse, APIs, object storage, databases) must define retries explicitly. Never rely on Airflow's defaults.

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
| Long-running warehouse query (>1h) | `execution_timeout=timedelta(hours=4)` | Avoid premature kill |
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
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

delete_and_insert = SQLExecuteQueryOperator(
    task_id="load_orders_partition",
    conn_id="warehouse_default",
    sql="""
        -- Step 1: delete the target partition
        DELETE FROM orders
        WHERE order_date = '{{ ds }}';

        -- Step 2: insert fresh data for that date
        INSERT INTO orders
        SELECT *
        FROM orders_staging
        WHERE order_date = '{{ ds }}';
    """,
)
```

**Why this works:** If the task is retried or re-run for the same `ds`, the DELETE removes any partial or duplicate data before re-inserting.

### Pattern B: MERGE (preferred for SCD/dimension updates)

Best for slowly-changing dimensions or upsert patterns.

```python
merge_customers = SQLExecuteQueryOperator(
    task_id="merge_customers",
    conn_id="warehouse_default",
    sql="""
        MERGE INTO customers AS target
        USING customers_staging AS source
        ON target.customer_id = source.customer_id
        WHEN MATCHED THEN
            UPDATE SET
                target.name       = source.name,
                target.email      = source.email,
                target.updated_at = source.updated_at
        WHEN NOT MATCHED THEN
            INSERT (customer_id, name, email, created_at, updated_at)
            VALUES (source.customer_id, source.name, source.email,
                    source.created_at, source.updated_at);
    """,
)
```

### Pattern C: Truncate + Insert (full-partition overwrite)

Use `TRUNCATE` on a staging/partition table before inserting, ensuring idempotency without MERGE complexity.

```python
truncate_and_load = SQLExecuteQueryOperator(
    task_id="truncate_and_load_partition",
    conn_id="warehouse_default",
    sql="""
        TRUNCATE TABLE orders_staging;

        INSERT INTO orders_staging
        SELECT * FROM orders_raw
        WHERE order_date = '{{ ds }}';
    """,
)
```

### Anti-pattern: bare INSERT

```python
# NEVER DO THIS for dimension or fact loads
INSERT INTO orders
SELECT * FROM staging WHERE order_date = '{{ ds }}';
```

If retried, this duplicates data. There is no safe recovery without manual intervention.

---

## 3. Sensor Best Practices

Sensors wait for external conditions. Misconfigured sensors are the number-one cause of Airflow worker pool exhaustion.

### Standard sensor configuration

```python
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.sensors.filesystem import FileSensor

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

wait_for_file = FileSensor(
    task_id="wait_for_landing_file",
    filepath="/data/landing/orders/{{ ds }}/orders.parquet",
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
wait_for_enrichment = FileSensor(
    task_id="wait_for_optional_enrichment",
    filepath="/data/enrichment/geo/{{ ds }}/geo_lookup.csv",
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
    bash_command="rm -rf /tmp/pipeline/{{ ds }}/",
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

full_load        = SQLExecuteQueryOperator(task_id="full_load", ...)
incremental_load = SQLExecuteQueryOperator(task_id="incremental_load", ...)
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
    SELECT * FROM events
    WHERE event_date = '{{ ds }}'
"""

# WRONG: uses wall-clock time, breaks backfill
query = """
    SELECT * FROM events
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
- Limit parallelism with `--max-active-runs` on the DAG to avoid overwhelming the warehouse or APIs during large backfills.

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
| Storing secrets in DAG code | Security risk, leaks in logs/UI | Use Airflow Connections + secret backend |
| `trigger_rule="all_done"` everywhere | Silently proceeds past failures | Use `all_done` only for cleanup tasks |
| No `execution_timeout` on tasks | Zombie tasks hold resources indefinitely | Set explicit timeout on every task |

---

## 7. Connection and Secret Management

> **Non-negotiable:** Never store credentials in DAG code, environment variables, or files accessible to the DAG.

### Use a secret backend

Configure Airflow to pull secrets from a secrets manager (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, etc.):

```python
# airflow.cfg / environment config
# AIRFLOW__SECRETS__BACKEND=airflow.providers.hashicorp.secrets.vault.VaultBackend
# AIRFLOW__SECRETS__BACKEND_KWARGS={"connections_path": "airflow/connections", "variables_path": "airflow/variables", "url": "http://vault:8200"}

# In DAG code — just reference the connection ID
from airflow.hooks.base import BaseHook

conn     = BaseHook.get_connection("warehouse_prod")
password = conn.password  # pulled from secrets manager at runtime
```

### Connection naming conventions

Use a consistent prefix scheme so connections are discoverable:

| Pattern | Example | Contains |
|---------|---------|----------|
| `{system}_{environment}` | `warehouse_prod` | Host, user, password |
| `{system}_api_{name}` | `stripe_api_prod` | API key, base URL |
| `{db}_{instance}_{env}` | `postgres_orders_prod` | Host, port, user, password |

### Rotating secrets

Pair secret rotation with a lightweight connection-check task at the DAG start:

```python
def verify_connections(**context):
    """Fail fast if critical connections are misconfigured."""
    for conn_id in ["warehouse_prod", "source_api_prod"]:
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
    └── constants.py                # connection IDs, schema names
```

> **Non-negotiable (Principle 8):** SQL stays in SQL files. Python logic stays in Python modules. The DAG file is orchestration glue only.

### Tagging

Tag every DAG for filtering in the Airflow UI:

```python
with DAG(
    dag_id="orders_daily_load",
    tags=["orders", "tier-1", "daily", "warehouse"],
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
    task_instance  = context["task_instance"]
    dag_id         = context["dag"].dag_id
    task_id        = task_instance.task_id
    execution_date = context["execution_date"].isoformat()
    log_url        = task_instance.log_url
    exception      = context.get("exception", "Unknown")

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

    critical_task = SQLExecuteQueryOperator(
        task_id="load_orders",
        sla=timedelta(hours=1),  # must complete within 1 hour
        ...
    )
```

### Data quality assertions (Fail loud)

> **Non-negotiable (Principle 3):** Silent data loss is worse than a failed run.

Add validation tasks after every load step:

```python
from airflow.providers.common.sql.operators.sql import SQLCheckOperator

check_freshness = SQLCheckOperator(
    task_id="check_orders_freshness",
    conn_id="warehouse_prod",
    sql="""
        SELECT MAX(loaded_at) > NOW() - INTERVAL '2 hours' AS is_fresh
        FROM orders
    """,
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

load_orders >> [check_freshness, check_no_duplicates] >> downstream_tasks
```

---

## Quick Reference: DAG Review Checklist

Before merging any DAG, verify:

- [ ] `default_args` includes retry config with exponential backoff
- [ ] Every task has an `execution_timeout`
- [ ] All loads use DELETE+INSERT, MERGE, or TRUNCATE+INSERT (no bare INSERT)
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
