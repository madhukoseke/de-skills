---
title: "Data Modeling Patterns"
description: "Data modeling paradigms for analytics engineering: Kimball, Data Vault, OBT, Lakehouse/medallion, SCD types, naming conventions, and schema versioning"
tags: [data-modeling, kimball, data-vault, scd, lakehouse, medallion, obt, schema, naming-conventions]
---

# Playbook 09 — Data Modeling Patterns

Covers: Kimball dimensional modeling, Data Vault 2.0, One Big Table (OBT), Lakehouse/medallion architecture, SCD types 0–3, naming conventions, and schema versioning.

---

## 1. Choosing a Modeling Paradigm

| Paradigm | Best For | Avoid When |
|----------|---------|------------|
| **Kimball (Star Schema)** | BI-facing analytics, known query patterns, Redshift/Snowflake | Source data changes frequently; exploratory/unknown query patterns |
| **Data Vault 2.0** | Regulated industries, auditability, rapidly changing source systems | Small teams, simple use cases, low compliance requirements |
| **One Big Table (OBT)** | Embedded analytics, single-entity deep analysis, Snowflake/BigQuery | Multiple entities, complex joins across domains |
| **Lakehouse / Medallion** | Unified batch + stream, open formats (Delta/Iceberg), Spark-heavy | BI-only, no need for raw data preservation |

**Rule: most analytics teams should start with Kimball (star schema) in dbt. Graduate to Data Vault only when auditability or source-system volatility demands it.**

---

## 2. Kimball Dimensional Modeling

### Layer structure
```
raw.*         → exact copy of source data, no transforms (Bronze)
staging.*     → cleaned, typed, renamed, no business logic (Silver/stg_)
intermediate.*→ business logic, pre-aggregations, join prep (int_)
mart.*        → final dimensional model: dim_ and fact_ tables (Gold/mart_)
```

### Fact table design
```sql
CREATE TABLE mart.fact_orders (
    -- Surrogate keys (foreign keys to dimensions)
    order_sk        BIGINT NOT NULL,   -- generated surrogate key
    customer_sk     BIGINT NOT NULL REFERENCES mart.dim_customers(customer_sk),
    product_sk      BIGINT NOT NULL REFERENCES mart.dim_products(product_sk),
    date_sk         INTEGER NOT NULL REFERENCES mart.dim_date(date_sk),

    -- Natural/business key (for debugging and idempotency)
    order_id        VARCHAR(50) NOT NULL,

    -- Measures (additive)
    quantity        INTEGER NOT NULL,
    unit_price      NUMERIC(12, 4) NOT NULL,
    discount_amount NUMERIC(12, 4) NOT NULL DEFAULT 0,
    total_amount    NUMERIC(12, 4) NOT NULL,

    -- Degenerate dimensions (non-FK attributes stored on fact)
    order_channel   VARCHAR(50),
    payment_method  VARCHAR(50),

    -- Audit columns
    _loaded_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    _source_file    VARCHAR(500)
);
```

