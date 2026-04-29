---
title: "Lineage & Observability"
description: "OpenLineage emission, dbt manifest export, lineage planes (DataHub / OpenMetadata / Marquez), SLO/SLI definition, and alerting strategy"
tags: [lineage, observability, openlineage, datahub, openmetadata, marquez, slo, sli, monitoring, alerting]
related_templates:
  - ../templates/slo_definition.md
  - ../templates/runbook.md
---

# Playbook 13 — Lineage & Observability

> **Guiding principles:** Observability by default (W007). Lineage is not optional (W009).
> A pipeline you can't see is a pipeline you can't fix. Emit lineage and metrics from day one — never bolt them on after the first incident.

This playbook turns Principles W007 and W009 into running code. It covers what to emit, where to send it, how to define SLOs/SLIs against the data, and how to alert on the right signals.

---

## 1. The Three Lineage Layers

Lineage exists at three layers. Confusing them is the most common source of "we have lineage but I still can't answer the question" pain.

| Layer | What it tracks | Owner | Examples |
|-------|----------------|-------|----------|
| **Code lineage** | Inputs/outputs declared in source files | Authors | dbt `ref()` / `source()`; Airflow `inlets` / `outlets`; Spark `spark.sql.lineage` |
| **Runtime lineage** | Inputs/outputs of an actual run | Orchestrator + processor | OpenLineage events from Airflow, Spark, dbt, Flink |
| **Catalog lineage** | Aggregated, queryable graph across systems | Catalog plane | DataHub, OpenMetadata, Marquez, Unity Catalog, Polaris |

**Rule:** code lineage is necessary but never sufficient. Without runtime lineage you can't answer "what actually ran last night and what did it touch?" Without catalog lineage you can't answer "if I drop this column, who breaks?"

---

## 2. OpenLineage — the wire format

