---
title: "Testing Strategies for Data Engineering"
description: "The DE testing pyramid: SQL unit tests, PySpark testing, dbt tests, contract testing, integration testing, and E2E validation"
tags: [testing, unit-tests, integration-tests, dbt-tests, pyspark-testing, contract-testing, data-quality]
---

# Playbook 11 — Testing Strategies for Data Engineering

Covers: the DE testing pyramid, SQL unit tests, PySpark/Spark testing, dbt test suite, contract testing, integration testing, and E2E pipeline validation.

---

## 1. The DE Testing Pyramid

```
                  ┌─────────────┐
                  │    E2E      │  ← Full pipeline run; slow; catches integration issues
                  │  (few)      │
                 ┌┴─────────────┴┐
                 │  Integration  │  ← Real DB/Spark; validates data flow across components
                 │  (moderate)   │
                ┌┴───────────────┴┐
                │   Contract      │  ← Schema and SLA assertions at every boundary
                │   (many)        │
               ┌┴─────────────────┴┐
               │   Unit / dbt test  │  ← Pure logic; fast; runs in CI on every commit
               │   (most)           │
               └───────────────────┘
```

**Rule: most tests should be unit/dbt tests. Integration and E2E tests are valuable but expensive — keep them focused on critical paths.**

---

## 2. SQL Unit Testing

Test SQL transformation logic in isolation using test fixtures (small, controlled datasets).

### Pattern: CREATE TABLE AS + assertion
```sql
-- test_apply_discount.sql
-- Setup: create test input
CREATE TEMP TABLE test_orders AS
SELECT 'ORD-001' AS order_id, 100.00 AS total_amount, TRUE  AS is_vip UNION ALL
SELECT 'ORD-002',             100.00,                  FALSE;

-- Execute: run the function/transform under test
CREATE TEMP TABLE test_result AS
SELECT
    order_id,
    total_amount,
    is_vip,
    CASE WHEN is_vip THEN total_amount * 0.9 ELSE total_amount END AS discounted_amount
FROM test_orders;

-- Assert
SELECT
    CASE
        WHEN (SELECT discounted_amount FROM test_result WHERE order_id = 'ORD-001') = 90.00
         AND (SELECT discounted_amount FROM test_result WHERE order_id = 'ORD-002') = 100.00
        THEN 'PASS'
        ELSE 'FAIL'
    END AS test_result;

-- Cleanup
DROP TABLE test_orders;
DROP TABLE test_result;
```

### dbt unit tests (dbt 1.8+)
```yaml
# models/intermediate/int_orders_enriched.yml
unit_tests:
  - name: test_vip_discount_applied
    model: int_orders_enriched
    given:
      - input: ref('stg_orders')
        rows:
          - {order_id: ORD-001, total_amount: 100.0, customer_tier: VIP}
          - {order_id: ORD-002, total_amount: 100.0, customer_tier: STANDARD}
    expect:
      rows:
        - {order_id: ORD-001, discounted_amount: 90.0}
        - {order_id: ORD-002, discounted_amount: 100.0}

  - name: test_null_total_amount_handled
    model: int_orders_enriched
    given:
      - input: ref('stg_orders')
        rows:
          - {order_id: ORD-003, total_amount: null, customer_tier: STANDARD}
    expect:
      rows:
        - {order_id: ORD-003, discounted_amount: null}
```

---

## 3. dbt Test Suite

Every dbt model must have tests. Minimum required: `unique` + `not_null` on primary key.

### Schema tests (schema.yml)
```yaml
models:
  - name: fact_orders
    description: "One row per order, partitioned by order_date"
    columns:
      - name: order_id
        description: "Natural order identifier from source system"
        tests:
          - unique
          - not_null

      - name: customer_id
        tests:
          - not_null
          - relationships:
              to: ref('dim_customers')
              field: customer_id
              severity: error

      - name: total_amount
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              inclusive: true

      - name: order_status
        tests:
          - accepted_values:
              values: ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
              severity: error
```

### Custom singular tests
```sql
-- tests/assert_no_future_order_dates.sql
-- Fails if any order has a date in the future
SELECT
    order_id,
    order_date
FROM {{ ref('fact_orders') }}
WHERE order_date > CURRENT_DATE
```

### Source freshness tests
```yaml
sources:
  - name: raw
    tables:
      - name: orders
        loaded_at_field: _ingested_at
        freshness:
          warn_after: {count: 6, period: hour}
          error_after: {count: 12, period: hour}
```

