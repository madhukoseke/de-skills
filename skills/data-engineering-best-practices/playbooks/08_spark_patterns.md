---
title: "Spark Patterns for Data Engineering"
description: "Production PySpark patterns: partitioning, skew, shuffle optimization, Delta/Iceberg/Hudi, Spark Structured Streaming, testing, and Airflow integration"
tags: [spark, pyspark, delta-lake, iceberg, hudi, spark-streaming, partitioning, shuffle, testing]
---

# Playbook 08 — Spark Patterns for Data Engineering

Covers: Spark vs SQL warehouse decision, partitioning and skew, shuffle optimization, open table formats (Delta / Iceberg / Hudi), Spark Structured Streaming, pytest+PySpark testing, and Airflow integration.

---

## 1. Spark vs SQL Warehouse — When to Use Which

| Factor | Use Spark | Use SQL Warehouse |
|--------|-----------|-------------------|
| Data volume | > 100 GB per job | < 100 GB per job |
| Processing complexity | Custom ML, complex transformations, graph processing | Aggregations, joins, window functions |
| Language | Python/Scala with custom libraries | SQL-first, BI-friendly |
| Output format | Parquet, Delta, Iceberg, Hudi | Native warehouse tables |
| Reusability | Shared code, custom UDFs, ML pipelines | Ad-hoc, BI layer, dbt models |
| Cost model | Pay per cluster-hour; spot instances possible | Pay per query / slot |
| Streaming | Spark Structured Streaming | Not suitable |

**Default: prefer a SQL warehouse (Snowflake, Redshift, Databricks SQL) for standard aggregations and joins. Reach for Spark when volume, complexity, or streaming requires it.**

---

## 2. SparkSession Configuration

```python
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("orders_daily_transform")
    .config("spark.sql.adaptive.enabled", "true")                # AQE — always enable
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
    .config("spark.sql.adaptive.skewJoin.enabled", "true")
    .config("spark.sql.shuffle.partitions", "200")               # tune per job; AQE adjusts down
    .config("spark.sql.files.maxPartitionBytes", "128m")         # target ~128 MB per partition
    .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
    .config("spark.sql.parquet.compression.codec", "snappy")
    .config("spark.dynamicAllocation.enabled", "true")           # scale executors to workload
    .getOrCreate()
)
```

---

## 3. Partitioning Strategy

### Input partitioning (reading data)
```python
# Read Parquet with partition discovery
df = spark.read.parquet("s3://bucket/orders/")
# Spark automatically discovers Hive-style partitions: order_date=2024-01-01/

# Coalesce or repartition before write if input has too many small files
df = df.coalesce(50)  # fewer files, same partition structure
```

### Output partitioning (writing data)
```python
# Partition by date for time-series data (enables partition pruning on reads)
(
    df.write
    .partitionBy("order_date")
    .mode("overwrite")           # idempotent for full partition refresh
    .parquet("s3://bucket/warehouse/fact_orders/")
)

# Dynamic partition overwrite — only overwrites partitions present in df
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
(
    df.write
    .partitionBy("order_date")
    .mode("overwrite")
    .parquet("s3://bucket/warehouse/fact_orders/")
)
```

### Partition sizing rules
- Target: **128 MB per partition** (matches `spark.sql.files.maxPartitionBytes`).
- Too small (<10 MB per partition): excessive task overhead → use `coalesce` or `repartition`.
- Too large (>512 MB per partition): executor OOM → reduce partition size or increase executor memory.
- Ideal partition count ≈ `total_data_size_bytes / 128_MB`.

### Repartition vs Coalesce
```python
# repartition: full shuffle, produces exactly N evenly-sized partitions
# Use before wide transformations or writing large outputs
df_balanced = df.repartition(200, "customer_id")  # hash partition by key

# coalesce: no shuffle, reduces partition count by merging
# Use at the end of a pipeline to reduce output file count
df_small = df.coalesce(10)
```

---

## 4. Skew Detection and Mitigation

### Detect skew
```python
# Check partition size distribution
df.rdd.mapPartitions(lambda p: [sum(1 for _ in p)]).collect()
# If one partition is 10× others → skew

# In Spark UI: Stages → Task metrics → look for max task duration >> median
```

### Skew mitigation strategies

**1. Salting the join key (for hot keys)**
```python
import pyspark.sql.functions as F
import random

SALT_FACTOR = 10

# Salt the large (skewed) table
large_df = df_large.withColumn(
    "salted_key",
    F.concat(F.col("customer_id"), F.lit("_"), (F.rand() * SALT_FACTOR).cast("int"))
)

# Explode the small (lookup) table to match all salt values
small_df = df_small.withColumn("salt", F.array([F.lit(i) for i in range(SALT_FACTOR)]))
small_df = small_df.withColumn("salt_val", F.explode("salt"))
small_df = small_df.withColumn(
    "salted_key",
    F.concat(F.col("customer_id"), F.lit("_"), F.col("salt_val").cast("string"))
)

result = large_df.join(small_df, on="salted_key", how="left")
```

