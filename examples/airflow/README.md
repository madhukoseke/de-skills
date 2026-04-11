# Airflow examples (illustrative)

This directory holds **reference DAGs only**. They are not executed by this repository, are not installed by `npx skills add`, and require your own Composer/Airflow environment plus provider packages (`apache-airflow-providers-*`).

Use these files as patterns to compare against the canonical reliability guidance in [`skills/data-engineering-best-practices/playbooks/02_airflow_reliability.md`](../../skills/data-engineering-best-practices/playbooks/02_airflow_reliability.md).

| File | Intent |
|------|--------|
| [`postgres_to_bq_orders.py`](postgres_to_bq_orders.py) | Sample batch pipeline: Postgres → GCS → BigQuery with validation hooks (adapt connection IDs, paths, and dbt commands before use). |
