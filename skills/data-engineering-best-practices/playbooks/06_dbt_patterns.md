---
title: "dbt Patterns"
description: "Model structure, materializations, testing, dbt+Airflow integration, DataForm comparison"
tags: [dbt, dataform, transformation, materialization, testing, bigquery]
related_templates:
  - ../templates/dbt_model_review.md
  - ../templates/data_contract.yaml
---

# dbt Patterns Playbook

> **Guiding principles:** Separation of concerns. Schema is a contract. Lineage is not optional.
> dbt is the transformation layer. Airflow is the orchestration layer. Never blur this boundary.

---

## 1. When to Use dbt vs DataForm vs Scheduled Queries

Choose your transformation tool before writing a single line of SQL.

| Criteria | dbt Core + Composer | dbt Cloud | DataForm (native BQ) | BQ Scheduled Queries |
|---|---|---|---|---|
| **Version control** | Git (full control) | Git (managed) | Git (in GCP) | None (anti-pattern) |
| **Testing framework** | Built-in + custom | Built-in + custom | Assertions (similar) | Manual only |
| **Lineage** | dbt docs + manifest | dbt docs + manifest | Dataplex integration | None |
| **CI/CD** | Cloud Build / GitHub Actions | dbt Cloud CI | Cloud Build | None |
| **Orchestration** | Airflow triggers dbt CLI | dbt Cloud scheduler | Dataform schedules | BQ scheduler |
| **Best for** | Teams already on Airflow | Teams wanting managed infra | Teams fully on GCP native | Ad-hoc or simple transforms only |

**Rule of thumb:** If your team has Airflow, use dbt Core. If you are greenfield on GCP and want minimal ops overhead, evaluate DataForm. Never use BQ Scheduled Queries as your primary transformation layer — they have no testing, no lineage, and no versioning.

---

## 2. dbt Project Structure

```
dbt_project/
├── dbt_project.yml               # Project config: name, models, vars
├── profiles.yml                  # Connection config (never commit credentials)
├── packages.yml                  # dbt packages (dbt-utils, dbt-expectations)
├── models/
│   ├── staging/                  # 1:1 with source. Light casting, renaming only.
│   │   ├── _sources.yml          # Source definitions + freshness checks
│   │   ├── _staging.yml          # Column descriptions + tests for staging models
│   │   ├── stg_orders.sql
│   │   └── stg_customers.sql
│   ├── intermediate/             # Multi-source joins, business logic
│   │   ├── _intermediate.yml
│   │   └── int_orders_with_customers.sql
│   ├── marts/                    # Consumer-facing, aggregated, BI-ready
│   │   ├── core/
│   │   │   ├── _core.yml
│   │   │   ├── fact_orders.sql
│   │   │   └── dim_customers.sql
│   │   └── finance/
│   │       └── rpt_monthly_revenue.sql
│   └── utils/                    # Shared macros and helpers
├── macros/
│   ├── generate_schema_name.sql  # Environment-aware schema routing
│   └── assert_row_count.sql      # Custom test macros
├── tests/
│   └── assert_no_future_dates.sql # Singular tests
├── snapshots/                    # SCD Type 2 logic
│   └── customers_snapshot.sql
└── analyses/                     # Ad-hoc SQL (not materialized)
```

### Layer Responsibilities

| Layer | Folder | Materialization | Rule |
|---|---|---|---|
| Staging | `models/staging/` | `view` (default) | Cast types, rename to standard names, add metadata columns. No joins. No business logic. |
| Intermediate | `models/intermediate/` | `ephemeral` or `view` | Join staging models, apply business rules. Not exposed to BI tools. |
| Mart | `models/marts/` | `table` or `incremental` | Pre-aggregated, consumer-specific. These are the SLA-bound tables. |

---

## 3. Materialization Strategy

Choosing the wrong materialization is the most common dbt mistake on BigQuery.

### Decision Tree

```
Is the model a mart or fact table consuming large volumes?
├── YES → Is the table append-friendly with a clear unique key?
│         ├── YES → incremental (merge strategy)
│         └── NO  → table (full refresh, acceptable if <2h runtime)
└── NO  → Is it a staging or intermediate model?
          ├── YES, staging → view (recomputed on query, no storage cost)
          └── YES, intermediate → ephemeral (inlined into downstream SQL, no BQ table)
```

### Materialization Reference

