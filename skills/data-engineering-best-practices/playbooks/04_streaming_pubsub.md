---
title: "Streaming & Pub/Sub"
description: "Pub/Sub design patterns, exactly-once processing, dead-letter, Dataflow"
tags: [streaming, pubsub, dataflow, real-time, exactly-once]
related_templates:
  - ../templates/runbook.md
  - ../templates/data_contract.yaml
  - ../templates/incident_postmortem.md
---

# Streaming & Pub/Sub

This playbook covers production patterns for building reliable streaming pipelines on Google Cloud Pub/Sub and Dataflow. Every recommendation here comes from hard-won operational experience -- follow these defaults unless you have a documented reason not to.

---

## 1. Pub/Sub Topic Design

### Naming Convention

Use a consistent, hierarchical naming scheme:

```
{env}-{domain}-{entity}-{event-type}
```

Examples:
- `prod-payments-transaction-created`
- `staging-inventory-stock-level-changed`
- `prod-users-profile-updated`

Never reuse a topic name after deletion. Pub/Sub retains metadata for a period after deletion and re-creation can cause silent message loss.

### Message Schema

- Always use a schema registry (Pub/Sub Schema or Confluent Schema Registry). Schemaless topics become unmaintainable after the second producer.
- Prefer Protocol Buffers over JSON for high-throughput topics. Protobuf gives you 3-5x smaller payloads and backward-compatible evolution by default.
- Include a `schema_version` field in every message even when using a registry. This makes debugging drastically easier.

### Message Structure: Attributes vs Body

| Put in **attributes** | Put in **message body** |
|---|---|
| Event type (`event_type: "ORDER_CREATED"`) | Full event payload |
| Schema version (`schema_version: "2"`) | Nested or large data structures |
| Trace/correlation ID | Business data fields |
| Source system identifier | Arrays, repeated fields |
| Partition/ordering key hint | Anything over 1 KB |

Attributes are indexed and filterable at the subscription level. Use them for routing, not for data.

### Ordering Keys

- Use ordering keys only when you need strict per-entity ordering (e.g., all events for `user_id=123` processed in sequence).
- Keep cardinality high: use entity IDs, not coarse keys like region. Low-cardinality keys create hot partitions and kill throughput.
- Ordering keys cap publish throughput to 1 MB/s per key. Plan accordingly.

---

## 2. Subscription Patterns

### Push vs Pull Decision Table

| Factor | Pull | Push |
|---|---|---|
| Consumer is a Dataflow pipeline | Yes | No |
| Consumer is a Cloud Run service | Possible | Preferred |
| Need exactly-once delivery | Yes (with Dataflow) | No (at-least-once only) |
| Consumer needs backpressure control | Yes | No |
| Latency requirement < 100ms | Pull with streaming pull | Push |
| Consumer behind a firewall | Yes | No (needs public endpoint) |

**Default choice**: Pull with streaming pull. It gives you the most control and works with exactly-once semantics in Dataflow.

### Acknowledgment Deadlines

- Set the ack deadline to at least 2x your p99 processing time.
- Use `modifyAckDeadline` to extend for long-running messages rather than setting a massive initial deadline.
- Default 10s deadline is almost never correct for data engineering workloads. Start at 60s for most batch-style consumers, 120s+ for anything that writes to BigQuery or runs transformations.

### Exactly-Once Delivery Settings

Enable exactly-once delivery on the subscription when your consumer supports it:

```bash
gcloud pubsub subscriptions create ${SUB_NAME} \
  --topic=${TOPIC_NAME} \
  --enable-exactly-once-delivery \
  --ack-deadline=60
```

Be aware: exactly-once delivery increases publish latency by ~50ms and reduces throughput. Only enable it when you actually need it.

---

## 3. Dead-Letter Topic Pattern

### When to Use

Always. Every production subscription must have a dead-letter topic. No exceptions.

### Configuration

```bash
gcloud pubsub subscriptions update ${SUB_NAME} \
  --dead-letter-topic=${DLT_TOPIC} \
  --max-delivery-attempts=5
```

