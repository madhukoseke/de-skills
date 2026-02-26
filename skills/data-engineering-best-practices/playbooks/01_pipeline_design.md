---
title: "Pipeline Design"
description: "Batch vs stream decision tree, hybrid patterns, architecture templates"
tags: [pipeline-design, batch, streaming, hybrid, architecture]
related_templates:
  - ../templates/data_contract.yaml
  - ../templates/runbook.md
---

# Pipeline Design Playbook

> **Guiding principles:** Idempotency first. Fail loud. Schema is a contract.
> Every decision in this playbook traces back to those three rules.

---

## 1. Batch vs Stream Decision Tree

Do not default to streaming because it sounds modern. Start with batch and only
add complexity when freshness requirements demand it.

### Decision Matrix

| Factor               | Batch                | Micro-Batch / Hybrid  | Streaming              |
|----------------------|----------------------|-----------------------|------------------------|
| **Freshness need**   | > 1 hour             | 1 min to 1 hour       | < 1 minute             |
| **Volume / day**     | Any                  | Any                   | Any (but cost scales)  |
| **Transform complexity** | Complex (joins, aggregations, ML) | Moderate       | Simple (filter, enrich, route) |
| **Cost budget**      | $                    | $$                    | $$$                    |
| **Ordering needs**   | Trivial (sorted at rest) | Per-window         | Per-key or global      |
| **Failure tolerance**| Re-run entire window | Re-run micro-window   | Dead-letter + replay   |
| **Team skill**       | SQL / Airflow        | SQL + some Beam       | Beam / Flink fluency   |

### Quick Decision Flow

```
Freshness requirement?
  |
  +-- > 1 hour ---------> BATCH (Cloud Composer + BQ scheduled queries)
  |
  +-- 1 min to 1 hour --> MICRO-BATCH (Composer short-interval DAG
  |                        or Dataflow batch on cron)
  |
  +-- < 1 minute -------> Does transform need multi-source joins?
                             |
                             +-- Yes --> HYBRID (stream ingest, batch transform)
                             +-- No  --> STREAMING (Pub/Sub -> Dataflow -> BQ)
```

**Rule of thumb:** If the stakeholder says "real-time" but the dashboard refreshes
every 15 minutes, you need micro-batch, not streaming. Push back.

---

## 2. Batch Architecture Patterns

### 2a. EL (Extract-Load)

Best for: SaaS sources where you trust the source schema and transform in-warehouse.

```
[ Source API ]                [ BigQuery ]
  (Salesforce,  ---> GCS ---> raw dataset ---> dbt / scheduled SQL ---> mart
   HubSpot)         (Avro)
```

- **GCP tools:** Cloud Functions or Cloud Run for extraction, GCS for landing, BigQuery LOAD jobs.
- **Orchestration:** Cloud Composer DAG with `GCSToBigQueryOperator`.
- **Idempotency:** Write to date-partitioned GCS prefix; LOAD job uses `WRITE_TRUNCATE` on partition.

### 2b. ELT (Extract-Load-Transform)

Best for: High-volume sources where raw data must be queryable before transformation.

```
[ Source DB ] --CDC/dump--> GCS (Avro/Parquet) --LOAD--> BQ raw --dbt--> BQ curated ---> BQ mart
```

- **GCP tools:** Datastream for CDC, `bq load` or Storage Write API for bulk.
- **Idempotency:** Staging tables with MERGE. Never INSERT blindly into curated layer.
- **Separation of concerns:** Airflow orchestrates; dbt transforms. No SQL in DAG files.

### 2c. ETL (Extract-Transform-Load)

Use only when: Data must be reshaped before it can land (PII scrubbing, format conversion).

```
[ Source ] ---> Dataflow (Batch) ---> GCS (cleaned) ---> BQ
```

- **GCP tools:** Dataflow batch (Apache Beam Python/Java), triggered by Composer.
- **Warning:** ETL hides lineage. Prefer ELT unless regulatory requirements force pre-load transformation.

---

## 3. Streaming Architecture Patterns

### 3a. Standard Streaming Pipeline

