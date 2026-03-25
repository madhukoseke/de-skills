---
title: "Pipeline Design"
description: "Batch vs stream decision tree, hybrid patterns, architecture templates"
tags: [pipeline-design, batch, streaming, hybrid, architecture]
related_templates:
  - ../templates/data_contract.yaml
  - ../templates/runbook.md
  - ../templates/incident_postmortem.md
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
| **Team skill**       | SQL / Airflow        | SQL + some stream processing | Flink / Spark Streaming fluency |

### Quick Decision Flow

```
Freshness requirement?
  |
  +-- > 1 hour ---------> BATCH (Airflow + warehouse scheduled queries)
  |
  +-- 1 min to 1 hour --> MICRO-BATCH (Airflow short-interval DAG
  |                        or batch stream processor on cron)
  |
  +-- < 1 minute -------> Does transform need multi-source joins?
                             |
                             +-- Yes --> HYBRID (stream ingest, batch transform)
                             +-- No  --> STREAMING (broker -> processor -> warehouse)
```

**Rule of thumb:** If the stakeholder says "real-time" but the dashboard refreshes
every 15 minutes, you need micro-batch, not streaming. Push back.

---

## 2. Batch Architecture Patterns

### 2a. EL (Extract-Load)

Best for: SaaS sources where you trust the source schema and transform in-warehouse.

```
[ Source API ]                  [ Warehouse ]
  (Salesforce,  ---> staging ---> raw schema ---> dbt / scheduled SQL ---> mart
   HubSpot)         storage
```

- **Tools:** API extractor (Airbyte, Fivetran, custom script), object storage for landing, warehouse LOAD job.
- **Orchestration:** Airflow DAG with appropriate load operator.
- **Idempotency:** Write to date-partitioned landing prefix; LOAD job uses truncate-and-replace on partition.

### 2b. ELT (Extract-Load-Transform)

Best for: High-volume sources where raw data must be queryable before transformation.

```
[ Source DB ] --CDC/dump--> object storage (Avro/Parquet) --LOAD--> raw --dbt--> curated ---> mart
```

- **Tools:** CDC connector (Debezium, Airbyte) or batch dump + warehouse bulk load.
- **Idempotency:** Staging tables with MERGE. Never INSERT blindly into curated layer.
- **Separation of concerns:** Airflow orchestrates; dbt transforms. No SQL in DAG files.

### 2c. ETL (Extract-Transform-Load)

Use only when: Data must be reshaped before it can land (PII scrubbing, format conversion).

```
[ Source ] ---> Spark/Flink (Batch) ---> object storage (cleaned) ---> warehouse
```

- **Tools:** Spark batch, triggered by Airflow.
- **Warning:** ETL hides lineage. Prefer ELT unless regulatory requirements force pre-load transformation.

---

## 3. Streaming Architecture Patterns

### 3a. Standard Streaming Pipeline

```
                                  +---> Warehouse (bulk streaming sink)
                                  |
[ Event Source ] --> Broker --> Stream Processor --+---> Object storage (archive)
                      |                           |
                      |                           +---> Secondary topic (fan-out)
                      v
                  Dead-Letter Topic
```

- **Broker:** Kafka, Kinesis, Pulsar. One topic per event type. Use schema validation.
- **Stream processor:** Flink, Spark Streaming, Kafka Streams. Set max parallelism.
- **Warehouse sink:** Prefer bulk/batch commit (every N seconds) over row-by-row inserts.
- **Fail loud:** Malformed messages go to dead-letter topic. Alert if DLT depth > 0.

### 3b. CDC Streaming (Change Data Capture)

```
[ Source DB ] --> CDC connector --> Broker --> Stream Processor --> Warehouse (MERGE)
    |
 binlog / WAL
```

- Use managed CDC (Debezium, Airbyte CDC). It handles initial snapshot + ongoing changes.
- MERGE into warehouse using the change event's operation type (INSERT/UPDATE/DELETE).
- Maintain a `_cdc_sequence` column for ordering guarantees.

### 3c. Event Sourcing

```
[ Microservice ] --> Broker (event log) --> Stream Processor --> Warehouse (append-only event store)
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
                    +---[ Batch Layer (Airflow + warehouse) ]---+
[ Source ] --> storage -+                                       +--> Serving (views)
              |          +---[ Speed Layer (stream processor) ]--+
              |
           Broker
```