**2. Adaptive Query Execution (AQE) — enable and tune**
```python
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256m")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
# AQE will automatically split skewed partitions during the join
```

**3. Broadcast join (small table)**
```python
from pyspark.sql.functions import broadcast

# Force broadcast for tables < spark.sql.autoBroadcastJoinThreshold (default 10 MB)
result = large_df.join(broadcast(small_df), on="customer_id", how="left")

# Adjust threshold
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "50m")
```

---

## 5. Shuffle Optimization

Shuffles (wide transformations: `groupBy`, `join`, `distinct`, `repartition`) are the primary source of Spark performance issues.

### Minimize shuffles
```python
# Bad: two shuffles — groupBy + join
result = (
    df.groupBy("customer_id").agg(F.sum("amount").alias("total"))
    .join(df_customers, on="customer_id")
)

# Better: filter before groupBy to reduce data volume
result = (
    df.filter(F.col("status") == "completed")
    .groupBy("customer_id").agg(F.sum("amount").alias("total"))
    .join(broadcast(df_customers), on="customer_id")
)
```

### Tune shuffle partition count
```python
# AQE tunes this at runtime, but set a reasonable starting point
# Rule: target ~128 MB per shuffle partition
# total_shuffle_data / 128 MB = target shuffle partitions
spark.conf.set("spark.sql.shuffle.partitions", "400")  # start high; AQE reduces
```

### Shuffle spill detection
- Open Spark UI → Stages → select the shuffle stage → look for "Shuffle Spill (Disk)" > 0.
- **Cause:** executor memory insufficient for shuffle blocks.
- **Fix:** increase `spark.executor.memory`, reduce `spark.sql.shuffle.partitions`, or increase number of executors.

---

## 6. Open Table Formats

### Delta Lake
```python
# Write as Delta
(
    df.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .save("s3://bucket/warehouse/fact_orders_delta/")
)

# Upsert (MERGE) with Delta
from delta.tables import DeltaTable

delta_table = DeltaTable.forPath(spark, "s3://bucket/warehouse/fact_orders_delta/")
delta_table.alias("target").merge(
    df_updates.alias("src"),
    "target.order_id = src.order_id"
).whenMatchedUpdateAll() \
 .whenNotMatchedInsertAll() \
 .execute()

# Optimize (compact small files) + Z-ORDER (co-locate related data)
delta_table.optimize().zOrder("customer_id")

# Vacuum (remove old versions, default 7-day retention)
delta_table.vacuum(retentionHours=168)
```

### Apache Iceberg
```python
# Read/write Iceberg tables (Spark with Iceberg catalog)
spark.conf.set("spark.sql.catalog.my_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.my_catalog.type", "hive")

# Write
df.writeTo("my_catalog.warehouse.fact_orders").using("iceberg").append()

# Merge (Spark 3.3+)
spark.sql("""
    MERGE INTO my_catalog.warehouse.fact_orders AS target
    USING staging_orders AS src
    ON target.order_id = src.order_id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")

# Expire snapshots
spark.sql("CALL my_catalog.system.expire_snapshots('warehouse.fact_orders', TIMESTAMP '2024-01-01 00:00:00.000')")
```

### Choosing between Delta / Iceberg / Hudi
| Criterion | Delta Lake | Iceberg | Apache Hudi |
|-----------|-----------|---------|------------|
| Spark ecosystem fit | Best (Databricks native) | Good | Good |
| Multi-engine reads | Improving (UniForm) | Best (Spark, Trino, Flink, DuckDB) | Good |
| Streaming upserts | Good | Good | Best (designed for CDC) |
| Schema evolution | Good | Best | Good |
| Time travel | Yes (version-based) | Yes (snapshot-based) | Yes (commit-timeline) |
| Community/ecosystem | Large (Databricks) | Growing fast | Uber/cloud-native |

**Rule: prefer Delta Lake if on Databricks. Prefer Iceberg for multi-engine (Trino + Spark + Flink) setups. Prefer Hudi for CDC-heavy upsert workloads.**

---

## 7. Spark Structured Streaming (see also Playbook 06)

```python
# Read from Kafka, parse JSON, write to Delta
schema = StructType([
    StructField("order_id", StringType()),
    StructField("customer_id", StringType()),
    StructField("total_amount", DoubleType()),
    StructField("event_ts", TimestampType()),
])

raw_stream = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", BOOTSTRAP_SERVERS)
    .option("subscribe", "orders.order.placed.v1")
    .option("startingOffsets", "latest")
    .load()
)

parsed = raw_stream.select(
    from_json(col("value").cast("string"), schema).alias("d"),
    col("timestamp").alias("kafka_ts"),
).select("d.*", "kafka_ts")

# Watermark for late data tolerance
parsed = parsed.withWatermark("event_ts", "5 minutes")

# Write to Delta with checkpointing (idempotent)
query = (
    parsed.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "s3://bucket/checkpoints/orders_stream/")
    .trigger(processingTime="60 seconds")
    .toTable("raw.orders_placed")
)
query.awaitTermination()
```

