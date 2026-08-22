# Transformation and Compute

Last verified: 2026-08-22. Verify framework and dialect syntax against official documentation before shipping.

Use this reference for SQL, Python, dbt, Spark, and batch transformation code.

## Establish the transformation contract

Define input contracts, output grain, keys, semantics, time behavior, update model, expected volume, and consumers before optimizing code. Keep orchestration thin: it coordinates independently testable transformation units and should not hide business rules inside callbacks or DAG construction.

## Write reliable SQL

- State the dialect and target engine.
- Select columns explicitly at durable boundaries.
- Make grain visible through keys, grouping, and tests.
- Define null, duplicate, late-arriving, and divide-by-zero behavior.
- Use deterministic tie-breakers in windows and deduplication.
- Bound incremental reads by source semantics and include a correction window when updates arrive late.
- Choose append, key-constrained insert, partition replacement, snapshot replacement, or upsert from the data model; `MERGE` is not mandatory.
- Inspect `EXPLAIN` or equivalent for scans, pruning, join strategy, exchange/shuffle, spills, estimates, and repeated work.

Correlated subqueries are not automatically quadratic, and CTEs are not automatically materialized. Validate the optimizer plan rather than repeating folklore.

## Package Python as production code

- Put source in importable modules with explicit dependencies and a lock file.
- Separate pure transformations from I/O, configuration, and orchestration adapters.
- Use typed records or validated schemas at boundaries.
- Stream or chunk large inputs; avoid loading unknown-size datasets into memory.
- Pass secrets through the runtime’s secret mechanism, never source or default config.
- Make clocks, randomness, filesystem, and external clients injectable for tests.
- Emit structured errors that distinguish retryable infrastructure failure from invalid data or code defects.

Use unit tests for pure logic, contract tests for boundaries, integration tests for real adapters, and a small end-to-end fixture for packaging and entrypoint behavior.

## Use dbt where SQL models are the product

Read current behavior from [dbt documentation](https://docs.getdbt.com/docs/introduction). Use `source()` and `ref()` for lineage, model contracts at published boundaries, tests tied to consumer risk, and incremental strategies that cover updates and schema change.

Do not split models solely to satisfy a layer naming convention. Split when grain, responsibility, materialization, ownership, access, or reuse changes. Keep macros focused and test logic that can alter many models.

For incremental models, test first run, no-change rerun, updates, late data, duplicate keys, schema addition, full refresh, and interruption/retry.

## Use Spark for distributed work that needs it

Read current behavior from [Apache Spark documentation](https://spark.apache.org/docs/latest/). Prefer built-in expressions over row-by-row Python UDFs, enable adaptive execution when supported, and inspect stage/task metrics before tuning.

Avoid `collect()` on unbounded data and `repartition(1)` as a publishing strategy. Choose partition count from input size, shuffle size, target file size, cores, skew, and downstream parallelism.

Handle skew by measuring key distribution and task tails. Options include pre-aggregation, broadcast of genuinely small inputs, adaptive skew splitting, salting, or data-model changes. Each has correctness and maintenance costs.

For distributed writes, define commit behavior, retry semantics, target partition replacement or upsert rules, and file maintenance.

## Decide between warehouse SQL and distributed compute

Prefer warehouse SQL when data already resides there, transformations are relational, governance is integrated, and concurrency matters. Prefer distributed compute for non-SQL libraries, large file-oriented workloads, custom stateful processing, or when storage/compute separation and engine portability justify operations.

Compare total scanned/shuffled bytes, startup, elasticity, developer feedback, operational ownership, and data movement—not only list price.

## Review gate

Require clear grain and keys, deterministic time logic, explicit update semantics, safe replay, bounded memory, secrets isolation, tests for change and failure, observable row/byte counts, and evidence from the target engine’s plan or runtime metrics when performance is claimed.
