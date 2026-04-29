---
title: "Streaming Architecture"
description: "Cloud-agnostic patterns for real-time and near-real-time pipelines: brokers, stream processors, CDC, windowing, exactly-once, and observability"
tags: [streaming, kafka, flink, spark-streaming, cdc, kafka-streams, kinesis, pulsar, dlq, exactly-once]
---

# Playbook 06 — Streaming Architecture

Covers: broker selection, topic/partition design, stream processing frameworks, CDC patterns, windowing, exactly-once semantics, dead-letter handling, and streaming observability.

---

## 1. When to Stream vs When to Batch

Use the decision tree from [01_pipeline_design.md](01_pipeline_design.md). Additional streaming-specific triggers:

| Requirement | Recommendation |
|-------------|----------------|
| Latency ≤ 1 minute | Stream (Kafka → Flink/Spark Streaming) |
| Latency 1–60 minutes | Micro-batch (Spark Structured Streaming, minute-interval Airflow) |
| Latency > 1 hour and volume < 10 GB/day | Batch is simpler and cheaper |
| Per-event triggers (fraud alert, notification) | Stream with stateful processing |
| Aggregations over rolling windows | Stream (tumbling/sliding/session windows) |
| Replayable, ordered delivery | Kafka (log-based) preferred over SQS/RabbitMQ |

**Default: prefer batch unless a streaming requirement is explicitly justified.** Streaming adds operational complexity (offset management, stateful failures, schema evolution across partitions).

---

## 2. Message Broker Selection

### Kafka (Apache / Confluent / MSK / Redpanda)
- **Best for:** high-throughput (>10K events/sec), ordered per-key delivery, replay, multiple consumers with independent offsets.
- **Strengths:** log retention (replay), consumer groups, exactly-once with transactions, rich ecosystem.
- **Watch out for:** partition rebalancing lag, consumer lag monitoring, key-based skew.

### Kinesis Data Streams (AWS)
- **Best for:** AWS-native stacks, moderate throughput (<1 MB/sec/shard), serverless preference.
- **Strengths:** tight IAM integration, no broker management, auto-scaling enhanced fan-out.
- **Watch out for:** shard count limits, iterator expiry, no log compaction.

### Pulsar (Apache)
- **Best for:** multi-tenant streaming, geo-replication requirements, mixed stream/queue semantics.
- **Strengths:** decoupled compute/storage, built-in schema registry, topic namespaces.
- **Watch out for:** operational complexity, smaller ecosystem than Kafka.

### SQS / RabbitMQ / ActiveMQ
- **Best for:** task queues, fan-out notification, simple pub/sub.
- **Not suitable for:** ordered event streams, replay, high-throughput analytics pipelines.

---

## 3. Topic / Partition Design

### Partition count
```
Target partitions = ceil(peak_events_per_sec / target_events_per_sec_per_partition)

Rule of thumb: 1 partition ≈ 10–50 MB/sec throughput, 1–5K msg/sec sustained.
Start conservative (12–24 partitions); adding partitions later breaks key ordering.
```

### Key selection
- **Partition key = unit of ordering.** Events with the same key always go to the same partition.
- Use `customer_id`, `order_id`, or `entity_id` as the key when per-entity ordering matters.
- Avoid keys with very high cardinality (UUID per event) — no ordering benefit, increases metadata overhead.
- **Hotspot warning:** if one key produces 10× more events than others, consider key salting or a compound key.

### Topic naming convention
```
<domain>.<entity>.<event-type>.<version>

Examples:
  orders.order.placed.v1
  payments.transaction.processed.v2
  inventory.product.updated.v1
```

### Retention
- **Raw ingest topics:** 7–30 days (enables replay during outages).
- **Processed/aggregated topics:** 1–3 days (downstream consumers are fast).
- **Dead-letter topics:** 14+ days (need time to investigate and replay).

---

## 4. Stream Processing Frameworks