```
                                  +---> BQ (Storage Write API)
                                  |
[ Event Source ] --> Pub/Sub --> Dataflow (Beam) --+---> GCS (Avro archive)
                      |                           |
                      |                           +---> Pub/Sub (fan-out)
                      v
                  Dead-Letter Topic
```

- **Pub/Sub:** One topic per event type. Use schema validation on the topic.
- **Dataflow:** Use `STREAMING` mode with autoscaling. Set `max_num_workers`.
- **BigQuery:** Prefer Storage Write API over legacy streaming inserts (cheaper, exactly-once).
- **Fail loud:** Malformed messages go to dead-letter topic. Alert if DLT depth > 0.

### 3b. CDC Streaming (Change Data Capture)

```
[ Cloud SQL / AlloyDB ] --> Datastream --> Pub/Sub --> Dataflow --> BQ (MERGE)
         |
     binlog / WAL
```

- Use Datastream for managed CDC. It handles initial snapshot + ongoing changes.
- MERGE into BQ using the change event's operation type (INSERT/UPDATE/DELETE).
- Maintain a `_cdc_sequence` column for ordering guarantees.

### 3c. Event Sourcing

```
[ Microservice ] --> Pub/Sub (event log) --> Dataflow --> BQ (append-only event store)
                                                 |
                                          Materialize views for current state
```

- Append-only events table partitioned by `event_timestamp`.
- Materialize current state via scheduled query or materialized view.
- Never mutate the event store. Corrections are new events with correction type.

---

## 4. Hybrid Patterns

### 4a. Lambda Architecture (Use with Caution)

```
                    +---[ Batch Layer (Composer + BQ) ]---+
[ Source ] --> GCS -+                                     +--> Serving (BQ views)
              |     +---[ Speed Layer (Dataflow) ]--------+
              |
           Pub/Sub
```

**Why to usually avoid it:** You maintain two codepaths producing the same output.
Bugs diverge. Testing doubles. Use only when batch reprocessing is mandatory AND
real-time is non-negotiable AND you cannot use Kappa.

### 4b. Kappa Architecture (Preferred Hybrid)

```
[ Source ] --> Pub/Sub --> Dataflow --> BQ (streaming)
                 |
                 +--> Replay from Pub/Sub (retained messages) or GCS archive
```

- Single codepath for both real-time and reprocessing.
- Retain Pub/Sub messages for replay window (max 31 days) or archive to GCS.
- Reprocess by draining Dataflow job, replaying from archive, restarting.

### 4c. Stream Ingest + Batch Reconciliation

The most practical hybrid for teams adopting streaming incrementally.

```
[ Source ] --> Pub/Sub --> Dataflow --> BQ streaming table (near real-time)
                                             |
Cloud Composer (daily) --------------------> BQ batch table (reconciled, SoR)
                                             |
                                     Reconciliation query: compare counts,
                                     detect gaps, alert on drift > threshold
```

- Streaming table serves dashboards with < 1 min latency.
- Batch table is the system of record, rebuilt daily with idempotent loads.
- Daily reconciliation query compares row counts and checksums. Alert if drift > 0.1%.

---

## 5. Source-Specific Ingestion Guidance

| Source Type       | Example              | Recommended Pattern     | GCP Tools                                | Key Consideration                        |
|-------------------|----------------------|-------------------------|------------------------------------------|------------------------------------------|
| **REST API**      | Salesforce, Stripe   | Batch EL, daily/hourly  | Cloud Run + Composer                     | Paginate fully; store cursor in GCS      |
| **Database (CDC)**| Cloud SQL, Postgres  | CDC streaming or daily dump | Datastream, Dataflow                  | CDC for freshness; dump for simplicity   |
| **Database (bulk)**| MySQL, Oracle       | Batch ELT, daily        | `bq load`, Dataflow batch               | Full vs incremental: use watermark column|
| **File drop (GCS)**| Partner CSV/Parquet | Event-driven EL         | Cloud Functions + Composer (trigger DAG) | Validate schema on landing; quarantine bad files |
| **Event stream**  | App events, IoT     | Streaming                | Pub/Sub + Dataflow + BQ                  | Schema registry on Pub/Sub topic         |
| **Webhook**       | GitHub, Slack events | Micro-batch             | Cloud Run (buffer to Pub/Sub) + Dataflow | Never write directly to BQ from webhook handler |