### Dimension table design
```sql
CREATE TABLE mart.dim_customers (
    -- Surrogate key (immutable, system-generated)
    customer_sk     BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    -- Natural/business key
    customer_id     VARCHAR(50) NOT NULL,

    -- Descriptive attributes
    name            VARCHAR(200),
    email           VARCHAR(200),
    country_code    CHAR(2),
    customer_tier   VARCHAR(20),

    -- SCD Type 2 fields (if tracking history)
    valid_from      TIMESTAMP NOT NULL,
    valid_to        TIMESTAMP,          -- NULL = current record
    is_current      BOOLEAN NOT NULL DEFAULT TRUE,

    -- Audit
    _loaded_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Date dimension (always pre-build)
```sql
-- Date dimension: required for all fact tables with time-based analysis
CREATE TABLE mart.dim_date (
    date_sk         INTEGER PRIMARY KEY,  -- YYYYMMDD format (e.g., 20240115)
    full_date       DATE NOT NULL,
    year            SMALLINT NOT NULL,
    quarter         SMALLINT NOT NULL,
    month           SMALLINT NOT NULL,
    month_name      VARCHAR(20) NOT NULL,
    week_of_year    SMALLINT NOT NULL,
    day_of_week     SMALLINT NOT NULL,  -- 1=Monday
    day_name        VARCHAR(20) NOT NULL,
    is_weekend      BOOLEAN NOT NULL,
    is_holiday      BOOLEAN NOT NULL DEFAULT FALSE,
    fiscal_year     SMALLINT,
    fiscal_quarter  SMALLINT
);
```

---

## 3. Data Vault 2.0

Data Vault separates raw history (Hubs, Links, Satellites) from business rules (Business Vault / Information Mart).

### Core entities

**Hub** — stores business keys
```sql
CREATE TABLE raw_vault.hub_customer (
    customer_hk     CHAR(32) PRIMARY KEY,   -- MD5 hash of business key
    customer_id     VARCHAR(50) NOT NULL,   -- business key
    load_date       TIMESTAMP NOT NULL,
    record_source   VARCHAR(200) NOT NULL   -- e.g., 'salesforce.contacts'
);
```

**Link** — stores relationships between hubs
```sql
CREATE TABLE raw_vault.link_order_customer (
    order_customer_hk   CHAR(32) PRIMARY KEY,   -- MD5 hash of all hub keys
    order_hk            CHAR(32) NOT NULL REFERENCES raw_vault.hub_order(order_hk),
    customer_hk         CHAR(32) NOT NULL REFERENCES raw_vault.hub_customer(customer_hk),
    load_date           TIMESTAMP NOT NULL,
    record_source       VARCHAR(200) NOT NULL
);
```

**Satellite** — stores descriptive attributes and history
```sql
CREATE TABLE raw_vault.sat_customer_details (
    customer_hk     CHAR(32) NOT NULL REFERENCES raw_vault.hub_customer(customer_hk),
    load_date       TIMESTAMP NOT NULL,  -- effective from
    load_end_date   TIMESTAMP,           -- NULL = current
    hash_diff       CHAR(32) NOT NULL,   -- MD5 of all attributes; detect changes
    name            VARCHAR(200),
    email           VARCHAR(200),
    record_source   VARCHAR(200) NOT NULL,
    PRIMARY KEY (customer_hk, load_date)
);
```

### Hash key generation (consistent across loads)
```sql
-- Generate MD5 hash key (uppercase, trimmed, null-safe)
MD5(UPPER(TRIM(COALESCE(customer_id, ''))))
```

### When to use Data Vault
- Regulatory requirements (audit trail of every source change)
- Multiple source systems feeding the same entity (customer from CRM + ERP + support)
- Source schemas change frequently and without notice
- Team > 5 data engineers with dedicated modeling capacity

---

## 4. One Big Table (OBT)

OBT denormalizes all attributes into a single wide table. Trades storage for query simplicity.

```sql
CREATE TABLE mart.obt_orders (
    -- Order attributes
    order_id            VARCHAR(50) PRIMARY KEY,
    order_date          DATE NOT NULL,
    order_status        VARCHAR(50),
    total_amount        NUMERIC(12, 4),

    -- Customer attributes (denormalized)
    customer_id         VARCHAR(50),
    customer_name       VARCHAR(200),
    customer_email      VARCHAR(200),
    customer_country    CHAR(2),
    customer_tier       VARCHAR(20),

    -- Product attributes (denormalized, first line item only or aggregated)
    primary_product_id  VARCHAR(50),
    primary_category    VARCHAR(100),

    -- Seller attributes
    seller_id           VARCHAR(50),
    seller_region       VARCHAR(100),

    _loaded_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**OBT is appropriate when:**
- Single primary entity (orders, sessions, events)
- Query patterns are mostly filters and aggregations on the same entity
- BI tool performance requires no runtime joins
- Table size < 1 TB (large OBTs become expensive to maintain)

**OBT is inappropriate when:**
- Multiple entities need independent updates (customer data changing ≠ re-loading all orders)
- Storage cost is constrained
- Different teams own different attribute groups

---

## 5. Lakehouse / Medallion Architecture

```
Bronze (raw)    → Exact copy of source data; append-only; never modified
Silver (clean)  → Cleaned, validated, deduplicated; schema enforced
Gold (mart)     → Aggregated, business-ready; serves BI and APIs
```

### Bronze layer conventions
- Schema: `raw.*` or `bronze.*`
- Storage: object storage (Parquet / Delta) — preserve original format where possible
- Transformations: none (or minimal: add `_ingested_at`, `_source_file` audit columns)
- Retention: 90 days minimum for replay; often 1–3 years for compliance
- Mode: append-only (never update or delete from Bronze)

### Silver layer conventions
- Schema: `staging.*` or `silver.*`
- Transformations: type casting, null handling, deduplication, standardization (phone/email format)
- DQ checks run here: fail the pipeline if checks fail, quarantine bad rows
- Partitioning: by ingestion date or event date

### Gold layer conventions
- Schema: `mart.*` or `gold.*`
- Transformations: business logic, aggregations, dimensional modeling
- Served to: BI tools, dashboards, ML features, APIs
- SLA: gold data must be available within the agreed SLA window

---

## 6. SCD Types

### SCD Type 0 — No change tracking
- Attribute never changes (e.g., birth date, original registration date)
- On update: ignore changes

### SCD Type 1 — Overwrite (no history)
```sql
-- Simple MERGE, no history preserved
MERGE INTO mart.dim_customers AS target
USING staging.stg_customers AS src ON target.customer_id = src.customer_id
WHEN MATCHED THEN UPDATE SET target.email = src.email, target.name = src.name
WHEN NOT MATCHED THEN INSERT (customer_id, email, name) VALUES (src.customer_id, src.email, src.name);
```
**Use:** frequently changing attributes where history has no analytical value.

### SCD Type 2 — Full history
```sql
-- See 07_sql_patterns.md §7 for full MERGE pattern
-- Key fields: valid_from, valid_to (NULL = current), is_current BOOLEAN
```
**Use:** attributes where historical values affect analytics (e.g., customer_tier, pricing_plan, country).

### SCD Type 3 — Previous value only
```sql
CREATE TABLE mart.dim_customers_scd3 (
    customer_sk         BIGINT PRIMARY KEY,
    customer_id         VARCHAR(50) NOT NULL,
    current_tier        VARCHAR(20),
    previous_tier       VARCHAR(20),    -- one prior value only
    tier_changed_at     TIMESTAMP,
    name                VARCHAR(200)
);

-- On change: shift current → previous, write new current
UPDATE mart.dim_customers_scd3
SET previous_tier = current_tier,
    current_tier  = :new_tier,
    tier_changed_at = CURRENT_TIMESTAMP
WHERE customer_id = :customer_id;
```
**Use:** "current vs previous" comparisons (one level of history); simple, low overhead.

### SCD Type 6 — Hybrid (Type 1 + 2 + 3)
- Stores full history (Type 2 rows) + current value denormalized on all rows (Type 1) + previous value (Type 3).
- Enables joining without filtering `is_current = TRUE`.
- High complexity — use only when justified.

---

## 7. Naming Conventions

### Table naming
```
<layer>_<domain>_<entity>       for staging/intermediate
<dim|fact|obt>_<entity>         for mart layer
<hub|link|sat>_<entity>         for Data Vault

Examples:
  stg_salesforce_contacts       (staging)
  int_order_items_enriched      (intermediate)
  dim_customers                 (Kimball dimension)
  fact_orders                   (Kimball fact)
  hub_customer                  (Data Vault hub)
  sat_customer_details          (Data Vault satellite)
```

### Column naming
```
<entity>_id          → natural/business key (e.g., order_id, customer_id)
<entity>_sk          → surrogate key (e.g., customer_sk)
<entity>_hk          → hash key (Data Vault)
is_<attribute>       → boolean (e.g., is_active, is_current)
has_<attribute>      → boolean (e.g., has_discount)
<metric>_count       → integer counts (e.g., item_count, retry_count)
<metric>_amount      → monetary values (e.g., total_amount, discount_amount)
<event>_at           → timestamp of event (e.g., created_at, updated_at, shipped_at)
<event>_date         → date of event (e.g., order_date, shipped_date)
_loaded_at           → audit: when row was loaded into warehouse
_source              → audit: source system/file identifier
valid_from / valid_to → SCD Type 2 effective dates
```

### All names: `snake_case`. No abbreviations unless universally understood (`id`, `ts`, `amt` are ambiguous — spell them out).

---

## 8. Schema Versioning

Every schema change must be intentional, backward-compatible where possible, and communicated to downstream consumers.

### Change classification
| Change Type | Compatible? | Required Action |
|------------|-------------|-----------------|
| Add column with default | Yes | Notify consumers; update data contract |
| Add NOT NULL column | No | Provide default or migrate existing rows first |
| Rename column | No | Add new column, dual-write, deprecate old |
| Change data type (widening) | Usually | Test downstream compatibility |
| Change data type (narrowing) | No | Treat as breaking change; version the table |
| Remove column | No | Deprecate (keep, stop populating), then remove after notice period |
| Rename table | No | Create view alias; migrate consumers; drop original |

### Breaking change process
1. Create new table version: `mart.fact_orders_v2`
2. Dual-write period: populate both `v1` and `v2`
3. Notify all downstream consumers (BI dashboards, dbt models, APIs)
4. Migrate consumers to `v2`
5. Stop writing to `v1` after all consumers confirmed migrated
6. Create `mart.fact_orders` view pointing to `v2` (backward compat alias)
7. Decommission `v1` after retention window

### Data contract update requirement
Every schema change (compatible or breaking) must update the corresponding `data_contract.yaml`. See [templates/data_contract.yaml](../templates/data_contract.yaml).

---

## 9. Anti-Patterns

| Anti-Pattern | Impact | Fix |
|-------------|--------|-----|
| Fact table with no surrogate key | Cannot efficiently join to multiple dimensions | Add `_sk` surrogate key |
| Storing business logic in dimension attributes | Logic embedded in data, invisible to reviewers | Move logic to mart layer SQL / dbt model |
| `SELECT *` from large fact table in dbt staging model | Full scan on every dbt run | Explicit column list |
| Granularity mixing in a fact table | Incorrect aggregations; user confusion | One fact table = one grain (order, order line item, session) |
| EAV (entity-attribute-value) tables | Unpivot-heavy queries; no type safety | Use proper columns; JSON for truly sparse attributes |
| No date dimension | Ad-hoc date logic repeated in every query | Pre-build dim_date once; join to it |
| SCD Type 2 without `is_current` index | Slow queries that must filter `valid_to IS NULL` | Add partial index on `is_current = TRUE` |
| Soft-delete without `_deleted` flag | Consumers can't distinguish deleted vs missing | Always add `is_deleted BOOLEAN` + `deleted_at TIMESTAMP` |
| Circular lineage (model A references model B which references A) | dbt compile error; unmaintainable | Refactor shared logic to intermediate model |
| Overloading a single staging model for all source objects | Massive model, unclear lineage | One staging model per source entity |