### Apache Flink
- **Best for:** stateful stream processing, complex event processing (CEP), exactly-once end-to-end, low-latency windowing.
- **Key concepts:** `DataStream` API or `Table` API / SQL; checkpoints to durable storage for fault tolerance; watermarks for event-time processing.
- **Deployment:** standalone cluster, YARN, Kubernetes (`FlinkDeployment` CRD).
- **When to choose:** latency < 10 seconds, large state (joins across streams), complex windowing.

### Spark Structured Streaming
- **Best for:** unified batch + stream logic (same DataFrame/SQL API), Delta Lake / Iceberg sinks, existing Spark expertise.
- **Key concepts:** micro-batch (default) or continuous mode; `trigger(processingTime="X seconds")` controls micro-batch interval; `checkpointLocation` required for fault tolerance.
- **When to choose:** team already uses Spark, need Delta/Iceberg ACID sinks, batch + stream code reuse priority.

```python
# Spark Structured Streaming — idiomatic incremental read from Kafka
stream_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", BOOTSTRAP_SERVERS)
    .option("subscribe", "orders.order.placed.v1")
    .option("startingOffsets", "latest")
    .option("failOnDataLoss", "false")   # allow offset gaps on compacted topics
    .load()
)

parsed_df = stream_df.select(
    col("key").cast("string"),
    from_json(col("value").cast("string"), ORDER_SCHEMA).alias("data"),
    col("timestamp").alias("kafka_timestamp"),
)

query = (
    parsed_df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", CHECKPOINT_PATH)
    .option("mergeSchema", "true")
    .trigger(processingTime="60 seconds")
    .toTable("raw.orders_placed")
)
```

### Kafka Streams / ksqlDB
- **Best for:** lightweight stateful processing without a separate compute cluster; enrichment, filtering, aggregation close to the broker.
- **When to choose:** Kafka-only stack, small team, simple transformations (filter, join two topics, aggregate counts).
- **Not suitable for:** complex ML inference, large-state joins, non-Kafka sources.

---

## 5. CDC (Change Data Capture)

CDC converts database change logs into event streams, enabling near-real-time replication without polling.

### Recommended tools
| Source DB | CDC Tool | Output Target |
|-----------|----------|---------------|
| PostgreSQL | Debezium (pgoutput/wal2json) | Kafka |
| MySQL / MariaDB | Debezium (binlog) | Kafka |
| SQL Server | Debezium (SQL Server CDC) | Kafka |
| Oracle | Debezium / GoldenGate | Kafka |
| MongoDB | Debezium (oplog) | Kafka |
| Any relational | Airbyte (CDC mode) | Warehouse |

### Debezium patterns
```json
// Debezium connector config — PostgreSQL example
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "plugin.name": "pgoutput",
  "database.hostname": "db-host",
  "database.port": "5432",
  "database.user": "debezium_user",
  "database.password": "${file:/secrets/db.properties:password}",
  "database.dbname": "app_db",
  "table.include.list": "public.orders,public.customers",
  "topic.prefix": "cdc",
  "slot.name": "debezium_slot",
  "publication.name": "debezium_pub",
  "heartbeat.interval.ms": "30000",
  "snapshot.mode": "initial"
}
```

### CDC envelope format (Debezium)
Each CDC event contains `before`, `after`, `op` (c/u/d/r), and `source` metadata:
```json
{
  "before": {"id": 1, "status": "pending"},
  "after":  {"id": 1, "status": "shipped"},
  "op": "u",
  "ts_ms": 1711000000000,
  "source": {"db": "app_db", "table": "orders", "lsn": 12345}
}
```

### Applying CDC to a warehouse table (idempotent MERGE)
```sql
-- Warehouse upsert from CDC stream (generic SQL)
MERGE INTO warehouse.orders AS target
USING (
    SELECT
        after.id            AS order_id,
        after.status        AS status,
        after.updated_at    AS updated_at,
        op,
        _kafka_offset       AS kafka_offset
    FROM staging.orders_cdc_staging
    WHERE op IN ('c', 'u', 'r')  -- create, update, read (snapshot)
) AS src
ON target.order_id = src.order_id
WHEN MATCHED THEN UPDATE SET
    status     = src.status,
    updated_at = src.updated_at,
    _updated_at_utc = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN INSERT (order_id, status, updated_at, _updated_at_utc)
    VALUES (src.order_id, src.status, src.updated_at, CURRENT_TIMESTAMP);

-- Handle deletes separately (soft-delete recommended over physical delete)
UPDATE warehouse.orders
SET _deleted = TRUE, _deleted_at_utc = CURRENT_TIMESTAMP
WHERE order_id IN (
    SELECT after.id FROM staging.orders_cdc_staging WHERE op = 'd'
);
```

