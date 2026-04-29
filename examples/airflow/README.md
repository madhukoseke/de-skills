# Airflow examples (illustrative)

This directory holds **reference DAGs only**. They are not executed by this repository, are not installed by `npx skills add`, and require your own Airflow environment plus provider packages (`apache-airflow-providers-postgres`).

Use these files as patterns to compare against the canonical reliability guidance in [`skills/data-engineering-best-practices/playbooks/02_airflow_reliability.md`](../../skills/data-engineering-best-practices/playbooks/02_airflow_reliability.md).

| File | Intent |
|------|--------|
| [`postgres_to_orders.py`](postgres_to_orders.py) | Postgres → warehouse fact-orders load. Demonstrates: TaskFlow API, parameterized SQL via `PostgresHook`, idempotent DELETE+INSERT for one partition, dataset-aware scheduling outlet, and source/target row-count parity check. Adapt connection IDs and target schema before use. |

## What this example deliberately does NOT do

- **No f-string SQL.** All `WHERE order_date = ...` filters use bound parameters (`%(order_date)s`) so the `ds` macro cannot bleed into the SQL string. See [`playbooks/05_data_quality.md`](../../skills/data-engineering-best-practices/playbooks/05_data_quality.md) §3 for the same pattern in the canonical guidance.
- **No top-level `Variable.get()`.** Reads happen inside `@task` bodies so the value is fetched at execute-time, not on every DAG-file scan.
- **No raw `settings.Session().query(Connection)`.** Connections are accessed exclusively through `PostgresHook`.
- **No vendor-specific operators.** The example is Postgres-only; swap the loader task for your warehouse of choice (BigQuery, Snowflake, Redshift, Databricks) without changing the rest of the DAG.

## Required Airflow connections

| Connection ID | Purpose |
|---------------|---------|
| `postgres_orders_source` | Source operational Postgres database holding `orders` |
| `postgres_orders_warehouse` | Target Postgres-compatible warehouse holding `<schema>.fact_orders` |

## Required Airflow Variable

| Variable | Purpose | Default |
|----------|---------|---------|
| `ORDERS_TARGET_SCHEMA` | Warehouse schema where `fact_orders` lives | `orders` |

## Pairing with downstream DAGs

The DAG emits `Dataset("warehouse://orders/fact_orders")` on successful partition load. Downstream transformation DAGs can subscribe with:

```python
from airflow.datasets import Dataset

@dag(schedule=[Dataset("warehouse://orders/fact_orders")], ...)
def orders_marts():
    ...
```

This eliminates `ExternalTaskSensor` chains. See [`playbooks/04_dbt_patterns.md`](../../skills/data-engineering-best-practices/playbooks/04_dbt_patterns.md) §5 (dataset-aware scheduling).
