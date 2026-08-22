from airflow import DAG
from airflow.operators.python import PythonOperator


def publish_orders():
    # Fixture defect: an unbounded append is neither interval-scoped nor replay-safe.
    warehouse.execute("INSERT INTO curated.orders SELECT * FROM staging.orders")


dag = DAG("orders", schedule="@daily")
PythonOperator(task_id="publish", python_callable=publish_orders, dag=dag, retries=5)
