"""
Airflow DAG — Postgres → warehouse (orders fact load).

**Illustrative example.** Adapt connection IDs, schema names, IAM, and target
table to your environment before production. The pipeline is intentionally
single-source / single-target (Postgres → Postgres) so the example stays
vendor-neutral; swap the target task for your warehouse loader if needed.

Pattern shown:
- TaskFlow API (`@dag`, `@task`) for explicit XCom typing
- Parameterized SQL via `PostgresHook.get_records(sql, parameters=...)` —
  never f-string interpolation of the `ds` macro into raw SQL
- Per-task `Variable.get()` (read at execute-time, not parse-time)
- Idempotent **DELETE + INSERT** for the partition under load
- Dataset-aware scheduling: emits `Dataset("warehouse://orders/fact_orders")`
  so downstream DAGs (e.g., dbt transforms) can `schedule=[that_dataset]`
- Source/target row-count parity check before declaring the partition loaded

Cross-references:
- ../../skills/data-engineering-best-practices/playbooks/02_airflow_reliability.md
- ../../skills/data-engineering-best-practices/playbooks/04_dbt_patterns.md  (dataset-aware scheduling)
- ../../skills/data-engineering-best-practices/playbooks/05_data_quality.md  (row-count + parameterized SQL pattern)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from airflow.datasets import Dataset
from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.models import Variable
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.sensors.postgres import SqlSensor


SOURCE_CONN_ID = "postgres_orders_source"
TARGET_CONN_ID = "postgres_orders_warehouse"

# Schema/table identifiers can't be SQL-parameter-bound; whitelist instead.
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def _safe_identifier(value: str, kind: str) -> str:
    if not _IDENTIFIER_PATTERN.match(value):
        raise AirflowFailException(f"unsafe {kind} identifier: {value!r}")
    return value

ORDERS_DATASET = Dataset("warehouse://orders/fact_orders")

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=1),
}


@dag(
    dag_id="postgres_to_orders",
    description="Daily batch ingestion of orders from source Postgres into the warehouse.",
    schedule="0 4 * * *",
    start_date=datetime(2026, 2, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    max_active_runs=1,
    tags=["postgres", "orders", "tier-1"],
)
def postgres_to_orders():
    """Idempotent Postgres → warehouse load with parity validation."""

    @task
    def resolve_target_schema() -> str:
        """Read environment-specific target schema at execute-time, not parse-time."""
        raw = Variable.get("ORDERS_TARGET_SCHEMA", default_var="orders")
        return _safe_identifier(raw, "schema")

    check_source = SqlSensor(
        task_id="check_source_partition_present",
        conn_id=SOURCE_CONN_ID,
        sql="SELECT 1 FROM orders WHERE order_date = %(order_date)s LIMIT 1;",
        parameters={"order_date": "{{ ds }}"},
        mode="reschedule",
        poke_interval=60,
        timeout=600,
    )

    @task
    def count_source_rows(*, ds: str = "") -> int:
        """Count partition rows in the source. Parameters are bound, not interpolated."""
        hook = PostgresHook(postgres_conn_id=SOURCE_CONN_ID)
        result = hook.get_first(
            "SELECT COUNT(*) FROM orders WHERE order_date = %(order_date)s;",
            parameters={"order_date": ds},
        )
        if result is None:
            raise AirflowFailException("source COUNT(*) returned no result")
        return int(result[0])

    @task
    def load_partition(target_schema: str, *, ds: str = "") -> int:
        """Idempotent DELETE + INSERT for the day's partition. Returns target row count."""
        target_schema = _safe_identifier(target_schema, "schema")
        source = PostgresHook(postgres_conn_id=SOURCE_CONN_ID)
        target = PostgresHook(postgres_conn_id=TARGET_CONN_ID)

        rows = source.get_records(
            """
            SELECT
              order_id,
              customer_id,
              order_date,
              order_status,
              total_amount,
              created_at,
              updated_at
            FROM orders
            WHERE order_date = %(order_date)s
            ORDER BY order_id;
            """,
            parameters={"order_date": ds},
        )

        with target.get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM {target_schema}.fact_orders WHERE order_date = %(order_date)s;",
                    {"order_date": ds},
                )
                if rows:
                    cursor.executemany(
                        f"""
                        INSERT INTO {target_schema}.fact_orders
                          (order_id, customer_id, order_date, order_status,
                           total_amount, created_at, updated_at, _loaded_at)
                        VALUES
                          (%s, %s, %s, %s, %s, %s, %s, NOW());
                        """,
                        rows,
                    )
            conn.commit()

        loaded = target.get_first(
            f"SELECT COUNT(*) FROM {target_schema}.fact_orders WHERE order_date = %(order_date)s;",
            parameters={"order_date": ds},
        )
        if loaded is None:
            raise AirflowFailException("target COUNT(*) returned no result after load")
        return int(loaded[0])

    @task(outlets=[ORDERS_DATASET])
    def assert_row_count_parity(source_count: int, target_count: int) -> None:
        """Fail loud on >0.1% drift between source and target row counts."""
        if source_count == 0 and target_count == 0:
            return
        denominator = max(source_count, 1)
        drift = abs(source_count - target_count) / denominator
        if drift > 0.001:
            raise AirflowFailException(
                f"row count drift exceeds 0.1%: source={source_count}, "
                f"target={target_count}, drift={drift:.4%}"
            )

    target_schema = resolve_target_schema()
    source_count = count_source_rows()
    target_count = load_partition(target_schema)

    check_source >> source_count
    check_source >> target_count
    assert_row_count_parity(source_count, target_count)


postgres_to_orders()
