# ML and AI Data Systems

Last verified: 2026-08-22. Verify model/provider and vector-store APIs before implementation.

Use this reference for feature pipelines, training datasets, embeddings, vector indexes, and RAG ingestion. Model training and inference architecture are adjacent concerns; focus here on data correctness and operations.

## Contract features and labels

Define feature name, entity key, event/effective time, source, transformation version, type, null/default semantics, freshness, owner, allowed uses, and online/offline availability. Define labels with observation and outcome windows.

Build training datasets with point-in-time correct joins. For each training example, use only feature values available at prediction time. Test future-data leakage and late corrections explicitly.

## Prevent training/serving skew

Prefer one transformation definition or generated equivalents for offline and online paths. Compare values by entity/time/version in continuous tests. Record code, data, feature, and model versions for reproduction.

Monitor feature availability, freshness, null/default rate, distribution, drift, and online/offline mismatch. Distinguish feature drift, label drift, and concept drift because remediation differs.

## Build reproducible training data

Snapshot or version source data, transformations, joins, filters, labels, and exclusions. Record lineage and contract versions. A notebook query without immutable inputs is not a reproducible dataset.

Apply access, consent/purpose, retention, and deletion policy to snapshots and experiment artifacts. Training copies are not exempt from subject deletion or licensing restrictions.

## Engineer embedding pipelines

Contract:

- Source document/content identity and version
- Parser and chunking strategy/version
- Embedding model/provider/version and vector dimension
- Normalization and distance metric
- Language/content policy
- Metadata filters and access labels
- Deduplication/content hash
- Generated timestamp and source lineage
- Retention, deletion, and re-embedding policy

Use content plus transformation-version identity to make ingestion idempotent. A model or chunker change creates a new index version; build and validate it separately before switching readers.

## Select vector serving from workload

Compare corpus/vector count, dimensions, update/delete rate, query rate, p95 latency, recall target, metadata filtering, hybrid search, multi-tenancy, replication, regional needs, backup/restore, access control, and total cost.

Benchmark with representative queries and labeled relevance. Vendor recall claims or synthetic random vectors do not prove application quality.

## Design RAG ingestion and retrieval

Preserve raw source, parsed representation, chunks, embeddings, and index publication as versioned stages when replay is valuable. Enforce source permissions at retrieval, not only ingestion.

Validate parsing coverage, chunk boundaries, duplicate rate, metadata completeness, index counts, retrieval recall/precision, freshness, citation/source identity, and deletion propagation. Track unanswerable and access-denied behavior.

Hybrid lexical/vector retrieval and reranking can improve quality, but add them only when evaluation shows value. Keep a versioned evaluation set and compare changes before rollout.

## Operate changes safely

Use shadow indexes or namespaces, backfill with throttling, reconcile document/chunk/vector counts, run retrieval evaluation, canary consumers, and retain switchback until the new version is stable. Avoid in-place full re-embedding without recoverable prior state.

## Review gate

Require point-in-time correctness, transformation/version lineage, online/offline consistency, representative evaluation, access propagation, sensitive-data policy, deletion across derived artifacts, capacity/cost estimates, safe reindex/backfill, and rollback.