---

## 6. Data Landing Zones

Every pipeline must flow through these layers. No shortcuts from raw to mart.

```
[ Source ] --> raw --> staging --> curated --> mart
                |         |          |          |
             Append   Dedupe     Business    Aggregated
             only     + type     rules +     + joined
                      cast       SCD logic   for consumers
```

### Layer Definitions

| Layer       | BQ Dataset Naming    | Description                                    | Retention   | Access           |
|-------------|----------------------|------------------------------------------------|-------------|------------------|
| **Raw**     | `raw_{source}`       | Exact copy of source data. Append-only. Never modify. | 90 days+   | Data eng only    |
| **Staging** | `stg_{source}`       | Deduped, type-cast, renamed. Still 1:1 with source. | 30 days    | Data eng only    |
| **Curated** | `cur_{domain}`       | Business logic applied. Joins across sources. SCD. | Indefinite | Eng + analysts   |
| **Mart**    | `mart_{consumer}`    | Pre-aggregated, consumer-optimized views/tables. | Indefinite | Analysts + BI    |

### Naming Conventions

- Tables: `{layer}_{source}_{entity}` -- e.g., `raw_salesforce_opportunities`
- Partitioned by: `_partition_date` (ingestion) or natural date column
- Staging dedup key column: `_row_hash` (SHA256 of business key columns)
- CDC tracking: `_loaded_at`, `_updated_at`, `_is_deleted`

---

## 7. Architecture Templates

### Standard Batch Pipeline

```
+-------------+     +-------+     +---------+     +-----------+     +----------+
|   Source     |     |  GCS  |     |   BQ    |     |    BQ     |     |    BQ    |
| (API / DB / |---->| raw/  |---->| raw_*   |---->| stg_*     |---->| mart_*   |
|  File)       |     | avro/ |     | dataset |     | dataset   |     | dataset  |
+-------------+     +-------+     +---------+     +-----------+     +----------+
       |                |               |                |                |
   [Cloud Run]    [GCS trigger]   [LOAD job]        [dbt run]       [dbt run]
       |                |               |                |                |
       +--- Cloud Composer DAG orchestrates all steps, with retries ------+
                                        |
                                  [Row count checks at each boundary]
```

### Standard Streaming Pipeline

```
+-------------+     +---------+     +----------+     +---------+     +----------+
| Event Source |     | Pub/Sub |     | Dataflow |     |   BQ    |     |    BQ    |
| (App / IoT  |---->|  Topic  |---->| Streaming|---->| raw_*   |---->| cur_*    |
|  / CDC)      |     |         |     |  Job     |     | (stream)|     | (sched.) |
+-------------+     +---------+     +----------+     +---------+     +----------+
                         |               |                                 |
                    [Schema val.]  [DLT on error]                   [Daily reconcile]
                         |               |
                    Dead-Letter     [Autoscale:
                      Topic         max_workers=N]
```

---

## 8. Failure Handling

> **Principle: Fail loud.** A silent data gap is always worse than a noisy failure.

### Retry Strategy

| Component        | Retries | Backoff                  | Max Delay   |
|------------------|---------|--------------------------|-------------|
| Airflow task     | 3       | Exponential with jitter  | 30 minutes  |
| API extraction   | 5       | Exponential (2^n * 1s)   | 5 minutes   |
| BQ load job      | 3       | Linear (60s intervals)   | 3 minutes   |
| Dataflow (streaming) | Infinite (built-in) | Managed by runner | N/A   |
| Pub/Sub push     | Use Pub/Sub native retry | Exponential    | 600 seconds |

### Dead-Letter Pattern

```
Main Topic --> Subscription --> Processing --> Success
                                    |
                                    +--> Failure (after retries)
                                            |
                                    Dead-Letter Topic --> DLT Subscription
                                            |
                                    [Alert: PagerDuty / Slack]
                                    [Manual inspect + replay]
```