**Max delivery attempts guidelines**:
- Transient failures (network, quota): 10-15 attempts (with exponential backoff via retry policy)
- Data quality failures (bad schema, missing fields): 5 attempts (it will not self-heal)
- Poison pill messages: 3 attempts (fail fast, investigate manually)

### Monitoring the Dead-Letter Queue

- Create a separate subscription on the DLT for monitoring. Never let DLT messages expire silently.
- Alert when DLT message count > 0. Dead-letter messages represent data loss until resolved.
- Build a reprocessing pipeline: read from DLT, fix the issue, republish to the original topic.

```yaml
# Example alert policy (Terraform)
resource "google_monitoring_alert_policy" "dlt_alert" {
  display_name = "Dead Letter Messages Detected"
  conditions {
    condition_threshold {
      filter          = "resource.type=\"pubsub_subscription\" AND metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND resource.label.subscription_id=\"${DLT_SUB}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
    }
  }
}
```

---

## 4. Dataflow (Apache Beam) Patterns

### Windowing Strategies

| Strategy | Use When | Example |
|---|---|---|
| **Fixed windows** | Regular aggregation intervals | 5-minute revenue totals |
| **Sliding windows** | Overlapping trend detection | 10-minute window, sliding every 1 minute |
| **Session windows** | User activity grouping | User clickstream with 30-minute gap timeout |
| **Global window** | Unbounded accumulation with triggers | Running counters, deduplication buffers |

**Default choice**: Fixed windows with event-time semantics. Start here and only move to sliding/session when the business logic demands it.

### Watermarks and Late Data

- Set `withAllowedLateness()` based on your data SLA, not on hope. Analyze actual data arrival patterns before choosing a value.
- Use `ACCUMULATING` mode when downstream consumers can handle retractions or updates. Use `DISCARDING` mode when downstream expects append-only data.
- A common production-tested configuration:

```java
.apply(Window.<Event>into(FixedWindows.of(Duration.standardMinutes(5)))
    .triggering(AfterWatermark.pastEndOfWindow()
        .withEarlyFirings(AfterProcessingTime.pastFirstElementInPane()
            .plusDelayOf(Duration.standardMinutes(1)))
        .withLateFirings(AfterPane.elementCountAtLeast(1)))
    .withAllowedLateness(Duration.standardHours(1))
    .accumulatingFiredPanes())
```

### Pipeline Best Practices

- Always set `--maxNumWorkers` to prevent cost runaway. Autoscaling with no ceiling is a billing incident waiting to happen.
- Use `--update` for pipeline updates, not stop-and-start. This preserves in-flight state.
- Set `--experiments=enable_recommendations` to get Dataflow's built-in performance suggestions.

---

## 5. BigQuery Sink Patterns

### Storage Write API vs Streaming Inserts

| Factor | Storage Write API | Legacy Streaming Inserts |
|---|---|---|
| Cost | Free (batch), $0.025/GB (committed) | $0.010/200 MB ($0.05/GB) |
| Exactly-once | Yes (COMMITTED mode) | No (best-effort dedup) |
| Throughput | Higher | Lower |
| Latency to queryable | Seconds | Seconds |
| Recommended | **Yes** | No (legacy) |

**Default choice**: Storage Write API in COMMITTED mode. There is no good reason to use legacy streaming inserts for new pipelines.

### Exactly-Once with Storage Write API

Use the `COMMITTED` write mode with explicit stream offsets:

```python
write_result = (
    events
    | "Write to BQ" >> beam.io.WriteToBigQuery(
        table="project:dataset.table",
        method=beam.io.WriteToBigQuery.Method.STORAGE_WRITE_API,
        triggering_frequency=10,  # seconds
    )
)
```

For Dataflow pipelines, the Beam BigQuery connector handles offset management automatically in COMMITTED mode.

---

## 6. Exactly-Once vs At-Least-Once

### Decision Tree

1. **Can your sink handle duplicates natively?** (e.g., BigQuery MERGE, upsert to database) -> At-least-once is fine.
2. **Are you doing financial calculations or counting?** -> You need exactly-once or explicit deduplication.
3. **Is throughput > 100K msg/s?** -> At-least-once + idempotency may outperform exactly-once.
4. **Can you afford ~50ms additional latency?** -> Exactly-once is viable.