| Materialization | Storage | Query time | Best For | Avoid When |
|---|---|---|---|---|
| `view` | None | Recomputed each query | Staging, rarely queried | Queried frequently or by many downstream models |
| `table` | Full | Fast | Small-medium marts, full-refresh dimensions | Very large tables (slow rebuild) |
| `incremental` | Full | Fast | Large fact tables, event tables | Complex dedup logic that is hard to get right |
| `ephemeral` | None | Inlined into SQL | CTEs you want to reuse across models | When you need the output as a standalone table |

### Incremental Models: BigQuery-Specific Config

```sql
{{
  config(
    materialized = 'incremental',
    incremental_strategy = 'merge',
    unique_key = 'order_id',
    partition_by = {
      'field': 'order_date',
      'data_type': 'date',
      'granularity': 'day'
    },
    cluster_by = ['customer_id', 'order_status'],
    on_schema_change = 'append_new_columns'
  )
}}

SELECT
  order_id,
  customer_id,
  order_date,
  order_status,
  total_amount,
  updated_at
FROM {{ ref('stg_orders') }}

{% if is_incremental() %}
  -- Only process rows newer than the max already in the table
  WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

**Critical details:**
- Always include the partition column in the incremental filter. Without it, dbt scans the entire target table on every run.
- `on_schema_change = 'append_new_columns'` prevents silent failures when source adds columns.
- `unique_key` must be the business key, not a surrogate. Composite keys are supported: `unique_key = ['order_id', 'order_date']`.

### Snapshots (SCD Type 2)

```sql
-- snapshots/customers_snapshot.sql
{% snapshot customers_snapshot %}

{{
  config(
    target_schema = 'snapshots',
    strategy = 'timestamp',
    unique_key = 'customer_id',
    updated_at = 'updated_at',
  )
}}

SELECT * FROM {{ source('raw', 'customers') }}

{% endsnapshot %}
```

Use snapshots when you need full history of dimension changes. The snapshot table will have `dbt_valid_from`, `dbt_valid_to`, and `dbt_scd_id` columns added automatically.

---

## 4. Testing Strategy

> **Non-negotiable (Principle 3):** Fail loud. Silent data loss is worse than a failed run. dbt tests are your first line of defense.

### Test Layers

Every model must have tests at the column level. No exceptions for mart models.

```yaml
# models/marts/core/_core.yml
version: 2

models:
  - name: fact_orders
    description: "One row per order. Partitioned by order_date."
    config:
      contract:
        enforced: true   # enforce column types defined in this file
    columns:
      - name: order_id
        description: "Unique order identifier from the source system"
        data_tests:
          - unique
          - not_null
      - name: customer_id
        description: "FK to dim_customers"
        data_tests:
          - not_null
          - relationships:
              to: ref('dim_customers')
              field: customer_id
      - name: order_date
        data_tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: "order_date <= current_date()"
      - name: total_amount
        data_tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: "total_amount >= 0"
      - name: order_status
        data_tests:
          - accepted_values:
              values: ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
```

### Source Freshness

Define freshness checks on every source so stale data is caught before transforms run:

```yaml
# models/staging/_sources.yml
version: 2

sources:
  - name: raw_orders
    database: my-project
    schema: raw_orders
    freshness:
      warn_after: {count: 6, period: hour}
      error_after: {count: 12, period: hour}
    loaded_at_field: _loaded_at
    tables:
      - name: orders
        description: "Raw orders from the source system"
```

Run freshness checks in CI and before mart builds:

```bash
dbt source freshness
```

### Singular Tests (Custom SQL)

For business-logic assertions that cannot be expressed as schema tests:

```sql
-- tests/assert_no_orphan_order_items.sql
-- Fails if any order_item references an order_id not in fact_orders

SELECT oi.order_item_id
FROM {{ ref('fact_order_items') }} oi
LEFT JOIN {{ ref('fact_orders') }} o ON oi.order_id = o.order_id
WHERE o.order_id IS NULL
```

If this query returns any rows, the test fails.

### Test Severity

```yaml
data_tests:
  - unique:
      severity: error      # blocks deployment
  - dbt_utils.recency:
      severity: warn        # alerts but does not block
      datepart: hour
      field: updated_at
      interval: 3
```

Use `error` for structural invariants (unique, not_null on keys). Use `warn` for business-logic checks that may legitimately vary.

---

## 5. dbt + Airflow Integration

### Pattern: Airflow triggers dbt CLI in Cloud Run or Composer worker

```
Composer DAG
  │
  ├── [extract task] → GCS → BQ raw
  │
  ├── [dbt source freshness] ← verify upstream is not stale
  │
  ├── [dbt run --select staging] ← build staging models
  │
  ├── [dbt test --select staging] ← test staging before proceeding
  │
  ├── [dbt run --select marts] ← build mart models
  │
  └── [dbt test --select marts] ← test marts, fail loud if issues
