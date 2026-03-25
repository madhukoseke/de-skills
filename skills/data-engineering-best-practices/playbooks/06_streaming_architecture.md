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