### Idempotency Strategies for At-Least-Once

- **Natural key deduplication**: Include a unique `event_id` in every message. Deduplicate using BigQuery MERGE or a Redis set before processing.
- **Idempotent writes**: Use `INSERT ... ON CONFLICT DO NOTHING` or BigQuery `MERGE` with match on event ID.
- **Time-window deduplication**: Keep a Bloom filter or windowed set of seen IDs. Sufficient for most use cases with <0.01% false positive rate.

### Deduplication Pattern in Beam

```java
events
    .apply("Dedup", Deduplicate.<Event>values()
        .withDuration(Duration.standardHours(1))
        .withRepresentativeValueFn(e -> e.getEventId()))
```

---

## 7. Capacity Planning

### Pub/Sub Throughput Limits

| Limit | Value | Notes |
|---|---|---|
| Publish throughput per topic | 1,000 MB/s | Soft limit, can be increased |
| Subscribe throughput per subscription | 500 MB/s | Soft limit |
| Message size | 10 MB max | Keep under 1 MB for performance |
| Attributes per message | 100 | Each key+value <= 1 KB |
| Ordering key throughput | 1 MB/s per key | Hard limit |

### Scaling Considerations

- Pub/Sub scales automatically but plan for burst capacity: request quota increases before known traffic spikes (marketing campaigns, seasonal events).
- Dataflow autoscaling reacts in 1-2 minutes. For sub-second burst absorption, overprovision workers by 20%.
- Monitor `subscription/backlog_bytes`. If this grows steadily, your consumer is underprovisioned.

---

## 8. Monitoring and Alerting

### Key Metrics to Track

| Metric | Alert Threshold | Meaning |
|---|---|---|
| `subscription/oldest_unacked_message_age` | > 300s | Consumer is falling behind |
| `subscription/num_undelivered_messages` | Sustained growth | Consumer cannot keep up |
| `subscription/dead_letter_message_count` | > 0 | Messages are failing permanently |
| `topic/send_request_count` (errors) | > 1% error rate | Publisher issues |
| `subscription/ack_latencies` p99 | > ack_deadline | Risk of redelivery storms |
| Dataflow `system_lag` | > 5 minutes | Pipeline processing delay |
| Dataflow `data_watermark_age` | > allowed_lateness | Data loss risk |

### Alert Configuration Principles

- Alert on backlog growth rate, not just absolute size. A 1 million message backlog that is shrinking is less urgent than a 1,000 message backlog that is growing.
- Page on `oldest_unacked_message_age` exceeding your SLA. This is the single most important streaming metric.
- Log and dashboard everything else. Not every metric needs a pager alert.

---

## 9. Common Anti-Patterns

| Anti-Pattern | Problem | Correct Approach |
|---|---|---|
| No dead-letter topic | Poison pills block processing forever | Always configure DLT with max delivery attempts |
| Ack before processing | Data loss on consumer crash | Ack only after successful processing and persistence |
| Giant messages (>1 MB) | Increased latency, higher costs | Store payload in GCS, send reference in message |
| Single subscription for multiple consumers | Consumers compete for messages | One subscription per consumer; use topic fan-out |
| Synchronous publish in request path | User-facing latency spike | Publish asynchronously, batch where possible |
| Unbounded Dataflow without max workers | Autoscaler provisions 1000 workers on a spike | Always set `--maxNumWorkers` |
| Ignoring ordering key throughput limit | Silent message drops | Shard ordering keys, keep cardinality high |
| Processing without idempotency | Duplicates corrupt aggregates | Design every consumer to handle redelivery safely |

---

## 10. Kafka as a Source (Hybrid / Multi-Cloud Scenarios)

When Kafka is your upstream event bus (on-premises or Confluent Cloud), bridge it to the GCP DE stack using one of these patterns.

### Pattern A: Kafka → Pub/Sub (Preferred for Full GCP Downstream)

Use the managed Pub/Sub Kafka connector or Dataflow's KafkaIO source. Keeps the downstream stack unchanged.