- Every Pub/Sub subscription must have a dead-letter topic configured.
- Monitor DLT message count. Alert threshold: > 0 messages.
- DLT messages retain original attributes + error reason.

### Circuit Breaker

When a source is consistently failing, stop hammering it:

1. Track consecutive failures in Airflow Variable or GCS state file.
2. After 3 consecutive failures, mark circuit as OPEN. Skip extraction, alert team.
3. After 1 hour cooldown, try a single probe request. If success, close circuit.
4. Log every state transition for audit.

### Data Reconciliation

Run daily reconciliation for every pipeline:

```sql
-- Compare source count vs BQ landing count
SELECT
  DATE(loaded_at) AS load_date,
  source_system,
  source_row_count,
  bq_row_count,
  ABS(source_row_count - bq_row_count) AS drift,
  SAFE_DIVIDE(ABS(source_row_count - bq_row_count), source_row_count) AS drift_pct
FROM `project.ops.reconciliation_log`
WHERE drift_pct > 0.001  -- Alert on > 0.1% drift
```

---

## 9. Capacity Planning

### Estimation Worksheet

| Metric                    | Formula                                              | Example                  |
|---------------------------|------------------------------------------------------|--------------------------|
| **Daily ingest volume**   | rows/day * avg_row_bytes                             | 50M * 500B = 25 GB/day  |
| **Monthly BQ storage**    | daily_volume * 30 * compression_ratio (0.3 for columnar) | 25 * 30 * 0.3 = 225 GB |
| **BQ storage cost**       | active: $0.02/GB/mo, long-term: $0.01/GB/mo         | 225 * $0.02 = $4.50/mo  |
| **BQ query cost (on-demand)** | bytes_scanned * $6.25/TB                        | 10 GB scan = $0.0625    |
| **Dataflow (batch)**      | vCPU-hr * $0.056 + GB-hr * $0.003                   | 4 vCPU * 0.5hr = $0.112 |
| **Dataflow (streaming)**  | vCPU-hr * $0.069 + GB-hr * $0.003 (24/7)            | 2 vCPU * 720hr = $99/mo |
| **Pub/Sub**               | $40/TiB ingested                                     | 25 GB/day = ~$30/mo     |
| **Composer (small)**      | ~$350-500/mo (environment baseline)                  | Fixed cost               |

### Scaling Thresholds

| Indicator                         | Threshold            | Action                              |
|-----------------------------------|----------------------|-------------------------------------|
| BQ slot utilization               | > 80% sustained      | Switch to reserved slots / editions |
| Dataflow worker CPU               | > 70% sustained      | Increase `max_num_workers`          |
| Composer DAG parse time           | > 30 seconds         | Split DAG files, reduce top-level code |
| Pub/Sub oldest unacked message    | > 10 minutes         | Scale Dataflow consumers            |
| GCS landing zone size             | > 1 TB unprocessed   | Investigate stuck pipeline          |

### Right-Sizing Checklist

1. Start with the smallest Composer environment. Scale only when parse times degrade.
2. Use Dataflow autoscaling with `max_num_workers` cap. Never leave it unlimited.
3. Use BQ on-demand until monthly spend exceeds flat-rate break-even (~$10K/mo for 500 slots).
4. Archive raw data to GCS Coldline after 90 days. Use BQ external tables if ad-hoc access is needed.
5. Set Pub/Sub message retention to the minimum acceptable replay window (default 7 days, max 31).

---

## Checklist: Before Shipping a New Pipeline

- [ ] Freshness requirement documented and validated with stakeholder
- [ ] Architecture pattern selected from this playbook with rationale
- [ ] Data contract YAML filled out (see `../templates/data_contract.yaml`)
- [ ] All four landing zones (raw/stg/cur/mart) defined with naming conventions
- [ ] Idempotency mechanism specified (MERGE / WRITE_TRUNCATE / dedup key)
- [ ] Retry and dead-letter strategy configured
- [ ] Row-count reconciliation query scheduled
- [ ] Capacity estimate completed with monthly cost projection
- [ ] Runbook created (see `../templates/runbook.md`)
- [ ] Monitoring: alerts on failure, drift, freshness SLA breach