### forEachBatch — idempotent MERGE sink
```python
def merge_batch(batch_df, batch_id):
    """Idempotent write: MERGE on order_id; safe on retry."""
    delta_table = DeltaTable.forName(spark, "warehouse.fact_orders")
    (
        delta_table.alias("target")
        .merge(batch_df.alias("src"), "target.order_id = src.order_id")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )

query = (
    parsed.writeStream
    .foreachBatch(merge_batch)
    .option("checkpointLocation", "s3://bucket/checkpoints/orders_merge/")
    .trigger(processingTime="60 seconds")
    .start()
)
```

---

## 8. PySpark Testing with pytest

### Unit testing transformations (no cluster required)
```python
# conftest.py
import pytest
from pyspark.sql import SparkSession

@pytest.fixture(scope="session")
def spark():
    return (
        SparkSession.builder
        .master("local[2]")
        .appName("test")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )

# test_transforms.py
from pyspark.sql import Row
from mypackage.transforms import apply_discount

def test_apply_discount(spark):
    input_df = spark.createDataFrame([
        Row(order_id="A", total_amount=100.0, is_vip=True),
        Row(order_id="B", total_amount=100.0, is_vip=False),
    ])
    result = apply_discount(input_df)
    rows = {r.order_id: r for r in result.collect()}
    assert rows["A"].discounted_amount == 90.0  # 10% VIP discount
    assert rows["B"].discounted_amount == 100.0
```

### Testing schema expectations
```python
def test_output_schema(spark):
    df = run_transform(spark, sample_input(spark))
    expected_columns = {"order_id", "customer_id", "total_amount", "order_date"}
    assert set(df.columns) == expected_columns, f"Unexpected schema: {df.columns}"
```

### Testing idempotency
```python
def test_idempotent_write(spark, tmp_path):
    df = sample_orders(spark)
    path = str(tmp_path / "fact_orders")

    write_orders(df, path)
    count_first = spark.read.parquet(path).count()

    # Re-run with same data — should not duplicate
    write_orders(df, path)
    count_second = spark.read.parquet(path).count()

    assert count_first == count_second, "Write is not idempotent — row count changed on re-run"
```

---

## 9. Airflow Integration

### SparkSubmitOperator (cluster mode)
```python
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

spark_job = SparkSubmitOperator(
    task_id="orders_daily_transform",
    application="jobs/orders_daily_transform.py",
    conn_id="spark_default",
    application_args=["--date", "{{ ds }}"],
    conf={
        "spark.sql.adaptive.enabled": "true",
        "spark.dynamicAllocation.enabled": "true",
    },
    executor_cores=4,
    executor_memory="8g",
    driver_memory="4g",
    retries=2,
    retry_delay=timedelta(minutes=5),
    retry_exponential_backoff=True,
    execution_timeout=timedelta(hours=2),
)
```

### Pattern: separate orchestration from logic
```
DAG file (Airflow): defines schedule, dependencies, parameters
  ↓
jobs/orders_daily_transform.py: PySpark job — takes --date arg, reads/writes data
  ↓
mypackage/transforms.py: Pure Python transform functions (testable without Spark)
```

**Rule:** Never put PySpark import or business logic inside the DAG file. The DAG only declares the job invocation with parameters.

---

## 10. Anti-Patterns

| Anti-Pattern | Impact | Fix |
|-------------|--------|-----|
| `df.collect()` on large dataset | OOM on driver | Use `df.write`, aggregations, or `df.limit(N).collect()` |
| UDF (Python) for simple expressions | Serialization overhead; no Catalyst optimization | Use built-in `pyspark.sql.functions` |
| `repartition(1)` before write | Single-threaded write, single output file | Use `coalesce(N)` with appropriate N |
| No checkpoint on streaming query | Job restart loses all progress; re-reads from start | Always set `checkpointLocation` |
| `cache()` everything | Disk/memory spill; caching what's used once | Cache only DataFrames used 2+ times in same job |
| Hardcoded `spark.sql.shuffle.partitions=200` | Wrong for large/small jobs without AQE | Enable AQE and set a high starting value |
| `explode()` without filter | Exponential row growth | Filter before explode; add limit in dev |
| Reading entire dataset to filter one day | Unnecessary I/O; ignores partitioning | Push date filter into `.filter()` before any wide transformation |
| Nested loops in Python calling Spark | Spark jobs inside Python loops = new DAG per iteration | Vectorize with window functions or single DataFrame operation |
| Schema inference on read | Schema changes break job silently | Always provide explicit schema on `read` |
