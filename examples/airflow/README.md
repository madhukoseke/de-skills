# Airflow example

`postgres_to_orders.py` is a review fixture showing bounded data intervals,
parameterized SQL, retry-aware task boundaries, and dataset publication. Evaluate
it with the canonical
[orchestration guidance](../../skills/data-engineering/references/orchestration-and-delivery.md)
and [quality guidance](../../skills/data-engineering/references/contracts-quality-and-testing.md).

The example is not a production-ready DAG: connection policy, source semantics,
capacity, ownership, and deployment controls remain environment-specific.
