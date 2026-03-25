---
title: "Orchestration Patterns"
description: "Modern pipeline orchestration: Airflow vs Prefect vs Dagster vs Temporal, DAG-as-code, dynamic pipelines, CI/CD for orchestration, and cross-tool decision guide"
tags: [orchestration, airflow, prefect, dagster, temporal, dag-as-code, ci-cd, dynamic-pipelines]
---

# Playbook 10 — Orchestration Patterns

Covers: orchestrator selection, DAG-as-code principles, dynamic pipelines, task dependencies, CI/CD for orchestration code, and cross-cutting patterns applicable regardless of tool.

---

## 1. Orchestrator Selection

| Criterion | Airflow | Prefect | Dagster | Temporal |
|-----------|---------|---------|---------|---------|
| **Maturity** | Very high (10+ yrs) | High | High | High |
| **Ecosystem** | Largest (400+ operators) | Growing | Growing | Growing |
| **Deployment complexity** | High (scheduler, workers, DB) | Medium (server + agent) | Medium | Medium |
| **DAG authoring UX** | Python (verbose) | Python (decorator-first) | Python (assets-first) | Go/Java/Python/TypeScript |
| **Data-aware scheduling** | Limited (sensors) | Limited | Native (asset materialization) | Not native |
| **Dynamic tasks** | Airflow 2.3+ (dynamic task mapping) | Native | Native | Native |
| **Long-running workflows** | Poor (DAG timeout) | Moderate | Moderate | Excellent (durable execution) |
| **Best for** | DE pipelines, batch ETL | Data science, ML pipelines | Analytics engineering, dbt-heavy | Microservices orchestration, human-in-the-loop |

**Default recommendation: Airflow for batch DE pipelines** if you already have it. Dagster if you are greenfield and heavily dbt/asset-oriented. Temporal for workflow orchestration outside DE (e.g., multi-step API flows with human approval steps).

---

## 2. DAG-as-Code Principles

These apply regardless of orchestrator:

1. **No business logic in orchestration code** — DAGs/flows only define structure, schedules, and parameter passing. SQL stays in SQL files; transforms in dedicated modules.
2. **No hardcoded credentials** — All secrets via secrets manager or orchestrator secret backend.
3. **No `datetime.now()` in scheduling logic** — Use the orchestrator's execution date macro/variable.
4. **Fail fast, fail loudly** — Do not catch exceptions and continue; surface failures immediately.
5. **Idempotent tasks** — Every task must be safely re-runnable without side effects.
6. **One task = one unit of failure** — Tasks should be granular enough that failures are pinpointed without being so granular that overhead dominates.
7. **Parameterize everything** — Date, environment, table name, batch size — all via parameters, never hardcoded.

---

## 3. Airflow DAG Patterns

See also [02_airflow_reliability.md](02_airflow_reliability.md) for retry and idempotency patterns.

### Standard DAG template
```python
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

@dag(
    dag_id="orders_daily_load",
    description="Load daily orders from source to warehouse",
    schedule="0 6 * * *",         # 06:00 UTC daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,             # prevent concurrent runs
    tags=["orders", "daily", "warehouse"],
    default_args={
        "owner": "data-engineering",
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=30),
        "execution_timeout": timedelta(hours=2),
        "on_failure_callback": alert_on_failure,
    },
    doc_md="""
    ## orders_daily_load
    Loads daily order records from staging to the warehouse fact table.
    Idempotent: DELETE + INSERT for the execution date partition.
    **SLA:** Data available by 08:00 UTC. **Owner:** #data-engineering
    """,
)
def orders_daily_load():

    wait_for_source = FileSensor(
        task_id="wait_for_source_file",
        filepath="landing/orders/{{ ds }}/",
        mode="reschedule",
        timeout=3600,
        soft_fail=False,
    )

    load_to_staging = SQLExecuteQueryOperator(
        task_id="load_to_staging",
        conn_id="warehouse_default",
        sql="sql/load_orders_staging.sql",
        parameters={"execution_date": "{{ ds }}"},
    )

    load_to_warehouse = SQLExecuteQueryOperator(
        task_id="load_to_warehouse",
        conn_id="warehouse_default",
        sql="sql/merge_orders_fact.sql",
        parameters={"execution_date": "{{ ds }}"},
    )

    dq_checks = SQLExecuteQueryOperator(
        task_id="data_quality_checks",
        conn_id="warehouse_default",
        sql="sql/dq_orders_fact.sql",
        parameters={"execution_date": "{{ ds }}"},
    )

    wait_for_source >> load_to_staging >> load_to_warehouse >> dq_checks

orders_daily_load()
```