```

### Airflow DAG Example

```python
from airflow import DAG
from airflow.providers.google.cloud.operators.kubernetes_engine import GKEStartPodOperator
from airflow.operators.bash import BashOperator
from datetime import timedelta

DBT_PROJECT_DIR = "/opt/airflow/dbt/my_project"
DBT_PROFILES_DIR = "/opt/airflow/dbt"

with DAG(
    dag_id="dbt_daily_transform",
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
        "execution_timeout": timedelta(hours=3),
    },
    schedule_interval="0 7 * * *",
    catchup=False,
    tags=["dbt", "transformation", "tier-1"],
) as dag:

    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=f"dbt source freshness --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR}",
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=f"dbt run --select staging --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR} --target prod",
    )

    dbt_test_staging = BashOperator(
        task_id="dbt_test_staging",
        bash_command=f"dbt test --select staging --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR} --target prod",
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=f"dbt run --select marts --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR} --target prod",
    )

    dbt_test_marts = BashOperator(
        task_id="dbt_test_marts",
        bash_command=f"dbt test --select marts --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR} --target prod",
    )

    dbt_source_freshness >> dbt_run_staging >> dbt_test_staging >> dbt_run_marts >> dbt_test_marts
```

**Key rules:**
- Always run `dbt test` immediately after `dbt run` for the same selector. A successful run that produces bad data is worse than a failed run.
- Use `--target prod` explicitly. Never rely on default profile targets in CI or Composer.
- Separate staging and mart runs so a mart failure does not prevent staging from completing (other DAGs may depend on staging).

### dbt + Airflow: Dataset-Aware Scheduling (Airflow 2.4+)

For loose coupling between extraction DAGs and transformation DAGs:

```python
from airflow.datasets import Dataset

# In extraction DAG — marks dataset as updated
raw_orders_dataset = Dataset("bigquery://my-project/raw_orders/orders")

extract_task = BigQueryInsertJobOperator(
    task_id="load_raw_orders",
    outlets=[raw_orders_dataset],  # signals: raw orders are fresh
    ...
)

# In dbt DAG — triggers when dataset is updated
with DAG(
    dag_id="dbt_daily_transform",
    schedule=[raw_orders_dataset],  # trigger when upstream updates
    ...
):
    ...
```

This eliminates brittle `ExternalTaskSensor` chains for extraction → transformation dependencies.

---

## 6. Environment Configuration

### profiles.yml: Environment-Aware Targets

```yaml
# profiles.yml
my_project:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: my-project-dev
      dataset: "{{ env_var('DBT_SCHEMA', 'dbt_' ~ env_var('DBT_USER', 'dev')) }}"
      threads: 4
      timeout_seconds: 300
      location: US

    staging:
      type: bigquery
      method: service-account
      project: my-project-staging
      dataset: "{{ var('target_dataset') }}"
      keyfile: "{{ env_var('GOOGLE_APPLICATION_CREDENTIALS') }}"
      threads: 8
      location: US

    prod:
      type: bigquery
      method: service-account
      project: my-project-prod
      dataset: "{{ var('target_dataset') }}"
      keyfile: "{{ env_var('GOOGLE_APPLICATION_CREDENTIALS') }}"
      threads: 16
      location: US
