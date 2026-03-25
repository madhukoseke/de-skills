---
title: "Schema Management"
description: "Schema registry, schema evolution compatibility modes, migration patterns, drift detection, and catalog-first development"
tags: [schema, schema-registry, schema-evolution, drift-detection, data-catalog, migrations, avro, protobuf]
---

# Playbook 12 — Schema Management

Covers: schema registry (Confluent, AWS Glue, Apicurio), schema evolution compatibility modes, safe migration patterns, schema drift detection, and catalog-first development practices.

---

## 1. Schema Registry

A schema registry is a versioned, centralized store for message/event schemas. Required for all streaming pipelines; strongly recommended for batch pipelines with shared contracts.

### When to use a schema registry
| Use Case | Registry? |
|----------|-----------|
| Kafka / Kinesis streaming topics | **Required** |
| REST API producing JSON events | Recommended (OpenAPI / JSON Schema) |
| File-based batch pipelines | Optional (document in data_contract.yaml) |
| Internal dbt models (warehouse only) | Not needed; dbt + data contract YAML is sufficient |

### Confluent Schema Registry (Kafka)
```python
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer, AvroDeserializer

schema_registry_conf = {"url": "https://schema-registry:8081"}
client = SchemaRegistryClient(schema_registry_conf)

order_schema_str = """
{
  "type": "record",
  "name": "Order",
  "namespace": "com.example.orders",
  "fields": [
    {"name": "order_id",      "type": "string"},
    {"name": "customer_id",   "type": "string"},
    {"name": "total_amount",  "type": "double"},
    {"name": "order_status",  "type": "string"},
    {"name": "created_at",    "type": {"type": "long", "logicalType": "timestamp-millis"}},
    {"name": "discount_pct",  "type": ["null", "double"], "default": null}
  ]
}
"""

serializer = AvroSerializer(client, order_schema_str)
deserializer = AvroDeserializer(client)
```

### AWS Glue Schema Registry
```python
import boto3
import json

glue = boto3.client("glue", region_name="us-east-1")

# Register schema version
response = glue.register_schema_version(
    SchemaId={"SchemaName": "orders", "RegistryName": "de-schemas"},
    SchemaDefinition=json.dumps(order_schema_dict),
)

# Get latest schema version
latest = glue.get_schema_version(
    SchemaId={"SchemaName": "orders", "RegistryName": "de-schemas"},
    SchemaVersionNumber={"LatestVersion": True},
)
```

---

## 2. Schema Evolution Compatibility

### Compatibility modes (Avro / Confluent Schema Registry)

| Mode | New schema can read old data | Old schema can read new data | Practical meaning |
|------|------------------------------|------------------------------|------------------|
| **BACKWARD** | Yes | No | Consumers upgrade first; then producers |
| **FORWARD** | No | Yes | Producers upgrade first; then consumers |
| **FULL** | Yes | Yes | Both can coexist; safest for rolling deployments |
| **NONE** | No | No | No compatibility check — never use in production |

**Default: FULL compatibility** for shared Kafka topics. Requires all changes to be additive with defaults.

### Safe changes (FULL / BACKWARD / FORWARD compatible)
```json
// Adding a field with a default value — always safe
{
  "name": "shipping_address",
  "type": ["null", "string"],
  "default": null
}

// Removing a field that has a default value — backward compatible
// (old consumers ignore fields they don't know; new schema still has a default)
```

### Breaking changes — require new version
| Change | Compatible? | Action |
|--------|------------|--------|
| Add field without default | No | Add with `"default": null` |
| Remove field without default | No | Add default first; wait one release cycle; then remove |
| Rename field | No | Add new field (with default); deprecate old; dual-produce; migrate; remove |
| Change type (e.g., `int` → `string`) | No | Create `v2` topic; dual-produce; migrate consumers; sunset `v1` |
| Remove enum value | No | Keep enum value until all consumers handle its absence |

### Setting compatibility in Confluent Schema Registry
```bash
# Set FULL compatibility for a subject
curl -X PUT https://schema-registry:8081/config/orders.order.placed.v1-value \
  -H "Content-Type: application/json" \
  -d '{"compatibility": "FULL"}'

# Check schema before registering (dry-run compatibility check)
curl -X POST https://schema-registry:8081/compatibility/subjects/orders.order.placed.v1-value/versions/latest \
  -H "Content-Type: application/json" \
  -d '{"schema": "<escaped-avro-schema-json>"}'
```

---

## 3. Warehouse Schema Migration Patterns