**Why to usually avoid it:** You maintain two codepaths producing the same output.
Bugs diverge. Testing doubles. Use only when batch reprocessing is mandatory AND
real-time is non-negotiable AND you cannot use Kappa.

### 4b. Kappa Architecture (Preferred Hybrid)

```
[ Source ] --> Broker --> Stream Processor --> Warehouse (streaming)
                 |
                 +--> Replay from broker (retained messages) or object storage archive
```

- Single codepath for both real-time and reprocessing.
- Retain broker messages for replay window or archive to object storage.
- Reprocess by draining the job, replaying from archive, restarting.

### 4c. Stream Ingest + Batch Reconciliation

The most practical hybrid for teams adopting streaming incrementally.

```
[ Source ] --> Broker --> Stream Processor --> Near-real-time table (streaming)
                                                     |
Airflow (daily) ------------------------------------> Batch table (reconciled, SoR)
                                                     |
                                             Reconciliation query: compare counts,
                                             detect gaps, alert on drift > threshold
```

- Streaming table serves dashboards with < 1 min latency.
- Batch table is the system of record, rebuilt daily with idempotent loads.
- Daily reconciliation query compares row counts and checksums. Alert if drift > 0.1%.

---

## 5. Source-Specific Ingestion Guidance

| Source Type       | Example              | Recommended Pattern     | Tools                                    | Key Consideration                        |
|-------------------|----------------------|-------------------------|------------------------------------------|------------------------------------------|
| **REST API**      | Salesforce, Stripe   | Batch EL, daily/hourly  | Custom extractor + Airflow               | Paginate fully; store cursor in state    |
| **Database (CDC)**| Postgres, MySQL      | CDC streaming or daily dump | Debezium, Airbyte CDC               | CDC for freshness; dump for simplicity   |
| **Database (bulk)**| MySQL, Oracle       | Batch ELT, daily        | Warehouse bulk load                      | Full vs incremental: use watermark column|
| **File drop**     | Partner CSV/Parquet  | Event-driven EL         | File sensor + Airflow (trigger DAG)      | Validate schema on landing; quarantine bad files |
| **Event stream**  | App events, IoT     | Streaming                | Kafka + Flink/Spark Streaming            | Schema registry on broker topic          |
| **Webhook**       | GitHub, Slack events | Micro-batch             | Buffer to broker + stream processor      | Never write directly to warehouse from webhook handler |

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

| Layer       | Schema Naming        | Description                                    | Retention   | Access           |
|-------------|----------------------|------------------------------------------------|-------------|------------------|
| **Raw**     | `raw_{source}`       | Exact copy of source data. Append-only. Never modify. | 90 days+   | Data eng only    |
| **Staging** | `stg_{source}`       | Deduped, type-cast, renamed. Still 1:1 with source. | 30 days    | Data eng only    |
| **Curated** | `cur_{domain}`       | Business logic applied. Joins across sources. SCD. | Indefinite | Eng + analysts   |
| **Mart**    | `mart_{consumer}`    | Pre-aggregated, consumer-optimized views/tables. | Indefinite | Analysts + BI    |

### Naming Conventions

- Tables: `{layer}_{source}_{entity}` — e.g., `raw_salesforce_opportunities`
- Partitioned by: `_partition_date` (ingestion) or natural date column
- Staging dedup key column: `_row_hash` (SHA256 of business key columns)
- CDC tracking: `_loaded_at`, `_updated_at`, `_is_deleted`

---

## 7. Architecture Templates

### Standard Batch Pipeline

```
+-------------+     +----------+     +---------+     +-----------+     +----------+
|   Source     |     | Object   |     | Whouse  |     | Whouse    |     | Whouse   |
| (API / DB / |---->| Storage  |---->| raw_*   |---->| stg_*     |---->| mart_*   |
|  File)       |     | (landing)|     | schema  |     | schema    |     | schema   |
+-------------+     +----------+     +---------+     +-----------+     +----------+
       |                |                 |                |                |
   [Extractor]    [file trigger]    [LOAD job]        [dbt run]       [dbt run]
       |                |                 |                |                |
       +--- Airflow DAG orchestrates all steps, with retries ---------------+
                                          |
                                  [Row count checks at each boundary]
```

