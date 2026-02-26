---
title: "Operational Runbook"
description: "Template for pipeline operational runbook"
tags: [runbook, operations, incident-response, template]
---

# Runbook: {PIPELINE_NAME}

**Owner:** {TEAM_NAME}
**Last Updated:** {DATE}
**On-call:** {ONCALL_ROTATION}
**Slack Channel:** {SLACK_CHANNEL}

## Pipeline Overview

| Property | Value |
|----------|-------|
| Pipeline name | {name} |
| DAG ID (if Airflow) | {dag_id} |
| Schedule | {e.g., "daily 06:00 UTC"} |
| Source(s) | {source systems} |
| Destination(s) | {destination tables/datasets} |
| SLA | {e.g., "Data available by 08:00 UTC"} |
| Expected duration | {e.g., "15-25 minutes"} |
| Expected row count | {e.g., "1M-3M rows/run"} |
| Data contract | {link to data contract YAML} |

## Architecture Diagram

```
{ASCII diagram of the pipeline flow}

Example:
  [Salesforce API] → [Cloud Composer Task] → [GCS Landing (Avro)]
                                                     ↓
                                            [BQ Load Job]
                                                     ↓
                                            [raw.salesforce_orders]
                                                     ↓
                                            [dbt transform]
                                                     ↓
                                            [mart.orders_daily]
```

## Monitoring & Alerts

| Alert | Condition | Severity | Response |
|-------|-----------|----------|----------|
| Pipeline failure | DAG run fails | P1 | See "Pipeline Failure" below |
| SLA miss | Not complete by {SLA_TIME} | P2 | See "SLA Miss" below |
| Data quality | Row count < {MIN} or > {MAX} | P2 | See "Data Quality" below |
| Freshness | No new data for > {THRESHOLD} | P2 | See "Stale Data" below |
| Source unavailable | Source API returns 5xx for > 15 min | P3 | See "Source Down" below |

## Common Failure Scenarios

### Pipeline Failure

**Symptoms:** DAG run marked as `failed` in Airflow UI.

**Diagnosis steps:**
1. Open Airflow UI → DAG runs → find the failed run
2. Click the failed task → View Log
3. Identify the error type:
   - **Connection error:** Source system unreachable → see "Source Down"
   - **Schema error:** Source schema changed → see "Schema Mismatch"
   - **Resource error:** BQ quota/slot exhaustion → see "Resource Exhaustion"
   - **Data error:** Unexpected NULLs, duplicates → see "Data Quality"

**Resolution:**
1. Fix the root cause (see specific scenario below)
2. Clear the failed task in Airflow: Task → Clear → confirm
3. Monitor the re-run to completion
4. Verify downstream data quality

### SLA Miss

**Symptoms:** Pipeline running but not complete by SLA deadline.

**Diagnosis steps:**
1. Check Airflow UI → DAG run → identify the slow task
2. Check BigQuery job history for long-running queries
3. Check source system response times
4. Check Composer resource utilization (CPU, memory)

**Resolution:**
1. If stuck on sensor: verify upstream dependency, consider `soft_fail`
2. If BQ query slow: check for missing partition pruning, full table scans
3. If source slow: check source system status, consider increasing timeout
4. If resource constrained: scale Composer environment or adjust parallelism

### Data Quality Issue

**Symptoms:** Row count anomaly, NULL spikes, duplicate records.

**Diagnosis steps:**
1. Compare current load metrics with historical baseline
2. Run data quality SQL checks:
   ```sql
   -- Row count comparison
   SELECT COUNT(*) as row_count, DATE(loaded_at) as load_date
   FROM `{TABLE}` WHERE DATE(loaded_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
   GROUP BY load_date ORDER BY load_date;

   -- NULL rate check
   SELECT
     COUNTIF({COLUMN} IS NULL) / COUNT(*) as null_rate
   FROM `{TABLE}` WHERE DATE(_PARTITIONTIME) = '{DATE}';

   -- Duplicate check
   SELECT {PRIMARY_KEY}, COUNT(*) as cnt
   FROM `{TABLE}` WHERE DATE(_PARTITIONTIME) = '{DATE}'
   GROUP BY {PRIMARY_KEY} HAVING cnt > 1;
   ```
3. Check source system for data issues

**Resolution:**
1. If source data issue: contact source team, document in incident
2. If pipeline bug: fix pipeline, re-run for affected partitions
3. If expected variation: update quality thresholds, document reason

### Schema Mismatch

**Symptoms:** `SchemaError`, `BigQueryError: no such field`, unexpected columns.

**Diagnosis steps:**
1. Compare source schema with data contract
2. Check if source deployed a schema change
3. Review data contract change log

**Resolution:**
1. If additive change (new column): update schema, backfill if needed
2. If breaking change: engage source team, follow change management process
3. Update data contract YAML with new schema version

### Source Down

**Symptoms:** Connection timeouts, HTTP 5xx errors, authentication failures.

**Diagnosis steps:**
1. Check source system status page
2. Verify credentials/tokens haven't expired
3. Check network connectivity from Composer environment

**Resolution:**
1. If source outage: wait for recovery, pipeline retries should handle automatically
2. If auth expired: rotate credentials in Secret Manager, restart affected tasks
3. If network issue: check VPC peering, firewall rules, Cloud NAT

### Resource Exhaustion

**Symptoms:** BQ quota errors, Composer OOM, slot reservation exceeded.

**Diagnosis steps:**
1. Check BQ admin console for slot utilization
2. Check Composer monitoring for CPU/memory usage
3. Check concurrent pipeline count

**Resolution:**
1. If BQ slots: reduce parallelism or request quota increase
2. If Composer: scale worker count/resources in environment config
3. If concurrent load: stagger pipeline schedules

## Backfill Procedure

1. Identify the date range to backfill: `{START_DATE}` to `{END_DATE}`
2. Verify the pipeline is idempotent (see data contract)
3. Run backfill:
   ```bash
   # Airflow CLI
   airflow dags backfill {DAG_ID} \
     --start-date {START_DATE} \
     --end-date {END_DATE} \
     --reset-dagruns
   ```
4. Monitor backfill progress in Airflow UI
5. Run data quality checks on backfilled partitions
6. Notify downstream consumers of backfill completion

## Escalation Path

| Level | Contact | When |
|-------|---------|------|
| L1 | On-call DE | First response, diagnosis |
| L2 | DE Team Lead | Unresolved after 30 min, or P1 severity |
| L3 | Platform/Infra | Composer/GCP infrastructure issues |
| L4 | Engineering Manager | SLA breach, data loss, customer impact |

## Key Links

| Resource | URL |
|----------|-----|
| Airflow UI | {URL} |
| BigQuery Console | {URL} |
| Source System Docs | {URL} |
| Data Contract | {PATH} |
| Alert Dashboard | {URL} |
| Slack Channel | {CHANNEL} |