### Test coverage targets
| Layer | Minimum Tests |
|-------|--------------|
| Staging | `not_null` + `unique` on PK; `accepted_values` for status columns |
| Intermediate | Row count assertion; null checks on join keys; referential integrity |
| Mart (fact) | `unique` + `not_null` PK; referential integrity to all dims; range checks on measures |
| Mart (dim) | `unique` + `not_null` on SK and BK; SCD `is_current` check |

---

## 4. PySpark Testing

See [08_spark_patterns.md §8](08_spark_patterns.md) for full PySpark test examples.

### Key principles
- Use `local[2]` SparkSession in pytest (no cluster required for unit tests).
- Keep SparkSession fixture at `scope="session"` — creating one per test is slow.
- Set `spark.sql.shuffle.partitions=2` for tests to avoid unnecessary overhead.
- Separate pure Python logic from Spark logic — test pure Python with plain pytest; test Spark logic with the local SparkSession.

### Testing schema enforcement
```python
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

EXPECTED_SCHEMA = StructType([
    StructField("order_id", StringType(), nullable=False),
    StructField("total_amount", DoubleType(), nullable=True),
])

def test_output_schema(spark):
    result = run_transform(spark, sample_input(spark))
    assert result.schema == EXPECTED_SCHEMA, \
        f"Schema mismatch: got {result.schema}, expected {EXPECTED_SCHEMA}"
```

### Testing null handling
```python
def test_null_total_amount_defaults_to_zero(spark):
    input_df = spark.createDataFrame(
        [("ORD-001", None)],
        schema="order_id STRING, total_amount DOUBLE"
    )
    result = apply_defaults(input_df)
    row = result.filter("order_id = 'ORD-001'").collect()[0]
    assert row["total_amount"] == 0.0
```

---

## 5. Contract Testing

Contract tests validate that data at every pipeline boundary matches the declared data contract. Run after every load, before downstream consumers run.

### Data contract assertions (SQL)
```sql
-- Contract: fact_orders schema and SLA
-- Run after load, before downstream dbt models

-- 1. Row count within expected bounds
WITH counts AS (
    SELECT COUNT(*) AS actual_count
    FROM mart.fact_orders
    WHERE order_date = :execution_date
)
SELECT
    CASE
        WHEN actual_count BETWEEN 50000 AND 5000000 THEN 'PASS'
        ELSE 'FAIL: row count ' || actual_count || ' outside bounds [50K, 5M]'
    END AS contract_result
FROM counts;

-- 2. No NULL on required fields
SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS'
         ELSE 'FAIL: ' || COUNT(*) || ' NULL order_id values'
    END AS contract_result
FROM mart.fact_orders
WHERE order_date = :execution_date
  AND order_id IS NULL;

-- 3. Referential integrity: all customer_ids exist in dim_customers
SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS'
         ELSE 'FAIL: ' || COUNT(*) || ' orphan customer_ids'
    END AS contract_result
FROM mart.fact_orders f
LEFT JOIN mart.dim_customers d ON f.customer_id = d.customer_id
WHERE f.order_date = :execution_date
  AND d.customer_id IS NULL;

-- 4. Freshness: data loaded within SLA
SELECT
    CASE
        WHEN MAX(_loaded_at) > CURRENT_TIMESTAMP - INTERVAL '2 hours'
        THEN 'PASS'
        ELSE 'FAIL: data not loaded within 2-hour SLA'
    END AS contract_result
FROM mart.fact_orders
WHERE order_date = :execution_date;
```

### dbt contract enforcement (dbt 1.5+)
```yaml
models:
  - name: fact_orders
    config:
      contract:
        enforced: true   # fails if model output doesn't match declared schema
    columns:
      - name: order_id
        data_type: varchar
        constraints:
          - type: not_null
          - type: unique
      - name: total_amount
        data_type: numeric
        constraints:
          - type: not_null
```

---

## 6. Integration Testing

Integration tests run against a real database (test schema or test environment) and validate end-to-end data flow across multiple components.

### What integration tests must cover
1. **Full pipeline run** on realistic sample data (1K–100K rows)
2. **Idempotency**: run the pipeline twice, verify row count and values unchanged
3. **Schema enforcement**: verify output schema matches contract
4. **Error handling**: inject a bad row, verify it routes to DLQ/quarantine, verify good rows load
5. **Backfill**: run for a past partition; verify idempotent overwrite