```java
// Apache Beam / Dataflow: read from Kafka, write to Pub/Sub
Pipeline p = Pipeline.create(options);

p.apply("ReadFromKafka", KafkaIO.<Long, String>read()
    .withBootstrapServers("broker1:9092,broker2:9092")
    .withTopic("orders")
    .withKeyDeserializer(LongDeserializer.class)
    .withValueDeserializer(StringDeserializer.class)
    .withConsumerConfigUpdates(ImmutableMap.of(
        "group.id", "gcp-bridge-consumer",
        "auto.offset.reset", "earliest"
    ))
    .withoutMetadata())
  .apply("ExtractValues", Values.create())
  .apply("WriteToPubSub", PubsubIO.writeStrings()
      .to("projects/my-project/topics/prod-orders-created"));
```

**Key considerations:**
- Use consumer group offsets, not time-based offsets, for reliable replay.
- Set `auto.offset.reset = earliest` for the bridge consumer so no messages are missed at startup.
- Monitor Kafka consumer group lag alongside Pub/Sub backlog.

### Pattern B: Kafka → Dataflow → BigQuery (Direct, Skip Pub/Sub)

Use when Kafka is the system of record and you don't need Pub/Sub fan-out.

```java
p.apply("ReadFromKafka", KafkaIO.<Long, GenericRecord>read()
    .withBootstrapServers("broker1:9092")
    .withTopic("orders")
    .withValueDeserializer(ConfluentSchemaRegistryDeserializerProvider.of(
        "http://schema-registry:8081", "orders-value"
    )))
  .apply("ParseAndTransform", ParDo.of(new OrderTransformFn()))
  .apply("WriteToBigQuery", BigQueryIO.<Order>write()
      .to("my-project:dataset.orders")
      .withWriteDisposition(BigQueryIO.Write.WriteDisposition.WRITE_APPEND)
      .withMethod(BigQueryIO.Write.Method.STORAGE_WRITE_API)
      .withTriggeringFrequency(Duration.standardSeconds(10)));
```

### Kafka → Pub/Sub via Managed Connector (No Code)

For teams on Confluent Cloud, use the GCP Pub/Sub Sink connector:

```json
{
  "name": "pubsub-sink-orders",
  "config": {
    "connector.class": "io.confluent.connect.gcp.pubsub.PubSubSinkConnector",
    "tasks.max": "4",
    "topics": "orders",
    "gcp.pubsub.project.id": "my-project",
    "gcp.pubsub.topic.id": "prod-orders-created",
    "key.converter": "org.apache.kafka.connect.storage.StringConverter",
    "value.converter": "io.confluent.connect.avro.AvroConverter",
    "value.converter.schema.registry.url": "http://schema-registry:8081"
  }
}
```

---

## 11. Schema Evolution

### Rules for Safe Evolution

1. **Adding a field**: Always safe. New consumers read it, old consumers ignore it (if using Protobuf or Avro).
2. **Removing a field**: Mark as deprecated first, stop all producers from sending it, then remove from schema after all consumers have migrated.
3. **Renaming a field**: Treat as remove + add. Never rename in place.
4. **Changing a field type**: Breaking change. Requires a new topic version.

### Versioned Topic Strategy

When a breaking change is unavoidable:

```
prod-payments-transaction-created-v1  (old consumers)
prod-payments-transaction-created-v2  (new consumers)
```

Run both topics in parallel during migration:
1. Producers publish to both v1 and v2.
2. Migrate consumers from v1 to v2 one at a time.
3. Drain v1 subscriptions (wait for backlog = 0).
4. Stop publishing to v1.
5. Delete v1 topic after a cool-down period (7 days minimum).

### Schema Registry Integration

Register schemas in Pub/Sub Schema Registry with `FULL` compatibility mode:

```bash
gcloud pubsub schemas create ${SCHEMA_NAME} \
  --type=PROTOCOL_BUFFER \
  --definition-file=./proto/event.proto

gcloud pubsub topics create ${TOPIC_NAME} \
  --schema=${SCHEMA_NAME} \
  --message-encoding=BINARY
```

This rejects any message that does not conform to the registered schema at publish time, catching producer bugs before they become consumer problems.