### Standard Streaming Pipeline

```
+-------------+     +---------+     +----------+     +---------+     +----------+
| Event Source |     | Broker  |     | Stream   |     | Whouse  |     | Whouse   |
| (App / IoT  |---->|  Topic  |---->| Processor|---->| raw_*   |---->| cur_*    |
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

| Component           | Retries | Backoff                  | Max Delay   |
|---------------------|---------|--------------------------|-------------|
| Airflow task        | 3       | Exponential with jitter  | 30 minutes  |
| API extraction      | 5       | Exponential (2^n * 1s)   | 5 minutes   |
| Warehouse load job  | 3       | Linear (60s intervals)   | 3 minutes   |
| Stream processor    | Infinite (built-in) | Managed by runner | N/A   |
| Broker push         | Use broker native retry | Exponential    | 600 seconds |

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

- Every broker subscription must have a dead-letter topic configured.
- Monitor DLT message count. Alert threshold: > 0 messages.
- DLT messages retain original attributes + error reason.

### Circuit Breaker

When a source is consistently failing, stop hammering it:

1. Track consecutive failures in Airflow Variable or state store.
2. After 3 consecutive failures, mark circuit as OPEN. Skip extraction, alert team.
3. After 1 hour cooldown, try a single probe request. If success, close circuit.
4. Log every state transition for audit.

### Data Reconciliation

Run daily reconciliation for every pipeline:

```sql
-- Compare source count vs warehouse landing count
SELECT
  DATE(loaded_at)    AS load_date,
  source_system,
  source_row_count,
  warehouse_row_count,
  ABS(source_row_count - warehouse_row_count)                       AS drift,
  ABS(source_row_count - warehouse_row_count) / source_row_count    AS drift_pct
FROM ops.reconciliation_log
WHERE drift_pct > 0.001  -- Alert on > 0.1% drift
```

---

## 9. Capacity Planning

### Estimation Worksheet

| Metric                    | Formula                                              | Example                  |
|---------------------------|------------------------------------------------------|--------------------------|
| **Daily ingest volume**   | rows/day * avg_row_bytes                             | 50M * 500B = 25 GB/day  |
| **Monthly storage**       | daily_volume * 30 * compression_ratio (0.3 columnar) | 25 * 30 * 0.3 = 225 GB |
| **Query cost (on-demand)**| bytes_scanned * warehouse_per_TB_rate                | 10 GB scan * $5/TB = $0.05 |
| **Stream processor**      | vCPU-hr * rate + GB-hr * rate                        | Platform-dependent      |
| **Broker throughput**     | ingest_GB/day * broker_rate                          | Platform-dependent      |

### Scaling Thresholds

| Indicator                         | Threshold            | Action                              |
|-----------------------------------|----------------------|-------------------------------------|
| Warehouse slot/concurrency utilization | > 80% sustained | Switch to reserved capacity         |
| Stream processor CPU              | > 70% sustained      | Increase max parallelism            |
| Airflow DAG parse time            | > 30 seconds         | Split DAG files, reduce top-level code |
| Broker oldest unacked message     | > 10 minutes         | Scale stream processor consumers    |
| Landing zone size                 | > 1 TB unprocessed   | Investigate stuck pipeline          |

### Right-Sizing Checklist

1. Start with the smallest Airflow environment. Scale only when parse times degrade.
2. Use stream processor autoscaling with a max workers cap. Never leave it unlimited.
3. Use on-demand warehouse compute until monthly spend justifies reserved capacity.
4. Archive raw data to cold object storage after 90 days.
5. Set broker message retention to the minimum acceptable replay window.

---

## Checklist: Before Shipping a New Pipeline

- [ ] Freshness requirement documented and validated with stakeholder
- [ ] Architecture pattern selected from this playbook with rationale
- [ ] Data contract YAML filled out (see `../templates/data_contract.yaml`)
- [ ] All four landing zones (raw/stg/cur/mart) defined with naming conventions
- [ ] Idempotency mechanism specified (MERGE / truncate+replace / dedup key)
- [ ] Retry and dead-letter strategy configured
- [ ] Row-count reconciliation query scheduled
- [ ] Capacity estimate completed with monthly cost projection
- [ ] Runbook created (see `../templates/runbook.md`)
- [ ] Monitoring: alerts on failure, drift, freshness SLA breach