### CDC engine comparison (when to choose what)

| Engine | Operating model | Strengths | Watch-outs | Best for |
|--------|-----------------|-----------|------------|----------|
| **Debezium** (Kafka Connect) | Self-hosted; reads DB log directly | Open source; rich connector matrix; full event envelope; widely understood | Operational overhead; replication-slot management; one-connector-per-DB; restart sensitivity | Org has Kafka and SREs; you want control over the stream and full event history |
| **Debezium Server** | Standalone; sinks to Kinesis / Pulsar / EventHubs without Kafka | Same engine, no Kafka dependency | Less mature than Connect-based deployments; community-supported sinks vary | You want Debezium semantics on a non-Kafka broker |
| **Fivetran HVR** | Managed; agent-based on source | Mature; rich source coverage including legacy DBs (DB2, Informix, Tandem); transaction-consistent across tables | Vendor cost scales with rows; closed source | Mainframe / legacy / cross-table transactional workloads; you want a SaaS SLA |
| **Airbyte CDC** | OSS / managed; periodic CDC pull | Hundreds of source connectors; warehouse-first landing; cheap to start | Not true streaming (minute-scale at best); some sources still polling-based | Daily / hourly warehouse refreshes that don't need sub-minute latency |
| **Striim** | Managed; agent-based on source | Built-in stream SQL transformations; multi-target fan-out | Smaller community; SaaS lock-in | Heterogeneous source-to-target with in-flight transformation |
| **AWS DMS** | Managed; reads source log | Native to AWS; cheap; ongoing replication mode | Limited transformation; row-based, not log-based for some sources | AWS-native pipelines that just need replication |
| **Cloud-native** (Snowflake Streams, BigQuery CDC, Databricks DLT CDC, Postgres logical decoding to a managed sink) | Native to one platform | Tight integration; minimal ops | Limits you to that platform; cross-database CDC needs another tool | Single-platform shops that want zero CDC operational footprint |

**Decision rule:** if you can land CDC into the warehouse without a dedicated stream processor (because the warehouse sink + batch MERGE is enough), prefer the simpler managed option (Airbyte CDC / Fivetran / native). Reach for Debezium only when you need the **stream itself** — fan-out to multiple consumers, in-flight enrichment, or sub-minute downstream effects.

### Initial snapshot strategy

Every CDC pipeline starts with a backfill of existing rows before tailing the log. Three strategies, increasingly safe:

| Strategy | Lock cost | Time cost | Risk |
|----------|-----------|-----------|------|
| **Blocking snapshot** | Holds a long-running read transaction | High on big tables | Blocks DDL; can OOM the DB; only safe on small tables |
| **Incremental snapshot** (chunked) | Per-chunk row locks only | Higher overall latency, lower per-chunk impact | Requires the log to retain history past snapshot start |
| **External snapshot** (load from a backup or replica, then attach to the log) | Zero on primary | Highest: backup time + rebuild | Cleanest for huge tables; requires more orchestration |

Debezium's incremental snapshot (DBZ-3489) is the default for new pipelines on tables larger than ~50 GB. Always verify that the log retention window is **larger than the worst-case snapshot duration** — otherwise the connector falls off the log and a full re-snapshot is forced.

### Schema evolution in CDC streams

CDC events carry both data and schema. A DDL change in the source produces a schema change event. Handle each transition explicitly:

| DDL change | Compatibility | Pipeline action |
|------------|:-------------:|-----------------|
| Add column with default | Backward | Auto-add column to target table; treat as additive |
| Add column without default | Backward | Add column; backfill NULL or recompute from log |
| Drop column | Forward | Stop writing column to target; keep historical data |
| Rename column | None | Treat as drop + add; dual-write; deprecate old |
| Change type widening (`INT` → `BIGINT`) | Backward | Apply at target; verify no downstream casts narrow back |
| Change type narrowing | None | Treat as breaking; stop CDC; coordinate consumer migration |
| Change primary key | None | New table version; dual-CDC; cut over after consumer migration |

**Rule:** every CDC pipeline must have a **DLQ** for events whose schema is incompatible with the current target. Land them with the raw envelope and the inferred schema diff; alert; do not silently drop. Reference Playbook 12 §2 for compatibility-mode terminology.

### Transactional consistency across tables

Most relational sources commit groups of changes to multiple tables atomically. CDC tools differ in how they preserve that grouping:

- **Debezium / Fivetran HVR / Striim** — emit a transaction-id (or LSN ordering) on every event; consumers can reconstitute transactions if they keep events in LSN order.
- **Airbyte CDC** — typically does **not** preserve cross-table transactional grouping; the warehouse sees rows in arbitrary commit order. Acceptable for analytics, dangerous for systems that depend on cross-table invariants.

If your downstream depends on "an order row never appears without its line items", verify your CDC tool emits transaction grouping and that your sink applies it as a single MERGE batch keyed by transaction-id. Otherwise, build the invariant in at the mart layer with a delayed-publish gate (e.g., wait until both fact_orders and fact_order_items have the same `tx_id`).

### Idempotency in CDC consumers (W001)

CDC streams will replay. The contract is **at-least-once delivery**; consumers achieve **effectively-once application** by:

1. **Dedup by source LSN / position.** Every CDC event carries a monotonically increasing position (`source.lsn`, `source.txid`, Kafka offset, ingestion timestamp). The consumer tracks `(table, primary_key, max_applied_position)` and skips events with `position <= max_applied_position`.
2. **MERGE, never INSERT.** Like batch loads (W001), CDC apply uses MERGE on the primary key. The merge key includes the position so a replay updates rather than duplicates.
3. **Soft-delete for tombstones.** Deletes in CDC arrive as `op = 'd'`. Apply as `_deleted = TRUE` plus `_deleted_at_utc`; physical delete only when retention requires it (Playbook 14 §6 for erasure semantics).
4. **Tombstone for compaction.** When using Kafka log compaction, send a `null` value with the same key after the delete to release the slot.

### Heartbeats and lag monitoring

Without a heartbeat, a quiet table looks like a stuck connector — and a stuck connector looks like a quiet table. Always enable:

```json
{ "heartbeat.interval.ms": "30000",
  "heartbeat.action.query": "INSERT INTO debezium_heartbeat(ts) VALUES (NOW())" }
```

The heartbeat advances the source LSN even when no real changes occur, which keeps replication slots from filling up and gives consumers a lag signal:

```sql
-- Postgres-side: how much WAL is the slot holding?
SELECT slot_name, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)) AS lag_bytes
FROM pg_replication_slots;

-- MySQL: SHOW BINARY LOGS;  // compare to the connector's last position
-- SQL Server: dm_cdc_log_scan_sessions

-- Consumer-side: emit lag as a metric
emit_gauge("cdc.consumer_lag_seconds", lag_seconds, tags=[connector, source_table])
```

Alert when lag exceeds the freshness SLO from Playbook 13 §4.

### Outbox pattern (when CDC isn't enough)

When the source database can't be CDC'd cleanly (e.g., truncates, schema churn, no log access), use the **outbox pattern**:

```
[ App business logic ] ──┐
                          │  same transaction
                          ▼
              [ App table ] + [ outbox event row ]
                                       │
                                       ▼  CDC-tail this single table
                                  [ Kafka topic ]
```

The application writes the business row and an `outbox_events` row in the same transaction. CDC tails only `outbox_events` — predictable schema, append-only, controlled by the application team. This bypasses every "we can't CDC the schema migrations on the main table" complaint.

**Trade-off:** doubles the source-write cost and adds an application-side concern. Use only when direct CDC is infeasible.

---

## 6. Windowing