### Migration file convention
```
migrations/
  V001__create_fact_orders.sql
  V002__add_discount_column.sql
  V003__add_order_channel_index.sql
  V004__rename_status_to_order_status.sql  ← breaking; requires dual-column approach
```

### Additive migration (safe)
```sql
-- V002__add_discount_column.sql
-- Safe: adding column with a default value
ALTER TABLE mart.fact_orders
ADD COLUMN IF NOT EXISTS discount_pct NUMERIC(5, 4) DEFAULT 0.0;

-- Update historical rows if needed
UPDATE mart.fact_orders SET discount_pct = 0.0 WHERE discount_pct IS NULL;
```

### Rename column (breaking — use dual-column approach)
```sql
-- V004a: Add new column and copy data
ALTER TABLE mart.fact_orders ADD COLUMN order_status VARCHAR(50);
UPDATE mart.fact_orders SET order_status = status;

-- V004b (next release): update all readers to use order_status
-- (deployed and validated before V004c)

-- V004c (after all readers migrated): drop old column
ALTER TABLE mart.fact_orders DROP COLUMN status;
```

### Type change (always breaking)
```sql
-- Never alter type in-place for columns with data.
-- Use table rename + recreate pattern:

-- Step 1: Create new table with correct type
CREATE TABLE mart.fact_orders_v2 AS
SELECT
    order_id,
    CAST(total_amount AS NUMERIC(14, 4)) AS total_amount,  -- was VARCHAR, now NUMERIC
    order_date,
    customer_id,
    _loaded_at
FROM mart.fact_orders;

-- Step 2: Add constraints and indexes
ALTER TABLE mart.fact_orders_v2 ADD CONSTRAINT pk_fact_orders_v2 PRIMARY KEY (order_id);

-- Step 3: Validate row counts match
SELECT
    (SELECT COUNT(*) FROM mart.fact_orders)    AS old_count,
    (SELECT COUNT(*) FROM mart.fact_orders_v2) AS new_count;

-- Step 4: Rename (atomic swap)
ALTER TABLE mart.fact_orders RENAME TO fact_orders_deprecated;
ALTER TABLE mart.fact_orders_v2 RENAME TO fact_orders;

-- Step 5: Drop old table after validation period
DROP TABLE mart.fact_orders_deprecated;
```

### Schema migration tooling
| Tool | Best For |
|------|---------|
| **Flyway** | Java/Kotlin projects; SQL-based migrations |
| **Liquibase** | Multi-database; XML or SQL changelogs |
| **dbt** (dbt-core) | dbt project schema changes via model updates |
| **Alembic** | Python projects (SQLAlchemy-based) |
| **Custom scripts** | Simple warehouse projects |

---

## 4. Schema Drift Detection

Schema drift occurs when source data changes structure without notice. Detect it early.

### Drift detection in ingestion (Python)
```python
import json
import hashlib

def compute_schema_fingerprint(df) -> str:
    """Stable fingerprint of a DataFrame schema for drift detection."""
    schema = [(f.name, str(f.dataType), f.nullable) for f in sorted(df.schema, key=lambda x: x.name)]
    return hashlib.md5(json.dumps(schema).encode()).hexdigest()

def detect_drift(expected_fingerprint: str, actual_df) -> bool:
    actual_fingerprint = compute_schema_fingerprint(actual_df)
    if actual_fingerprint != expected_fingerprint:
        new_cols = set(f.name for f in actual_df.schema) - EXPECTED_COLUMNS
        removed_cols = EXPECTED_COLUMNS - set(f.name for f in actual_df.schema)
        raise SchemaDriftError(
            f"Schema drift detected.\n"
            f"New columns: {new_cols}\n"
            f"Removed columns: {removed_cols}\n"
            f"Expected fingerprint: {expected_fingerprint}\n"
            f"Actual fingerprint: {actual_fingerprint}"
        )
```

### dbt source freshness + schema drift
```yaml
# sources.yml — enforce expected columns via dbt tests
sources:
  - name: raw
    tables:
      - name: orders
        loaded_at_field: _ingested_at
        freshness:
          error_after: {count: 12, period: hour}
        columns:
          - name: order_id
            tests: [not_null]
          - name: total_amount
            tests: [not_null]
```

