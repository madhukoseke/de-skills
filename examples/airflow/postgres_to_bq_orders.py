"""
Airflow DAG: PostgreSQL → BigQuery Orders Pipeline

Daily batch ingestion from PostgreSQL into BigQuery with ELT pattern.
- Extract: PostgreSQL → GCS (Parquet)
- Load: GCS → BigQuery (WRITE_TRUNCATE per partition)
- Transform: dbt staging, curation, mart
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.sensors.postgres import SqlSensor
from airflow.providers.google.cloud.operators.gcs import GCSCreateBucketOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryCheckOperator,
    BigQueryInsertJobOperator,
)
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.models import Variable
from airflow.utils.task_group import TaskGroup

# Configuration
POSTGRES_CONN_ID = "postgres_production"
GCP_PROJECT = Variable.get("GCP_PROJECT_ID")
GCS_BUCKET = Variable.get("GCS_LANDING_BUCKET")
BQ_DATASET = "raw_postgres"
BQ_TABLE = "fact_orders"

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2026, 2, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}

dag = DAG(
    "postgres_to_bq_orders",
    default_args=default_args,
    description="Daily batch ingestion: PostgreSQL orders → BigQuery",
    schedule_interval="0 4 * * *",  # 04:00 UTC daily
    catchup=False,
    tags=["postgres", "bigquery", "orders"],
)

# SLA callback
def sla_callback(context):
    """Alert if SLA is missed."""
    print(f"SLA missed for DAG {context['dag'].dag_id} on {context['ds']}")
    # TODO: Send alert to Slack/PagerDuty


dag.sla_miss_callback = sla_callback


def extract_postgres_to_gcs(ds, **context):
    """
    Extract PostgreSQL data to GCS in chunked fashion.
    Writes date-partitioned Parquet files.
    """
    import logging
    from google.cloud import storage
    from sqlalchemy import create_engine
    import pandas as pd
    from datetime import datetime as dt

    logger = logging.getLogger(__name__)

    # Get Airflow connection
    from airflow.models import Connection
    from airflow import settings

    conn = settings.Session().query(Connection).filter(
        Connection.conn_id == POSTGRES_CONN_ID
    ).first()

    postgres_url = f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"
    engine = create_engine(postgres_url)

    # Extract data with watermark (incremental)
    query = f"""
    SELECT
      order_id,
      customer_id,
      order_date,
      status,
      total_amount,
      created_at,
      updated_at,
      MD5(CONCAT(order_id::text, customer_id::text)) AS _row_hash
    FROM orders
    WHERE order_date = '{ds}'
    ORDER BY order_id
    """

    # Chunk extraction: 100k rows per chunk
    chunk_size = 100000
    chunk_num = 0
    total_rows = 0

    with engine.connect() as connection:
        for chunk in pd.read_sql(query, connection, chunksize=chunk_size):
            chunk["_loaded_at"] = dt.now()
            chunk["_batch_id"] = f"{ds}_{chunk_num:03d}"

            # Write to GCS
            gcs_path = f"raw/orders/date={ds}/part-{chunk_num:05d}.parquet"
            chunk.to_parquet(f"gs://{GCS_BUCKET}/{gcs_path}", index=False)
            total_rows += len(chunk)
            chunk_num += 1
            logger.info(f"Wrote chunk {chunk_num} ({len(chunk)} rows) to {gcs_path}")

    logger.info(f"Extraction complete: {total_rows} rows in {chunk_num} chunks")
    return {"total_rows": total_rows, "chunks": chunk_num}


def validate_row_count(ds, ti, **context):
    """
    Validate extracted row count matches source.
    Allow ≤0.1% drift.
    """
    import logging
    from sqlalchemy import create_engine, text
    from airflow.models import Connection
    from airflow import settings

    logger = logging.getLogger(__name__)

    # Get postgres count
    conn = settings.Session().query(Connection).filter(
        Connection.conn_id == POSTGRES_CONN_ID
    ).first()
    postgres_url = f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"
    engine = create_engine(postgres_url)

    with engine.connect() as connection:
        result = connection.execute(
            text(f"SELECT COUNT(*) FROM orders WHERE order_date = '{ds}'")
        )
        postgres_count = result.scalar()

    # Get GCS count (sum of chunk rows)
    extracted = ti.xcom_pull(task_ids="extract_postgres_to_gcs")
    gcs_count = extracted["total_rows"]

    drift = abs(postgres_count - gcs_count) / postgres_count
    logger.info(
        f"Row count validation: Postgres={postgres_count}, GCS={gcs_count}, drift={drift:.4%}"
    )

    if drift > 0.001:
        raise ValueError(
            f"Row count drift exceeds threshold: {drift:.4%} > 0.1%"
        )
    logger.info("Row count validation passed")


# Task: Check PostgreSQL source
check_postgres = SqlSensor(
    task_id="check_postgres_source",
    conn_id=POSTGRES_CONN_ID,
    sql="SELECT 1 FROM orders WHERE order_date = {{ ds }} LIMIT 1",
    poke_interval=60,
    timeout=600,
    dag=dag,
)

# Task: Extract to GCS
extract_task = PythonOperator(
    task_id="extract_postgres_to_gcs",
    python_callable=extract_postgres_to_gcs,
    provide_context=True,
    dag=dag,
)

# Task: Validate row counts
validate_task = PythonOperator(
    task_id="validate_row_count",
    python_callable=validate_row_count,
    provide_context=True,
    dag=dag,
)

# Task: Load GCS → BigQuery
load_bq_task = GCSToBigQueryOperator(
    task_id="load_gcs_to_bq_raw",
    bucket=GCS_BUCKET,
    source_objects=[f"raw/orders/date={{{{ ds }}}}/part-*.parquet"],
    destination_project_dataset_table=f"{GCP_PROJECT}.{BQ_DATASET}.{BQ_TABLE}",
    source_format="PARQUET",
    write_disposition="WRITE_TRUNCATE",
    allow_quoted_newlines=True,
    skip_leading_rows=0,
    autodetect=False,
    create_disposition="CREATE_IF_NEEDED",
    schema_update_options=["ALLOW_FIELD_ADDITION"],
    dag=dag,
)

# Task: Validate BQ row count
validate_bq_task = BigQueryCheckOperator(
    task_id="validate_bq_row_count",
    sql=f"""
    SELECT
      CASE
        WHEN ABS(CAST(bq_count AS FLOAT64) - CAST(postgres_count AS FLOAT64))
             / postgres_count > 0.001
        THEN 0
        ELSE 1
      END
    FROM (
      SELECT
        (SELECT COUNT(*) FROM `{GCP_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
         WHERE order_date = '{{{{ ds }}}}') AS bq_count,
        {{ ti.xcom_pull(task_ids='extract_postgres_to_gcs')['total_rows'] }} AS postgres_count
    )
    """,
    use_legacy_sql=False,
    dag=dag,
)

# Task: dbt staging
dbt_stg = BashOperator(
    task_id="run_dbt_stg",
    bash_command="cd /home/airflow && dbt run --select stg_orders",
    dag=dag,
)

# Task: dbt curation
dbt_cur = BashOperator(
    task_id="run_dbt_cur",
    bash_command="cd /home/airflow && dbt run --select fact_orders",
    dag=dag,
)

# Task: dbt mart
dbt_mart = BashOperator(
    task_id="run_dbt_mart",
    bash_command="cd /home/airflow && dbt run --select daily_summary",
    dag=dag,
)

# DAG dependencies
check_postgres >> extract_task >> validate_task >> load_bq_task >> validate_bq_task
validate_bq_task >> dbt_stg >> dbt_cur >> dbt_mart
