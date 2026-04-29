---
title: "dbt Patterns"
description: "Model structure, materializations, testing, dbt+Airflow integration"
tags: [dbt, transformation, materialization, testing, sql-warehouse]
related_templates:
  - ../templates/dbt_model_review.md
  - ../templates/data_contract.yaml
---

# dbt Patterns Playbook

> **Guiding principles:** Separation of concerns. Schema is a contract. Lineage is not optional.
> dbt is the transformation layer. Airflow is the orchestration layer. Never blur this boundary.

---

## 1. When to Use dbt vs Scheduled Queries

Choose your transformation tool before writing a single line of SQL.

| Criteria | dbt Core + Airflow | dbt Cloud | Warehouse Scheduled Queries |
|---|---|---|---|
| **Version control** | Git (full control) | Git (managed) | None (anti-pattern) |
| **Testing framework** | Built-in + custom | Built-in + custom | Manual only |
| **Lineage** | dbt docs + manifest | dbt docs + manifest | None |
| **CI/CD** | Your own pipeline | dbt Cloud CI | None |
| **Orchestration** | Airflow triggers dbt CLI | dbt Cloud scheduler | Warehouse scheduler |
| **Best for** | Teams already on Airflow | Teams wanting managed infra | Ad-hoc or simple transforms only |

**Rule of thumb:** If your team has Airflow, use dbt Core. Never use warehouse scheduled queries as your primary transformation layer — they have no testing, no lineage, and no versioning.

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

Choosing the wrong materialization is the most common dbt mistake on any warehouse.

### Decision Tree

```
Is the model a mart or fact table consuming large volumes?
├── YES → Is the table append-friendly with a clear unique key?
│         ├── YES → incremental (merge strategy)
│         └── NO  → table (full refresh, acceptable if <2h runtime)
└── NO  → Is it a staging or intermediate model?
          ├── YES, staging → view (recomputed on query, no storage cost)
          └── YES, intermediate → ephemeral (inlined into downstream SQL, no table)
```

### Materialization Reference

| Materialization | Storage | Query time | Best For | Avoid When |
|---|---|---|---|---|
| `view` | None | Recomputed each query | Staging, rarely queried | Queried frequently or by many downstream models |
| `table` | Full | Fast | Small-medium marts, full-refresh dimensions | Very large tables (slow rebuild) |
| `incremental` | Full | Fast | Large fact tables, event tables | Complex dedup logic that is hard to get right |
| `ephemeral` | None | Inlined into SQL | CTEs you want to reuse across models | When you need the output as a standalone table |

### Incremental Models

```sql
{{
  config(
    materialized = 'incremental',
    incremental_strategy = 'merge',
    unique_key = 'order_id',
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
- Always include a time-based filter in the `is_incremental()` block. Without it, dbt scans the entire target table on every run.
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

> **Non-negotiable (Principle W003 — Fail loud):** Silent data loss is worse than a failed run. dbt tests are your first line of defense.

### Test Layers

Every model must have tests at the column level. No exceptions for mart models.

```yaml
# models/marts/core/_core.yml
version: 2

models:
  - name: fact_orders
    description: "One row per order."
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

### Pattern: Airflow triggers dbt CLI

```
Airflow DAG
  │
  ├── [extract task] → object storage → warehouse raw
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
from airflow.operators.bash import BashOperator
from datetime import timedelta

DBT_PROJECT_DIR  = "/opt/airflow/dbt/my_project"
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
- Use `--target prod` explicitly. Never rely on default profile targets in CI or Airflow.
- Separate staging and mart runs so a mart failure does not prevent staging from completing (other DAGs may depend on staging).

### dbt + Airflow: Dataset-Aware Scheduling (Airflow 2.4+)

For loose coupling between extraction DAGs and transformation DAGs:

```python
from airflow.datasets import Dataset

# In extraction DAG — marks dataset as updated
raw_orders_dataset = Dataset("warehouse://my_schema/raw_orders/orders")

