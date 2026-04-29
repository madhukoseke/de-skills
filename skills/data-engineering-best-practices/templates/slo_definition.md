---
title: "SLO Definition"
description: "Template for defining Service Level Objectives and Indicators on a data product"
tags: [slo, sli, observability, monitoring, data-product]
---

# SLO Definition Template

Fill in all fields. Used by DESIGN, AIRFLOW, STREAMING, DBT modes when a data product is being declared production-ready. Referenced by `playbooks/13_lineage_and_observability.md`.

---

## Data Product

**Name:** <!-- e.g., warehouse.mart.fact_orders -->
**Owner team:** <!-- e.g., data-platform -->
**On-call rotation:** <!-- e.g., data-oncall@example.com -->
**Slack / chat channel:** <!-- e.g., #data-eng-alerts -->
**Criticality tier:** <!-- tier-1 (revenue-impacting) | tier-2 (operational) | tier-3 (nice-to-have) -->
**Review cadence:** <!-- monthly | quarterly -->

---

## Business Window

**Window:** <!-- e.g., 06:00–22:00 local | 24/7 | weekdays only -->
**Local time zone:** <!-- e.g., America/Los_Angeles -->
**Notes:** <!-- e.g., quarterly close window has stricter SLO -->

---

## SLIs

Fill in each SLI applicable to this data product. Delete rows you do not measure.

### Freshness

| Field | Value |
|-------|-------|
| Metric | `MAX(event_time) - MAX(loaded_at)` per partition |
| Measurement source | <!-- e.g., mart.fact_orders_freshness_log --> |
| Objective | <!-- e.g., P99 ≤ 2 hours during business window --> |
| Measurement window | <!-- e.g., 30 days rolling --> |
| Error budget | <!-- e.g., 1% of business-window minutes --> |

### Completeness

| Field | Value |
|-------|-------|
| Metric | `actual_row_count / expected_row_count` per partition |
| Expected baseline | <!-- contract minimum / rolling 7d average / explicit upstream count --> |
| Objective | <!-- e.g., ≥ 99.5% --> |
| Measurement window | <!-- e.g., 7 days --> |
| Error budget | <!-- e.g., 0.5% of partitions per measurement window --> |

### Validity

| Field | Value |
|-------|-------|
| Metric | DQ check pass rate (rows passing required-field + domain checks) |
| Measurement source | <!-- e.g., dbt test results / Great Expectations checkpoint output --> |
| Objective | <!-- e.g., ≥ 99.9% of rows pass required checks --> |
| Measurement window | <!-- e.g., 7 days --> |
| Error budget | <!-- e.g., 0.1% of rows per partition --> |

### Reconciliation / Accuracy

| Field | Value |
|-------|-------|
| Metric | `warehouse_total / source_total` for the chosen reconciliation key |
| Reconciliation key | <!-- e.g., gross_revenue, order_count --> |
| Source of truth | <!-- e.g., upstream OLTP / source system close report --> |
| Objective | <!-- e.g., within ±0.1% on T-1 close --> |
| Measurement window | <!-- e.g., 30 days --> |
| Error budget | <!-- e.g., 0.1% drift; escalate to incident at 0.5% --> |

---

## Alerting Policy

| Signal | Threshold | Action |
|--------|-----------|--------|
| Fast burn (1h window) | <!-- 14 × SLO target --> | <!-- Page on-call --> |
| Slow burn (24h window) | <!-- 6 × SLO target --> | <!-- Page on-call --> |
| Single freshness miss | (No standalone alert — counts toward budget) | Log; review weekly |
| Validity drop > 1% absolute | <!-- e.g., one-shot alert --> | <!-- Slack alert + ticket --> |
| Reconciliation drift > 0.5% | <!-- one-shot --> | <!-- Page on-call; freeze releases --> |

---

## Error Budget Policy

| Budget remaining | Allowed actions | Forbidden actions |
|------------------|-----------------|-------------------|
| > 50% | Normal release cadence | — |
| 20–50% | Normal release; document mitigations | — |
| 0–20% | Bug fixes + reliability work only | New features without on-call sign-off |
| < 0% | Reliability work only; daily review until restored | All non-critical changes |

---

## Consumers

List downstream consumers with `sla_dependency: true`. Pull this from the catalog plane, not from memory.

| Consumer | Team | Usage | Notification path on incident |
|----------|------|-------|-------------------------------|
| | | | |

---

## Linked Artifacts

- Data contract: <!-- path to data_contract.yaml --> 
- Runbook: <!-- path to runbook.md -->
- Lineage view: <!-- catalog plane URL -->
- Dashboard: <!-- metrics dashboard URL -->

---

## Sign-off

**Author:** <!-- name --> 
**Reviewer (engineering):** <!-- name -->
**Reviewer (consumer team):** <!-- name -->
**Approval date:** <!-- YYYY-MM-DD -->
**Next review:** <!-- YYYY-MM-DD -->
