# Storage and Table Formats

Last verified: 2026-08-22. Recheck product-specific syntax against official documentation before implementation.

Use this reference for warehouses, lakes, lakehouses, object storage, physical design, and open table formats.

## Choose the storage role

Separate logical roles even when one platform implements several:

- System of record: authoritative operational state
- Replay layer: durable source-aligned history
- Curated analytical layer: cleaned, conformed data
- Serving layer: consumer-optimized tables, extracts, indexes, or APIs
- Archive: low-cost retained data with tested retrieval

Do not create layers by ritual. Each layer needs a distinct contract, retention or recovery purpose, or consumer boundary.

## Select a platform from access and change patterns

Use a warehouse when governed SQL analytics, concurrency, and managed operations dominate. Use object storage with an open table format when multi-engine access, large retained history, decoupled storage, or portable metadata matters. Use an operational database or serving index for low-latency point access and updates. Hybrid designs need explicit ownership of each copy and freshness path.

Evaluate transaction guarantees, schema evolution, time travel, concurrency, optimizer behavior, maintenance, catalog integration, encryption, regional availability, egress, and exit path.

## Design physical layout from workload evidence

- Partition when pruning aligns with common bounded predicates and partitions will not be excessively small.
- Cluster, sort, or index when selective filters or joins benefit and maintenance cost is justified.
- Avoid high-cardinality partition keys that create tiny partitions or metadata pressure.
- Do not prescribe partitioning merely from table size; some engines use automatic micro-partitioning or indexes more effectively.
- Validate with query plans, bytes scanned, files touched, latency distribution, and maintenance cost.

Target file sizes from engine and object-store behavior. For distributed analytic reads, 128–512 MiB is a reasonable initial range, not a universal law. Measure task startup, scan parallelism, compaction cost, and mutation pattern.

## Preserve table correctness

Define the write model:

- Append-only immutable facts with uniqueness enforcement or downstream deduplication
- Partition replacement for bounded recalculation
- Upsert/version-aware application for mutable entities
- Snapshot replacement for small reference datasets
- Bitemporal or SCD history when effective and system time both matter

Choose a commit protocol that prevents readers from seeing partial output. On object storage, write data files and then atomically publish table metadata or a manifest. Never rely on directory listing order as a transaction.

## Use open table formats deliberately

[Apache Iceberg](https://iceberg.apache.org/spec/), [Delta Lake](https://github.com/delta-io/delta), and [Apache Hudi](https://hudi.apache.org/docs/overview/) all add table metadata and transactional behavior, but differ in engine ecosystem, mutation path, indexing, services, and operational model.

Before choosing, prove:

- Required engines can read and write the selected features
- Catalog and concurrency semantics match deployment
- Schema and partition evolution are supported by every critical consumer
- Compaction, snapshot expiration, orphan cleanup, and restore are owned
- Lock-in and conversion costs are acceptable

Avoid using product-specific optimization features in a contract that claims cross-engine portability unless consumers explicitly accept the dependency.

## Manage retention and recovery

Distinguish business retention, legal hold, time-travel retention, backup retention, and raw replay retention. Longer time travel is not a backup. Test restore from independent copies where the RPO/RTO requires it.

Deletion must reach derived tables, indexes, caches, extracts, backups according to policy. Record exceptions such as immutable legal archives.

## Control storage cost

Model logical bytes, compression, replicas, snapshots, metadata, time travel, failed writes, and egress. Apply lifecycle tiers only after measuring retrieval frequency and restore time. Review unused columns, duplicate copies, stale snapshots, and small files before purchasing more capacity.

## Verify physical design

Use representative queries and peak concurrency. Capture plans and bytes/files scanned before and after the change. Test writes, concurrent readers, schema changes, compaction, rollback/time travel, and restore. A faster happy-path query is insufficient if maintenance or recovery becomes unsafe.