| Window Type | Definition | Use Case |
|-------------|-----------|---------|
| **Tumbling** | Fixed, non-overlapping intervals (e.g., 5-min buckets) | Metrics aggregation, billing |
| **Sliding** | Fixed size, advances by smaller step (e.g., 10-min window every 1 min) | Moving averages, rolling counts |
| **Session** | Gap-based; closes after inactivity period | User session analytics |
| **Global** | Processes all events regardless of time; manual trigger | Batch-like accumulation |

### Watermarks (event-time processing)
Watermarks define how long to wait for late-arriving events before closing a window.

```python
# Flink — watermark strategy for event-time with 30-second lateness tolerance
stream.assign_timestamps_and_watermarks(
    WatermarkStrategy
    .for_bounded_out_of_orderness(Duration.of_seconds(30))
    .with_timestamp_assigner(lambda e, _: e["event_ts_ms"])
)

# Spark — watermark for late data handling
stream_df.withWatermark("event_timestamp", "30 seconds") \
    .groupBy(window("event_timestamp", "5 minutes"), "customer_id") \
    .agg(count("*").alias("event_count"))
```

**Rule:** Set watermark delay ≥ P99 of your observed event-time latency. Too short = data loss; too long = memory pressure and output latency.

---

## 7. Exactly-Once Semantics

### At-least-once (default)
- Consumer commits offsets after processing; crash before commit → reprocessing.
- Safe only if downstream writes are idempotent (MERGE, upsert with unique key).

### Exactly-once (Kafka Transactions)
```python
# Kafka producer with exactly-once (transactional)
from confluent_kafka import Producer

producer = Producer({
    "bootstrap.servers": BOOTSTRAP_SERVERS,
    "transactional.id": "orders-processor-v1",
    "enable.idempotence": True,
})

producer.init_transactions()
try:
    producer.begin_transaction()
    producer.produce("output-topic", key=key, value=payload)
    producer.commit_transaction()
except Exception:
    producer.abort_transaction()
    raise
```

- **Flink:** enable checkpointing + `FlinkKafkaProducer` with `Semantic.EXACTLY_ONCE`.
- **Spark:** `forEachBatch` + idempotent sink writes (Delta MERGE or warehouse upsert).
- **Verdict:** Prefer **at-least-once + idempotent sink** in most cases. True exactly-once transactions add latency and operational complexity.

---

## 8. Dead-Letter Queues (DLQ)

Every streaming pipeline must have a DLQ. No exceptions.

### When to send to DLQ
- Schema validation failure (unexpected fields, type mismatch)
- Deserialization error (corrupted payload, wrong codec)
- Processing exception after max retries
- Business rule violation that is not retryable

### DLQ topic naming
```
<original-topic>.dlq

Example: orders.order.placed.v1.dlq
```

### DLQ message envelope (add metadata before routing)
```json
{
  "original_topic": "orders.order.placed.v1",
  "original_partition": 3,
  "original_offset": 99812,
  "original_timestamp_ms": 1711000000000,
  "error_type": "SchemaValidationError",
  "error_message": "Field 'total_amount' expected DECIMAL, got STRING",
  "failed_at_ms": 1711000050000,
  "processor_version": "orders-processor-v2.1.0",
  "raw_payload": "<base64-encoded original message>"
}
```

### DLQ handling in Flink
```java
// Flink — side output for DLQ routing
OutputTag<DlqRecord> dlqTag = new OutputTag<DlqRecord>("dlq"){};

SingleOutputStreamOperator<OrderEvent> processed = rawStream
    .process(new ProcessFunction<RawEvent, OrderEvent>() {
        @Override
        public void processElement(RawEvent event, Context ctx, Collector<OrderEvent> out) {
            try {
                out.collect(parse(event));
            } catch (Exception e) {
                ctx.output(dlqTag, DlqRecord.from(event, e));
            }
        }
    });

processed.getSideOutput(dlqTag).sinkTo(kafkaDlqSink);
```

---

## 9. Schema Registry and Evolution

Use a schema registry (Confluent Schema Registry, AWS Glue Schema Registry, Apicurio) with Avro or Protobuf serialization.