### Airflow schema validation task
```python
from airflow.decorators import task
import pyarrow.parquet as pq

@task
def validate_schema(file_path: str, expected_schema_path: str):
    """Fail early if source schema has drifted."""
    actual = pq.read_schema(file_path)
    with open(expected_schema_path) as f:
        expected = pq.schema_from_pandas(json.load(f))

    mismatches = []
    for field in expected:
        actual_field = actual.field(field.name) if field.name in actual.names else None
        if actual_field is None:
            mismatches.append(f"MISSING: {field.name}")
        elif actual_field.type != field.type:
            mismatches.append(f"TYPE_MISMATCH: {field.name} expected={field.type} actual={actual_field.type}")

    if mismatches:
        raise ValueError(f"Schema drift detected in {file_path}:\n" + "\n".join(mismatches))
```

---

## 5. Catalog-First Development

A data catalog (Amundsen, DataHub, OpenMetadata, Atlan) is the source of truth for dataset discovery, lineage, and data contracts.

### Catalog-first workflow
```
1. Design schema → Document in catalog (description, owner, tags, SLA)
2. Register data contract (link to data_contract.yaml)
3. Build pipeline → Implement schema
4. Emit metadata from pipeline → Update catalog (lineage, run stats)
5. Validate → Run DQ checks; update catalog with quality score
6. Publish → Mark dataset as "certified" in catalog
```

### Metadata emission from Airflow (DataHub example)
```python
from datahub_airflow_plugin.hooks.datahub import DatahubRestHook
from datahub.emitter.mce_builder import make_dataset_urn

@task
def emit_lineage():
    hook = DatahubRestHook(datahub_rest_conn_id="datahub_rest_default")
    emitter = hook.make_emitter()

    lineage_mce = builder.make_lineage_mce(
        upstream_urns=[make_dataset_urn("postgres", "raw.orders")],
        downstream_urn=make_dataset_urn("snowflake", "mart.fact_orders"),
    )
    emitter.emit_mce(lineage_mce)
```

### Minimum catalog requirements for every dataset
| Field | Required | Example |
|-------|---------|---------|
| Name | Yes | `mart.fact_orders` |
| Description | Yes | "One row per order; daily partition by order_date" |
| Owner | Yes | `#data-engineering` |
| SLA | Yes | "Available by 08:00 UTC" |
| Data contract link | Yes | Link to `data_contract.yaml` |
| Upstream lineage | Yes | `raw.orders` → `staging.stg_orders` → `mart.fact_orders` |
| Tags | Yes | `pii: false`, `domain: commerce`, `tier: gold` |
| Last updated | Auto | From pipeline run metadata |
| DQ score | Auto | From DQ check results |

---

## 6. Schema Documentation Standards

Every table must have a documented schema in the data contract and/or dbt schema YAML.

```yaml
# data_contract.yaml excerpt — schema section
schema:
  version: "2.0.0"
  fields:
    - name: order_id
      type: VARCHAR(50)
      nullable: false
      description: "Natural order identifier from source CRM. Format: ORD-{YYYYMMDD}-{SEQ}"
      pii: false
      tests: [unique, not_null]

    - name: customer_id
      type: VARCHAR(50)
      nullable: false
      description: "References dim_customers.customer_id. Always exists at load time."
      pii: false
      tests: [not_null, relationships(dim_customers)]

    - name: total_amount
      type: NUMERIC(14, 4)
      nullable: false
      description: "Total order value in USD after discounts, before tax."
      pii: false
      tests: [not_null, accepted_range(min=0)]
```

---

## 7. Anti-Patterns

| Anti-Pattern | Impact | Fix |
|-------------|--------|-----|
| No schema registry for Kafka topics | Consumers break silently on producer schema changes | Register all topic schemas; enforce BACKWARD or FULL compatibility |
| `NONE` compatibility mode | Any schema change breaks consumers | Set at minimum BACKWARD; prefer FULL |
| In-place column type change | Data loss or silent truncation | Use rename + recreate + migrate pattern |
| No schema drift detection | Pipeline accepts wrong data silently | Add schema validation task before load |
| Schema documentation only in Confluence/Notion | Docs drift from actual schema | Document in code (dbt YAML + data_contract.yaml); auto-publish to catalog |
| Breaking changes without notice period | Consumers go down on deploy | Dual-write period minimum 1 sprint; communicate to all consumers |
| Storing schema in application code only | Multiple sources of truth; schema conflicts | Centralized schema registry or data contract YAML in git |
| Dropping columns immediately on rename | Readers using old column name break | Keep old column as alias/view for one release cycle |
| No catalog lineage | Cannot trace impact of upstream changes | Emit lineage from every pipeline (DataHub, OpenMetadata, Marquez) |