extract_task = SQLExecuteQueryOperator(
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

The shape is identical across warehouses; only the `type:` block and credential fields change. Authenticate via short-lived credentials (OIDC / IAM / OAuth) where supported and **never** commit a populated `profiles.yml` — pull every secret from env vars or a secret manager.

#### Vendor-neutral skeleton (recommended)

```yaml
# profiles.yml
my_project:
  target: "{{ env_var('DBT_TARGET', 'dev') }}"
  outputs:
    dev:
      type: <warehouse>            # snowflake | bigquery | databricks | redshift | postgres | duckdb | trino
      threads: 4
      schema: "{{ env_var('DBT_SCHEMA', 'dbt_' ~ env_var('DBT_USER', 'dev')) }}"
      # warehouse-specific fields (account / project / host / catalog) injected per the alternatives below

    staging:
      type: <warehouse>
      threads: 8
      schema: "{{ var('target_dataset') }}"

    prod:
      type: <warehouse>
      threads: 16
      schema: "{{ var('target_dataset') }}"
```

#### Warehouse-specific fields

Drop one of the blocks below into each environment under `outputs:`. Field names match the official `dbt-<adapter>` plugins.

```yaml
# Snowflake
type: snowflake
account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
user: "{{ env_var('SNOWFLAKE_USER') }}"
authenticator: externalbrowser   # or 'oauth' for SSO
database: "{{ env_var('SNOWFLAKE_DATABASE') }}"
warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE') }}"
role: "{{ env_var('SNOWFLAKE_ROLE') }}"

# BigQuery
type: bigquery
method: oauth                    # or 'service-account-json' / 'service-account' for CI
project: "{{ env_var('GCP_PROJECT') }}"
dataset: "{{ var('target_dataset') }}"
location: "{{ env_var('BQ_LOCATION', 'US') }}"
priority: interactive

# Databricks (Unity Catalog)
type: databricks
host: "{{ env_var('DATABRICKS_HOST') }}"
http_path: "{{ env_var('DATABRICKS_HTTP_PATH') }}"
catalog: "{{ env_var('DATABRICKS_CATALOG') }}"
token: "{{ env_var('DATABRICKS_TOKEN') }}"

# Redshift
type: redshift
host: "{{ env_var('REDSHIFT_HOST') }}"
port: 5439
dbname: "{{ env_var('REDSHIFT_DATABASE') }}"
user: "{{ env_var('REDSHIFT_USER') }}"
ra3_node: true

# Postgres / Trino / DuckDB
type: postgres
host: "{{ env_var('PG_HOST') }}"
port: 5432
dbname: "{{ env_var('PG_DATABASE') }}"
user: "{{ env_var('PG_USER') }}"
password: "{{ env_var('PG_PASSWORD') }}"
```

**Cross-warehouse rules:**
- Use `env_var(...)` with a default only for non-secret fields (region, schema, role). Never default a secret.
- Increase `threads` proportional to warehouse compute size (4 dev / 8 staging / 16 prod is a fine starting point on a small-medium warehouse; raise to 32+ on large warehouses).
- Always declare an explicit target — never rely on the local default profile in CI/CD.

### generate_schema_name macro (Principle W010 — Environments must be code-identical)

Override dbt's default schema naming to route models to the correct schema per environment:

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

## 7. Lineage Documentation (Principle W009)

Every dbt model must document its lineage via `ref()` and `source()`. Never hardcode table paths.

```sql
-- CORRECT: lineage is explicit and tracked by dbt
SELECT o.*, c.customer_name
FROM {{ ref('stg_orders') }} o
JOIN {{ ref('stg_customers') }} c ON o.customer_id = c.customer_id

-- WRONG: lineage is invisible to dbt
SELECT o.*, c.customer_name
FROM raw_orders.orders o
JOIN raw_customers.customers c ON o.customer_id = c.customer_id
```

Run `dbt docs generate && dbt docs serve` after every significant model addition to verify the DAG graph is connected and there are no orphaned models.

---

## 8. Model Contracts (dbt 1.5+)

A contract pins a model's column list and types. The warehouse refuses to materialize the model if the SELECT drifts. **Required for any model exposed across teams** (mart layer, semantic-layer inputs, downstream API consumers).

```yaml
# models/marts/core/_core.yml
version: 2

models:
  - name: fact_orders
    description: "One row per order. Contract is enforced — column names and types are stable for downstream consumers."
    config:
      contract:
        enforced: true
    columns:
      - name: order_id
        data_type: varchar(64)
        constraints:
          - type: not_null
          - type: primary_key
      - name: customer_id
        data_type: varchar(64)
        constraints:
          - type: not_null
          - type: foreign_key
            expression: "{{ ref('dim_customers') }} (customer_id)"
      - name: order_date
        data_type: date
        constraints:
          - type: not_null
      - name: total_amount
        data_type: numeric(18, 2)
```

**Notes:**
- Constraint enforcement varies by warehouse. Most enforce `not_null` and `primary_key`; cross-table `foreign_key` constraints are typically advisory at compile-time only.
- A contract change is a breaking change. Bump the model version (§10) instead of editing in place.

---

## 9. Groups & Access (dbt 1.5+ / Mesh)

**Groups** scope models to a team (owner, allowed downstream consumers). **Access** declares the model's blast radius. Together they enable [dbt Mesh](https://docs.getdbt.com/docs/collaborate/govern/about-model-governance) — one shared graph of dbt projects with explicit cross-project boundaries.

### Declare groups

```yaml
# dbt_project.yml
groups:
  - name: core
    owner:
      name: Data Platform
      email: data-platform@example.com
  - name: finance
    owner:
      name: Finance Engineering
      email: finance-eng@example.com
```

### Apply group + access on each model

```yaml
# models/marts/core/_core.yml
models:
  - name: fact_orders
    group: core
    access: public          # private | protected | public
    description: "Order fact. Public — finance and marketing both consume it."

  - name: int_orders_pricing_logic
    group: core
    access: private         # only models in 'core' may ref()
    description: "Internal pricing computation. Not stable; do not depend on it."

  - name: fct_finance_revenue
    group: finance
    access: protected       # ref()-able by other groups in this project, but not from another dbt project
```

| Access level | Same group | Other group, same project | Other dbt project (Mesh) |
|--------------|:----------:|:-------------------------:|:------------------------:|
| `private`    | ✅         | ❌                        | ❌                       |
| `protected`  | ✅         | ✅                        | ❌                       |
| `public`     | ✅         | ✅                        | ✅                       |

**Rule:** Default new mart models to `protected`. Only flip to `public` once the contract (§8) and tests are in place — `public` advertises stability to consumers outside this dbt project.

### Cross-project consumption (dbt Mesh)

In a downstream project, consume an upstream public model via `{{ ref('upstream_project', 'fact_orders') }}`. Configure the upstream project under `dependencies.yml`:

```yaml
# dependencies.yml (downstream project)
projects:
  - name: platform_core
```

---

## 10. Model Versions (dbt 1.5+)

Use versions when a contract-breaking change is unavoidable. Both versions exist concurrently; consumers migrate on their own clock.

```yaml
# models/marts/core/_core.yml
models:
  - name: fact_orders
    latest_version: 2
    config:
      contract:
        enforced: true
    columns:
      - name: order_id
      - name: customer_id
      - name: order_date
      - name: order_status
      - name: total_amount

    versions:
      - v: 1
        deprecation_date: "2026-09-30"     # callers must migrate by this date
        defined_in: fact_orders_v1         # SQL file name (without .sql)
        columns:
          - include: all
            exclude: [order_status]        # v1 lacks order_status

      - v: 2
        columns:
          - include: all
```

```sql
-- models/marts/core/fact_orders_v1.sql
SELECT
  order_id,
  customer_id,
  order_date,
  total_amount
FROM {{ ref('int_orders_with_customers') }}

-- models/marts/core/fact_orders_v2.sql
SELECT
  order_id,
  customer_id,
  order_date,
  order_status,
  total_amount
FROM {{ ref('int_orders_with_customers') }}
```

Consumers reference a specific version: `{{ ref('fact_orders', v=2) }}`. After `deprecation_date`, the v1 model is removed in a follow-up PR.

---

## 11. Semantic Layer & Metrics (dbt 1.6+)

Define metrics once in dbt; consume them via the dbt Semantic Layer (or compatible BI tools that speak MetricFlow). Eliminates the "every dashboard re-implements `gross_revenue`" anti-pattern.

```yaml
# models/marts/core/_semantic.yml
semantic_models:
  - name: orders
    model: ref('fact_orders')
    defaults:
      agg_time_dimension: order_date
    entities:
      - name: order_id
        type: primary
      - name: customer_id
        type: foreign
    dimensions:
      - name: order_date
        type: time
        type_params:
          time_granularity: day
      - name: order_status
        type: categorical
    measures:
      - name: order_count
        agg: count
        expr: order_id
      - name: gross_revenue
        agg: sum
        expr: total_amount

metrics:
  - name: gross_revenue
    label: "Gross Revenue"
    type: simple
    type_params:
      measure: gross_revenue

  - name: gross_revenue_30d
    label: "Gross Revenue (30d rolling)"
    type: cumulative
    type_params:
      measure: gross_revenue
      window: 30 days

  - name: revenue_per_active_customer
    label: "Revenue per Active Customer"
    type: ratio
    type_params:
      numerator: gross_revenue
      denominator: order_count
```

Query at runtime:

```bash
# Native MetricFlow CLI (dbt Cloud Semantic Layer or dbt-core 1.6+)
mf query --metrics gross_revenue --group-by metric_time__day,order_status --order metric_time__day
```

**Rules:**
- Define metrics in the same group/access as their underlying mart so governance is consistent.
- Every metric must reference a measure on a contracted (§8) model. Do not build metrics on `view`-materialized staging models.
- BI tools that don't speak MetricFlow can still query via JDBC/SQL through the dbt Cloud Semantic Layer endpoint.

---

## 12. Warehouse-Managed Incremental Tables

When the warehouse can keep a materialized result fresh on its own, you may not need a dbt `incremental` model at all. These options let the **warehouse** decide when to refresh and how to reconcile state, in exchange for some loss of orchestration control. Useful for low-latency marts where dbt's run cadence is the bottleneck.

| Capability | dbt `incremental` | Snowflake Dynamic Table | BigQuery Materialized View / managed Iceberg | Databricks Live Table (DLT) | Redshift Materialized View |
|---|---|---|---|---|---|
| Refresh trigger | Airflow / cron | Lag SLA (`TARGET_LAG`) | Auto / on query | Continuous or triggered | Auto / scheduled |
| State tracking | Watermark in `is_incremental()` | Warehouse | Warehouse | Warehouse | Warehouse |
| MERGE semantics | Author writes | Built-in | Limited (append + dedupe in def) | Built-in | Limited |
| Backfill / replay | `--full-refresh` | `ALTER ... REFRESH` | `BQ.REFRESH_MATERIALIZED_VIEW` | `FULL REFRESH` | `REFRESH MATERIALIZED VIEW` |
| Cost model | Compute per run | Continuous, billed against lag SLA | Storage + scan-on-refresh | Continuous (clusters always-on) | Storage + scan-on-refresh |
| Best for | Hourly/daily marts, complex MERGE | Sub-15-minute marts on Snowflake | Pre-aggregated dashboards on BigQuery | Streaming + batch unified | Reporting marts on Redshift |

### Defining via dbt configs

dbt 1.6+ ships adapter-specific materializations that wrap the native object so it stays in your dbt graph:

```sql
-- Snowflake Dynamic Table (dbt-snowflake 1.6+)
{{
  config(
    materialized = 'dynamic_table',
    target_lag = '5 minutes',
    snowflake_warehouse = 'transformation_wh',
    on_configuration_change = 'apply'
  )
}}

SELECT order_id, customer_id, order_date, total_amount
FROM {{ ref('stg_orders') }}
```

```sql
-- BigQuery Materialized View (dbt-bigquery 1.6+)
{{
  config(
    materialized = 'materialized_view',
    enable_refresh = true,
    refresh_interval_minutes = 30,
    cluster_by = ['order_date']
  )
}}

SELECT order_date, COUNT(*) AS order_count, SUM(total_amount) AS gross_revenue
FROM {{ ref('fact_orders') }}
GROUP BY order_date
```

```sql
-- Databricks Live Table (dbt-databricks 1.6+)
{{
  config(
    materialized = 'streaming_table',
    schedule = {'interval': '5 minutes'}
  )
}}

SELECT * FROM stream({{ ref('stg_orders') }})
```

**Rule of thumb:**
- If your refresh need is **cron-able with > 30 minute granularity**, stay with `incremental`. dbt's MERGE control + `--full-refresh` semantics are easier to reason about.
- If you need **< 15 minute freshness on a dashboard mart**, evaluate the warehouse-native option first; you remove a DAG and a watermark column.
- **Always** declare an SLO and a freshness check (Playbook 05 §1) — the warehouse's "best-effort" refresh is not free of skew.

---

## 13. Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| `SELECT *` in a dbt model | Propagates unwanted columns, breaks contract | Explicitly list columns |
| No `unique` + `not_null` tests on primary keys | Duplicates or NULLs silently enter marts | Add tests to every model's primary key |
| Hardcoded schema/database paths | Breaks across environments | Use `ref()` and `source()` always |
| Business logic in staging models | Violates separation; staging should be 1:1 with source | Move joins and logic to intermediate layer |
| Incremental model without time filter in `is_incremental()` block | Full table scan on every run | Always filter on the updated-at or partition column |
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
- [ ] Incremental model includes time filter in `is_incremental()` block
- [ ] `on_schema_change` is set (prefer `append_new_columns` over `ignore`)
- [ ] `dbt test` passes in CI before merge
- [ ] Model is documented with a description in the YAML schema file
- [ ] No business logic in staging models
- [ ] Data contract updated if mart schema changed

See the full template at [../templates/dbt_model_review.md](../templates/dbt_model_review.md).