### Dynamic task mapping (Airflow 2.3+)
```python
@dag(...)
def multi_tenant_load():

    @task
    def get_tenants():
        return ["tenant_a", "tenant_b", "tenant_c"]  # from config or DB query

    @task
    def load_tenant(tenant_id: str):
        # Runs one task instance per tenant
        run_load(tenant_id=tenant_id)

    load_tenant.expand(tenant_id=get_tenants())

multi_tenant_load()
```

---

## 4. Prefect Patterns

```python
from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta

@task(
    retries=3,
    retry_delay_seconds=60,
    cache_key_fn=task_input_hash,     # idempotent: skip if same inputs already ran
    cache_expiration=timedelta(days=1),
)
def extract_orders(execution_date: str) -> list:
    return fetch_orders_from_api(date=execution_date)

@task(retries=2, retry_delay_seconds=30)
def load_to_warehouse(orders: list, execution_date: str):
    run_merge(orders, partition=execution_date)

@flow(
    name="orders-daily-load",
    description="Daily order ingestion pipeline",
    log_prints=True,
)
def orders_pipeline(execution_date: str = None):
    if execution_date is None:
        from datetime import date
        execution_date = str(date.today())

    orders = extract_orders(execution_date)
    load_to_warehouse(orders, execution_date)

# Deploy via Prefect Cloud or self-hosted server
```

---

## 5. Dagster Patterns (Asset-First)

```python
from dagster import asset, AssetIn, define_asset_job, ScheduleDefinition, Definitions

@asset(
    group_name="orders",
    description="Cleaned staging orders from source system",
    io_manager_key="warehouse_io_manager",
)
def stg_orders(context, raw_orders):
    """Transform raw orders into clean staging records."""
    return clean_and_validate(raw_orders)

@asset(
    group_name="orders",
    ins={"stg_orders": AssetIn()},
    description="Fact table: one row per order, partitioned by order_date",
    partitions_def=DailyPartitionsDefinition(start_date="2024-01-01"),
)
def fact_orders(context, stg_orders):
    """Merge staged orders into the warehouse fact table."""
    return merge_to_fact(stg_orders, partition=context.partition_key)

orders_job = define_asset_job("orders_daily_job", selection=["stg_orders", "fact_orders"])

orders_schedule = ScheduleDefinition(
    job=orders_job,
    cron_schedule="0 6 * * *",
)

defs = Definitions(
    assets=[stg_orders, fact_orders],
    jobs=[orders_job],
    schedules=[orders_schedule],
)
```

---

## 6. CI/CD for Orchestration Code

Orchestration code is production code. Apply the same CI/CD rigor as application code.

### CI pipeline requirements
```yaml
# .github/workflows/dag-ci.yml
jobs:
  test:
    steps:
      - name: Lint (flake8 / ruff)
        run: ruff check dags/ plugins/ jobs/

      - name: Type check (mypy)
        run: mypy dags/ plugins/ jobs/ --ignore-missing-imports

      - name: Unit tests
        run: pytest tests/unit/ -v --tb=short

      - name: DAG import test (Airflow-specific)
        run: |
          python -c "
          from airflow.models import DagBag
          bag = DagBag(dag_folder='dags/', include_examples=False)
          assert not bag.import_errors, f'DAG import errors: {bag.import_errors}'
          print(f'{len(bag.dags)} DAGs loaded successfully')
          "

      - name: Integration tests (against test DB)
        run: pytest tests/integration/ -v --tb=short
        env:
          AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: ${{ secrets.TEST_DB_CONN }}
```

### DAG import test (essential for Airflow)
The DAG import test catches:
- Syntax errors in DAG files
- Import errors (missing dependencies)
- Top-level code that raises exceptions at parse time
- Circular imports