### Compatibility modes
| Mode | What it allows | When to use |
|------|---------------|-------------|
| BACKWARD | New schema can read old data | Default for consumers — new code reads old messages |
| FORWARD | Old schema can read new data | Default for producers — old consumers read new messages |
| FULL | Both backward and forward | Safest; strictest |
| NONE | No compatibility check | Never use in production |

### Safe evolution (FULL / BACKWARD compatible)
- Add a field with a **default value** — safe.
- Remove a field that has a **default value** — safe (backward).
- Rename a field — **breaking change**; use alias or add new field and deprecate old one.
- Change a field type — **always breaking**; use a new version topic.

### Version topic pattern (for breaking changes)
```
orders.order.placed.v1  →  orders.order.placed.v2

1. Produce to v2 topic with new schema.
2. Run dual-write period: produce to both v1 and v2.
3. Migrate all consumers to v2.
4. Stop writing to v1; keep retention for replay window.
5. Decommission v1 after all consumers confirm migration.
```

---

## 10. Streaming Observability

### Required metrics (emit for every streaming job)
| Metric | Description | Alert Threshold |
|--------|-------------|----------------|
| Consumer lag | Records behind latest offset | > 10K records for > 5 min |
| Processing throughput | Records/sec processed | < 10% of baseline for > 5 min |
| Error rate | Exceptions / records processed | > 1% |
| DLQ rate | Records routed to DLQ / total | > 0.1% |
| Checkpoint duration | Time to complete Flink checkpoint | > 2× baseline |
| End-to-end latency | Event time → sink write time | > SLA threshold |
| Watermark lag | Current watermark vs wall clock | > 2× watermark delay setting |

### Kafka consumer lag monitoring
```bash
# Check lag for a consumer group
kafka-consumer-groups.sh \
  --bootstrap-server broker:9092 \
  --describe \
  --group orders-processor-v1

# Output columns: TOPIC, PARTITION, CURRENT-OFFSET, LOG-END-OFFSET, LAG
```

### Alerting strategy
1. **P1 (page immediately):** consumer lag growing for > 15 min, DLQ filling at > 100 msg/min, job not running.
2. **P2 (alert, investigate within 1 hour):** throughput drop > 50%, error rate > 0.5%.
3. **P3 (track in dashboard):** slight lag fluctuation within normal bounds, occasional schema warnings.

---

## 11. Capacity Planning

```
Kafka storage per day:
  = events_per_sec × avg_message_bytes × 86400 × replication_factor

Example: 10K events/sec × 1 KB × 86400 × 3 = 2.59 TB/day

Consumer throughput:
  = events_per_sec / partitions_count  (events per partition per second)
  Ensure this is below the per-partition throughput limit of your consumer

Stream processor sizing (rule of thumb):
  - 1 CPU core handles 5K–50K events/sec (varies by processing complexity)
  - State store: size = (avg_state_record_bytes × unique_keys × replication)
  - Flink TaskManagers: 2–4 GB heap for low-state jobs; 8–32 GB for heavy aggregations
```

---

## 12. Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Bare INSERT on stream sink | Duplicates on reprocessing | MERGE or upsert with idempotency key |
| No DLQ | Silent data loss on processing errors | Add DLQ topic and routing for all error types |
| datetime.now() as event time | Non-deterministic replays | Use `event_timestamp` from the message payload |
| Partition count = 1 | No parallelism, no throughput scaling | Size partitions to throughput requirements |
| Storing large blobs in Kafka | Slow consumers, storage explosion | Store blob in object storage; put reference URL in message |
| No watermark | All windows wait indefinitely for late data | Set watermark to P99 latency of event delivery |
| Ignoring consumer lag | Silent backlog build-up goes undetected | Alert on consumer lag > threshold |
| Shared consumer group for different pipelines | One slow consumer starves others | Dedicated consumer group per logical consumer |
| Processing after schema change without registry | Downstream breaks silently | Enforce schema registry with BACKWARD compatibility |
| Long-running stateful operator without checkpoints | Job restart loses all state | Enable Flink checkpoints every 60–120 seconds |