### Integration test setup
```python
# conftest.py (integration tests)
import pytest
import psycopg2

@pytest.fixture(scope="session")
def test_db():
    conn = psycopg2.connect(os.environ["TEST_DB_CONN"])
    yield conn
    conn.close()

@pytest.fixture(autouse=True)
def clean_test_schema(test_db):
    """Reset test schema before each test."""
    with test_db.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS test_mart CASCADE")
        cur.execute("CREATE SCHEMA test_mart")
    test_db.commit()
    yield
    # teardown: schema dropped at next test start
```

### Idempotency integration test
```python
def test_pipeline_is_idempotent(test_db):
    run_pipeline(date="2024-01-15", target_schema="test_mart")
    count_first = query_count(test_db, "test_mart.fact_orders", "2024-01-15")

    run_pipeline(date="2024-01-15", target_schema="test_mart")  # re-run
    count_second = query_count(test_db, "test_mart.fact_orders", "2024-01-15")

    assert count_first == count_second, \
        f"Not idempotent: first={count_first}, second={count_second}"
```

---

## 7. E2E Pipeline Validation

E2E tests validate the full pipeline from source to final mart layer.

### E2E test checklist
- [ ] Source data seeded (test fixtures or masked prod sample)
- [ ] Pipeline triggered (Airflow DAG / Prefect flow run)
- [ ] All tasks completed successfully
- [ ] Row counts at each layer match expected (raw → staging → mart)
- [ ] DQ checks passed
- [ ] Data contract assertions passed
- [ ] Downstream consumers (BI query, API endpoint) return expected results
- [ ] Re-run produces identical output (idempotency check)

### Smoke test (runs per commit on a small dataset)
```bash
#!/bin/bash
# tests/run_smoke.sh
set -euo pipefail

DATE="2024-01-15"
echo "Running smoke test for date=$DATE"

# Seed test data
psql "$TEST_DB_CONN" -f tests/fixtures/seed_orders_2024-01-15.sql

# Trigger pipeline
airflow dags trigger orders_daily_load --exec-date "$DATE" --run-id "smoke_test_$(date +%s)"

# Wait for completion (poll)
airflow dags state orders_daily_load "$DATE" | grep -q "success" || exit 1

# Validate output
ROW_COUNT=$(psql "$TEST_DB_CONN" -t -c \
    "SELECT COUNT(*) FROM mart.fact_orders WHERE order_date = '$DATE'")
[ "$ROW_COUNT" -ge 100 ] || (echo "FAIL: expected ≥100 rows, got $ROW_COUNT" && exit 1)

echo "Smoke test PASSED"
```

---

## 8. Testing in CI

```yaml
# .github/workflows/test.yml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/unit/ -v --tb=short --cov=src --cov-report=term-missing

  dbt-tests:
    runs-on: ubuntu-latest
    steps:
      - run: dbt test --select staging intermediate   # fast; unit + schema tests
    env:
      DBT_TARGET: ci

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
    steps:
      - run: pytest tests/integration/ -v --tb=short
    env:
      TEST_DB_CONN: postgresql://test:test@localhost/test_db

  e2e-tests:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'    # E2E only on main branch
    steps:
      - run: bash tests/run_smoke.sh
```

---

## 9. Anti-Patterns

| Anti-Pattern | Impact | Fix |
|-------------|--------|-----|
| No tests at all | Production failures discovered by users | Start with dbt schema tests; add unit tests for transforms |
| Testing only the happy path | Edge cases (nulls, empty partitions, schema changes) break in prod | Add null-input, empty-input, and boundary-value test cases |
| Mocking the database in integration tests | Mock/prod divergence; migration failures hidden | Use a real test database (Docker Postgres or test warehouse schema) |
| Test data hardcoded in test files without cleanup | Tests interfere with each other; flaky results | Use fixtures with teardown; isolate test schemas |
| Running all tests in CI every commit | Slow CI; developers skip tests | Tiered CI: fast unit tests always; integration/E2E on merge |
| `assert df.count() == expected` without partition filter | Counts entire table; wrong on partitioned tables | Filter to the specific partition being tested |
| Skipping idempotency tests | Silent duplicate data in production | Idempotency test is mandatory for every write |
| No contract test between pipeline stages | Schema changes break downstream silently | Add contract assertion SQL after every layer load |