```python
# tests/unit/test_dag_integrity.py
from airflow.models import DagBag

def test_no_import_errors():
    bag = DagBag(dag_folder="dags/", include_examples=False)
    assert not bag.import_errors, f"Import errors: {bag.import_errors}"

def test_dag_count():
    bag = DagBag(dag_folder="dags/", include_examples=False)
    assert len(bag.dags) > 0, "No DAGs found"

def test_dag_tags():
    bag = DagBag(dag_folder="dags/", include_examples=False)
    for dag_id, dag in bag.dags.items():
        assert dag.tags, f"DAG '{dag_id}' has no tags — required for filtering"

def test_default_args():
    bag = DagBag(dag_folder="dags/", include_examples=False)
    for dag_id, dag in bag.dags.items():
        assert dag.default_args.get("retries") is not None, \
            f"DAG '{dag_id}' missing 'retries' in default_args"
```

### Deployment strategy
```
main branch  → auto-deploy to dev environment (sync DAG folder)
release tag  → deploy to staging → manual approval → deploy to prod
```

**Never manually edit DAG files in production.** All changes go through git + CI.

---

## 7. Cross-Cutting Patterns

### Dependency management
```python
# Explicit task dependencies (Airflow)
extract >> transform >> load >> dq_check >> notify_downstream

# Multiple predecessors
[extract_orders, extract_customers] >> enrich >> load

# Fan-out
load >> [dq_check, update_metadata, trigger_downstream_dag]
```

### Cross-DAG dependencies (ExternalTaskSensor / triggering)
```python
from airflow.sensors.external_task import ExternalTaskSensor

wait_for_upstream = ExternalTaskSensor(
    task_id="wait_for_upstream_pipeline",
    external_dag_id="customers_daily_load",
    external_task_id="data_quality_checks",
    execution_date_fn=lambda dt: dt,  # same execution date
    mode="reschedule",
    timeout=7200,
    poke_interval=300,
)
```

### Monitoring and alerting callback
```python
def alert_on_failure(context):
    """Send alert to on-call channel on task failure."""
    dag_id = context["dag"].dag_id
    task_id = context["task_instance"].task_id
    execution_date = context["execution_date"]
    log_url = context["task_instance"].log_url

    message = (
        f":red_circle: *Pipeline failure*\n"
        f"DAG: `{dag_id}` | Task: `{task_id}`\n"
        f"Execution date: `{execution_date}`\n"
        f"Logs: {log_url}"
    )
    send_slack_alert(channel="#data-oncall", message=message)
```

### SLA miss callback
```python
from airflow.models import DAG

def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    send_slack_alert(
        channel="#data-oncall",
        message=f":warning: SLA missed for DAG `{dag.dag_id}`. "
                f"Blocking tasks: {blocking_task_list}"
    )

with DAG(
    dag_id="orders_daily_load",
    sla_miss_callback=sla_miss_callback,
    ...
):
    ...
```

---

## 8. Anti-Patterns

| Anti-Pattern | Impact | Fix |
|-------------|--------|-----|
| Business logic in DAG file | Untestable; logic hidden in orchestration | Move to separate Python module or SQL file |
| `catchup=True` with no idempotency | Backfill corrupts data | Ensure idempotency first; then consider catchup |
| Top-level DB queries in DAG file | Runs at parse time; slows scheduler | Move DB calls inside task callables |
| Hardcoded `datetime.now()` | Non-deterministic; backfill produces wrong results | Use `{{ ds }}` / `{{ data_interval_start }}` |
| No `max_active_runs=1` for stateful pipelines | Concurrent runs create duplicates | Set `max_active_runs=1` for non-idempotent pipelines |
| `task_concurrency` set to 1 globally | Unnecessarily serializes independent tasks | Only limit concurrency where resource contention exists |
| No failure callback | Silent failures; missed SLAs go unnoticed | Add `on_failure_callback` and `sla_miss_callback` |
| One giant DAG with 50+ tasks | Hard to debug; rerun scope too large | Split into domain-scoped DAGs with ExternalTaskSensor |
| Manual DAG file edits in production | Drift from git; no review; no rollback | All changes via git + CI/CD |
| No DAG import test in CI | Broken DAGs deploy silently | Add DAG import test as required CI step |