[OpenLineage](https://openlineage.io) is a vendor-neutral standard for emitting lineage events as JSON. Every modern tool can produce or consume it. Treat it as the lingua franca; choose your catalog plane independently.

### Event shape

```json
{
  "eventType": "COMPLETE",
  "eventTime": "2026-04-29T08:15:30.000Z",
  "run": {
    "runId": "9f5d3e7a-2c1f-4b8a-94e1-7a7c4f0e3d2b"
  },
  "job": {
    "namespace": "warehouse.prod",
    "name": "dbt.fact_orders.run"
  },
  "inputs": [
    {
      "namespace": "warehouse.prod",
      "name": "raw.orders",
      "facets": {
        "schema": {
          "_producer": "https://github.com/openlineage/openlineage",
          "fields": [
            {"name": "order_id", "type": "VARCHAR"},
            {"name": "customer_id", "type": "VARCHAR"},
            {"name": "order_date", "type": "DATE"}
          ]
        }
      }
    }
  ],
  "outputs": [
    {
      "namespace": "warehouse.prod",
      "name": "mart.fact_orders",
      "facets": {
        "columnLineage": {
          "fields": {
            "order_id": {
              "inputFields": [
                {"namespace": "warehouse.prod", "name": "raw.orders", "field": "order_id"}
              ]
            }
          }
        }
      }
    }
  ]
}
```

### Producers (how to emit)

| Source | Mechanism |
|--------|-----------|
| Airflow 2.7+ | `apache-airflow-providers-openlineage` — set `OPENLINEAGE_URL` and the provider auto-emits per-task events |
| dbt 1.5+ | `dbt-ol run` (from [`OpenLineage-dbt`](https://openlineage.io/docs/integrations/dbt)); reads `manifest.json` + `run_results.json` and emits per-model events |
| Spark | `io.openlineage:openlineage-spark` listener jar; configured via `spark.extraListeners` |
| Flink | `io.openlineage:openlineage-flink` runtime listener |
| Kafka Connect | Connector-specific; or rely on `kafka` namespace + topic names |
| Generic / homegrown | Emit JSON to the OpenLineage HTTP receiver directly |

### Receivers (where to send)

```bash
# Marquez — open-source reference receiver, MIT license, REST + UI
export OPENLINEAGE_URL=https://marquez.example.com
export OPENLINEAGE_API_KEY=...
export OPENLINEAGE_NAMESPACE=warehouse.prod

# DataHub — accepts OpenLineage via the openlineage-datahub connector
# OpenMetadata — accepts OpenLineage via the openlineage-meta connector
# Many managed catalogs (Unity Catalog, Snowflake Horizon, BigQuery Lineage) ingest natively
```

**Rule:** emit OpenLineage from every batch and streaming job, even if your catalog plane is unsettled. Events are cheap to produce; routing them is a knob you can change later.

---

## 3. dbt manifest as a first-class lineage artifact

dbt's `target/manifest.json` and `target/run_results.json` together form a complete catalog of every model, every column, every test, and every run timing. Treat them as a deployable artifact:

```bash
# In CI, after every build of prod
dbt run --target prod
dbt test --target prod
dbt docs generate --target prod

# Upload to your catalog plane
upload_to_catalog target/manifest.json target/run_results.json target/catalog.json
```

### What to extract from `manifest.json`

| Field | Use |
|-------|-----|
| `nodes.<id>.depends_on` | Code lineage edges |
| `nodes.<id>.columns` | Column-level schema |
| `nodes.<id>.config.contract.enforced` | Which models advertise stability |
| `nodes.<id>.access` | Public / protected / private |
| `nodes.<id>.deprecation_date` | Which models are retiring |
| `sources.<id>.freshness` | SLA inputs for the freshness SLI (§5) |

### Catalog plane integration

| Plane | dbt connector |
|-------|---------------|
| DataHub | `acryl-datahub`'s `dbt-cloud` or `dbt-local` source |
| OpenMetadata | `metadata.ingestion.source.database.dbt` |
| Marquez | OpenLineage `dbt-ol` adapter |
| Atlan | dbt Cloud OAuth integration |
| Unity Catalog | dbt-databricks emits lineage to UC automatically |

---

## 4. SLOs and SLIs for data products

You can't define an alert before you've defined a service level. Borrow the SRE framing: **SLI** is the measured signal, **SLO** is the target, **error budget** is what you spend before paging on-call.

### The four data SLIs every mart needs

| SLI | Definition | Measurement |
|-----|------------|-------------|
| **Freshness** | Time between event-time and availability in the mart | `MAX(event_time)` vs `MAX(loaded_at)` per partition |
| **Completeness** | Fraction of expected rows that arrived | `actual_row_count / expected_row_count` (expected from contract or rolling baseline) |
| **Validity** | Fraction of rows passing required-field / domain checks | `passing_rows / total_rows` from DQ checks (Playbook 05) |
| **Accuracy / Reconciliation** | Agreement with source system on key totals | `warehouse_total / source_total` for a chosen reconciliation key |

### SLO template

```yaml
# orders_fact_orders.slo.yml
data_product: warehouse.mart.fact_orders
owner_team: data-platform
oncall_rotation: data-oncall@example.com

slis:
  freshness:
    metric: max(event_time) vs max(loaded_at)
    objective: "P99 ≤ 2 hours during business window 06:00–22:00 local"
    measurement_window: 30 days
    error_budget: "1% of business-window minutes"

  completeness:
    metric: actual_row_count / expected_row_count
    objective: "≥ 99.5%"
    measurement_window: 7 days
    error_budget: "0.5% of partitions"

  validity:
    metric: dq_check_pass_rate
    objective: "≥ 99.9% of rows pass required checks"
    measurement_window: 7 days
    error_budget: "0.1% of rows per partition"

  reconciliation:
    metric: warehouse_revenue / source_revenue
    objective: "Within ±0.1% of source on T-1 close"
    measurement_window: 30 days
    error_budget: "0.1% drift, escalating to incident at 0.5%"

policies:
  alert_on_burn_rate: true       # page when error budget consumed faster than linearly
  weekly_review: true            # post weekly burn rate to the team channel
  freeze_on_exhaustion: true     # halt non-critical changes when budget < 0
```

### Burn-rate alerting

Page when the error budget is being **consumed faster than linearly**, not on every breach. This catches the "slow drift to disaster" case without paging on every transient hiccup.

```sql
-- Burn-rate query: how fast are we burning the freshness budget over the last 1h vs 24h?
WITH freshness_breaches AS (
  SELECT
    DATE_TRUNC('hour', loaded_at) AS hour_bucket,
    SUM(CASE WHEN freshness_minutes > 120 THEN 1 ELSE 0 END) AS breach_count,
    COUNT(*) AS total_count
  FROM mart.fact_orders_freshness_log
  WHERE loaded_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
  GROUP BY 1
)
SELECT
  SUM(breach_count) FILTER (WHERE hour_bucket >= CURRENT_TIMESTAMP - INTERVAL '1 hour')::FLOAT
    / NULLIF(SUM(total_count) FILTER (WHERE hour_bucket >= CURRENT_TIMESTAMP - INTERVAL '1 hour'), 0)
    AS burn_1h,
  SUM(breach_count)::FLOAT / NULLIF(SUM(total_count), 0) AS burn_24h
FROM freshness_breaches;
-- Page when burn_1h > 14 * SLO_target  (the "fast burn" signal)
-- Page when burn_24h > 6 * SLO_target  (the "slow burn" signal)
```

---

## 5. Pipeline-level metrics to emit

Every job (Airflow task, dbt run, Spark job, Flink operator) must emit these at a minimum:

```python
# Pseudocode — adapt to your metric backend (Datadog / Prometheus / OTLP)
emit_gauge("pipeline.rows_in",        rows_in,        tags=[job, partition_date])
emit_gauge("pipeline.rows_out",       rows_out,       tags=[job, partition_date])
emit_gauge("pipeline.bytes_scanned",  bytes_scanned,  tags=[job, partition_date])
emit_timing("pipeline.duration_ms",   end_ms - start_ms, tags=[job])
emit_gauge("pipeline.freshness_min",  freshness_min,  tags=[job, dataset])
emit_counter("pipeline.dq_failures",  dq_fail_count,  tags=[job, check_type])
emit_counter("pipeline.run_outcome",  1,              tags=[job, outcome])  # success / failed / partial
```

**Rule:** if you can't query "rows_in vs rows_out per partition for the last 30 days" in your metrics backend, you don't have observability. You have logs.

### OpenTelemetry as the wire protocol

Use OTLP for metrics + traces; route to whatever backend your platform team picked. Avoid coupling pipeline code to a specific vendor SDK.

```python
from opentelemetry import metrics

meter = metrics.get_meter("warehouse.fact_orders")
rows_in = meter.create_counter("pipeline.rows_in", description="Source rows read this run")
rows_in.add(extracted_rows, attributes={"job": "fact_orders", "partition": ds})
```

---

## 6. Catalog plane: DataHub vs OpenMetadata vs Marquez

All three speak OpenLineage. Choose by feature set, not by hype.

| Plane | Best for | Trade-off |
|-------|----------|-----------|
| **DataHub** | Large orgs, rich UI, semantic tagging, glossary, governance workflows | Heavyweight; steep ops cost; opinionated about identity |
| **OpenMetadata** | Mid-size, Python-native ingestion, profiling + DQ in one tool | Younger ecosystem; UI is improving but less polished |
| **Marquez** | OpenLineage-only setups, strong run-level lineage, lighter footprint | Minimal UI; treat as an event store, surface with your own dashboards |
| **Unity Catalog** | Databricks-native; deep lineage on Spark/dbt/notebooks | Locked to Databricks compute; lineage ends at the UC boundary |
| **Snowflake Horizon / BigQuery Data Lineage** | Native to a single warehouse, zero ops | Doesn't span warehouses; cross-system lineage requires another plane |

**Rule:** pick one **catalog plane** as the source of truth for "who depends on what" — running two in parallel without a clear mapping is worse than running none. Federate read-only views into BI tools; don't sync writes.

---

## 7. Tying it back: the on-call escalation chain

When an SLO is breached, lineage answers "who do I tell?" — not the alerting system.

```
freshness SLO breach
  ↓
runbook lookup (linked from data_contract.yaml.owner)
  ↓
catalog query: "what consumes warehouse.mart.fact_orders?"
  ↓
notify owners of every consumer with sla_dependency: true
  ↓
post-incident: review reconciliation SLI for downstream marts
```

Your runbook (template at [`../templates/runbook.md`](../templates/runbook.md)) **must** name the catalog query needed to find consumers. Hardcoding the consumer list ages badly.

---

## 8. Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Emit lineage only in production | Dev/staging changes break consumers undetected | Emit OpenLineage from every environment; namespace by env |
| One vague SLO ("data should be fresh") | Unmeasurable; can't define error budget | Quantify: P99, business window, measurement period |
| Page on every freshness miss | On-call burnout; real incidents drown in noise | Burn-rate alerts (§4); freshness misses are a budget burn, not always an incident |
| Alert system as the consumer registry | Stale; humans forget to update it | Catalog plane (§6) is the consumer registry; alert system reads from it |
| Lineage UI as the only consumer | Humans look at it once a quarter | Make lineage queryable by code (REST/SQL); use it in CI to gate breaking changes |
| Column-level lineage but no `principlesCited` ID linkage | Reviewers can't map lineage to contract semantics | Reference principle IDs (W001-W012) in the runbook so the SRE link is explicit |
| dbt docs as the catalog | Doesn't include external producers (Airflow, Spark, Kafka) | dbt docs are *one input* to the catalog plane, not the plane itself |
| "We have logs" as the observability claim | Logs are unstructured and unqueryable at scale | Logs ≠ metrics ≠ traces ≠ lineage. You need all four — and they must reference the same `runId` |

---

## Quick Reference Checklist: Lineage & Observability

Before declaring a data product production-ready:

- [ ] OpenLineage events emitted from every job in the pipeline (W009)
- [ ] dbt `manifest.json` uploaded to the catalog plane on every prod build
- [ ] Catalog plane chosen and documented; all consumers federated read-only
- [ ] Per-job metrics emitted: rows_in, rows_out, bytes_scanned, duration, freshness, dq_failures, outcome (W007)
- [ ] SLOs defined for the four standard SLIs: freshness, completeness, validity, reconciliation
- [ ] Burn-rate alerts configured (fast + slow); error budget freezes non-critical changes when exhausted
- [ ] Runbook references the catalog query that finds downstream consumers; no hardcoded list
- [ ] Trace + run + lineage events share a `runId` so an incident can be reconstructed end-to-end
- [ ] Dev/staging environments emit lineage in their own namespace; not silenced

See the filled SLO template at [`../templates/slo_definition.md`](../templates/slo_definition.md) and the runbook template at [`../templates/runbook.md`](../templates/runbook.md).