```

### generate_schema_name macro (Principle 10: Environments must be code-identical)

Override dbt's default schema naming to route models to the correct BQ dataset per environment:

```sql
-- macros/generate_schema_name.sql
{% macro generate_schema_name(custom_schema_name, node) -%}
  {%- set default_schema = target.schema -%}

  {%- if target.name == 'prod' -%}
    {%- if custom_schema_name is none -%}
      {{ default_schema }}
    {%- else -%}
      {{ custom_schema_name | trim }}
    {%- endif -%}
  {%- else -%}
    {%- if custom_schema_name is none -%}
      {{ default_schema }}
    {%- else -%}
      {{ default_schema }}_{{ custom_schema_name | trim }}
    {%- endif -%}
  {%- endif -%}
{%- endmacro %}
```

This ensures `models/marts/core/fact_orders.sql` lands in:
- `dbt_jdoe` (developer personal schema in dev)
- `staging_core` (in staging)
- `core` (in prod, matching the data contract destination)

---

## 7. DataForm: GCP-Native Alternative

DataForm is Google's managed SQL transformation tool, natively integrated into BigQuery. Use it when your team does not operate Airflow and wants zero infrastructure overhead.

### Key Differences vs dbt

| Feature | dbt Core | DataForm |
|---|---|---|
| Language | Jinja2 + SQL | SQLX (JS templating + SQL) |
| Runtime | CLI / Airflow | Managed by GCP |
| Testing | `data_tests:` in YAML | `assertions {}` blocks in SQLX |
| Lineage | dbt docs graph | Native Dataplex integration |
| CI/CD | Your own pipeline | Built into GCP console + Cloud Build |
| Scheduler | External (Airflow) | Built-in Dataform schedules |
| Cost | OSS (infra cost only) | Included in BQ (no separate cost) |

### SQLX Model Example

```sqlx
-- definitions/orders/fact_orders.sqlx
config {
  type: "incremental",
  schema: "marts_core",
  description: "One row per order, partitioned by order_date",
  bigquery: {
    partitionBy: "order_date",
    clusterBy: ["customer_id", "order_status"],
    requirePartitionFilter: true
  },
  uniqueKey: ["order_id"]
}

SELECT
  order_id,
  customer_id,
  DATE(order_timestamp) AS order_date,
  order_status,
  total_amount,
  updated_at
FROM ${ref("stg_orders")}

${ when(incremental(), `WHERE updated_at > (SELECT MAX(updated_at) FROM ${self()})`) }

post_operations {
  ASSERT (SELECT COUNT(*) FROM ${self()} WHERE order_id IS NULL) = 0
    AS "order_id must not be null"
}
```

### When to Choose DataForm over dbt

- You want native Dataplex lineage without additional tooling.
- Your team has no Airflow experience and does not want to operate it.
- You are prototyping quickly and want scheduling built in.
- You are fully committed to GCP and have no multi-cloud requirements.

---

## 8. Lineage Documentation (Principle 9)

Every dbt model must document its lineage via `ref()` and `source()`. Never hardcode table paths.

```sql
-- CORRECT: lineage is explicit and tracked by dbt
SELECT o.*, c.customer_name
FROM {{ ref('stg_orders') }} o
JOIN {{ ref('stg_customers') }} c ON o.customer_id = c.customer_id

-- WRONG: lineage is invisible to dbt
SELECT o.*, c.customer_name
FROM `my-project.raw_orders.orders` o
JOIN `my-project.raw_customers.customers` c ON o.customer_id = c.customer_id
```

Run `dbt docs generate && dbt docs serve` after every significant model addition to verify the DAG graph is connected and there are no orphaned models.

---

## 9. Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| `SELECT *` in a dbt model | Propagates unwanted columns, breaks contract | Explicitly list columns |
| No `unique` + `not_null` tests on primary keys | Duplicates or NULLs silently enter marts | Add tests to every model's primary key |
| Hardcoded project/dataset paths | Breaks across environments | Use `ref()` and `source()` always |
| Business logic in staging models | Violates separation; staging should be 1:1 with source | Move joins and logic to intermediate layer |
| Incremental model without partition filter in `is_incremental()` block | Full table scan on every run | Always filter on the partition column |
| Running `dbt run` without `dbt test` in CI | Bad data reaches production | CI pipeline must run both, in order |
| `dbt run --full-refresh` in production without safeguard | Truncates production tables | Gate full-refresh behind an approval step |
| Large ephemeral models used in many downstream models | Inline SQL explosion, query cost multiplies | Promote to `view` or `table` if referenced >2 times |
| No freshness check on sources | Transforms succeed on stale data | Add `loaded_at_field` and freshness config to all sources |

---

## Quick Reference Checklist: dbt Model Review

Before merging any dbt model change:

- [ ] Model uses `ref()` / `source()` — no hardcoded table paths
- [ ] Column-level tests defined (`unique`, `not_null` on primary key at minimum)
- [ ] Source freshness is configured for any new source
- [ ] Materialization is appropriate for the layer (view for staging, table/incremental for marts)
- [ ] Incremental model includes partition filter in `is_incremental()` block
- [ ] `on_schema_change` is set (prefer `append_new_columns` over `ignore`)
- [ ] `dbt test` passes in CI before merge
- [ ] Model is documented with a description in the YAML schema file
- [ ] No business logic in staging models
- [ ] Data contract updated if mart schema changed

See the full template at [../templates/dbt_model_review.md](../templates/dbt_model_review.md).
