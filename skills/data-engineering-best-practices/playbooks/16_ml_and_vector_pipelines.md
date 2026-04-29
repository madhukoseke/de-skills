---
title: "ML & Vector Pipelines"
description: "Feature stores, training-serving skew, vector DB selection, RAG ingestion, embedding pipeline observability"
tags: [ml, feature-store, vector-database, embeddings, rag, training-serving-skew, drift, feast, tecton, pinecone, weaviate, pgvector, qdrant]
related_templates:
  - ../templates/data_contract.yaml
  - ../templates/data_quality_report.md
---

# Playbook 16 — ML & Vector Pipelines

> **Guiding principles:** Schema is a contract (W004). Idempotency first (W001). Test at every layer (W011).
> ML pipelines and embedding/RAG pipelines are still data pipelines. Apply every other principle in this skill before reaching for ML-specific patterns. The places where ML pipelines are different are predictable: training-serving skew, drift, embedding versioning.

This playbook covers the data-engineering side of ML and AI workloads — feature stores, vector indexing, RAG ingestion. Model training, hyperparameter tuning, and serving infrastructure are out of scope; they belong in MLOps.

---

## 1. The two ML data planes

Every ML pipeline has two planes; mixing them is the source of most production failures.

| Plane | Purpose | Latency | Storage |
|-------|---------|---------|---------|
| **Offline (training)** | Reproducible features for model training and back-testing | Minutes-hours | Warehouse, lakehouse, parquet |
| **Online (serving)** | Low-latency features for real-time inference | <100 ms | Key-value store, in-memory cache, low-latency DB |

A feature store is the abstraction that keeps these two planes consistent — same feature definition, two materializations, guaranteed agreement.

```
[ Source events ]
        │
        ▼
   ┌─────────────┐
   │  Feature    │── offline materialization ──▶ [ Warehouse / parquet ] ──▶ Training
   │  Definition │
   │  (Feast,    │── online materialization ──▶ [ KV store: Redis /     ] ──▶ Inference
   │  Tecton)    │                                Cassandra / DynamoDB ]
   └─────────────┘
```

**Rule:** the **same code** that computes a feature for training must compute it for serving. If you have one Spark job for training and one Java function for serving, you have built training-serving skew on purpose.

---

## 2. Feature stores

### When you need one

You need a feature store when **two or more models share at least one feature** AND **at least one model serves online**. With one offline-only model, a feature store is overkill — a parquet table on the warehouse with strict naming + version is enough.

### Vendor-neutral comparison

| Capability | Feast (OSS) | Tecton | Databricks Feature Store | Vertex AI Feature Store | SageMaker Feature Store |
|------------|:-----------:|:------:|:------------------------:|:-----------------------:|:-----------------------:|
| Offline-only mode | ✅ | ❌ | ✅ | ✅ | ✅ |
| Online store options | Multiple (Redis, DDB, BT, ...) | Managed | UC + DB Online Store | Bigtable | DynamoDB / Aurora |
| Point-in-time joins | ✅ | ✅ | ✅ | ✅ | ✅ |
| Self-host | ✅ | ❌ | ❌ (managed) | ❌ (managed) | ❌ (managed) |
| dbt integration | ✅ | ✅ | ✅ (UC native) | partial | partial |
| Streaming ingest | basic | ✅ | ✅ | ✅ | ✅ |

### Feature definition (Feast example)

```python
from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float32, Int64

customer = Entity(name="customer_id", join_keys=["customer_id"])

source = FileSource(
    name="customer_orders",
    path="warehouse/marts/feature_customer_orders.parquet",
    timestamp_field="event_timestamp",
)

customer_orders_30d = FeatureView(
    name="customer_orders_30d",
    entities=[customer],
    ttl=timedelta(days=90),
    schema=[
        Field(name="orders_30d", dtype=Int64),
        Field(name="gross_revenue_30d", dtype=Float32),
        Field(name="last_order_days_ago", dtype=Int64),
    ],
    source=source,
    online=True,
    tags={"team": "growth", "owner": "ml-platform"},
)
```

**Feature contract rules:**
- Every feature carries `team`, `owner`, `cost_center` tags (W005).
- TTL set explicitly — features without TTL leak across drift events forever.
- Feature name pattern: `<entity>_<measure>_<window>` (e.g., `customer_orders_30d`). Ad-hoc naming is the source of many "I thought this was the average" bugs.
- Every feature has a backing **point-in-time-correct** SQL (no leakage from the future when joining for training labels).

### Point-in-time joins (the killer feature)

```python
# CORRECT: point-in-time join — for each (customer_id, label_event_time),
# fetch features as they were at label_event_time.
training_df = store.get_historical_features(
    entity_df=labels_df,                 # has: customer_id, label_event_time, did_churn
    features=[
        "customer_orders_30d:orders_30d",
        "customer_orders_30d:gross_revenue_30d",
    ],
).to_df()

# WRONG: naive join — if a label is from 2026-03-01 but features are from 2026-04-29,
# the model trains on data that didn't exist at prediction time. Performance looks
# great in offline eval, collapses in production.
```

---

## 3. Training-serving skew

The single most expensive ML data bug. You catch it in production the day after launch, when you can't explain why the offline AUC was 0.92 and the live AUC is 0.71.

### Detection

```python
# Run every day in production: compare live-served features to offline-recomputed features
# for the same (entity_id, timestamp). Both should be byte-identical.
discrepancies = compare_feature_distributions(
    live_features = pull_online_logs(date='2026-04-29'),
    offline_recompute = pull_warehouse_features(date='2026-04-29'),
)

# Alert when any feature has > 0.1% mismatch
```

### Common skew sources

| Source | Symptom | Fix |
|--------|---------|-----|
| Different code paths offline vs online | Mean / variance drifts visibly between planes | Single feature definition; feature store materializes both |
| Offline uses future data (leakage) | Model great offline, fails online | Point-in-time joins; never `t.created_at > prediction_t` in feature SQL |
| Timezone mismatch | Features at midnight boundary mis-bucketed | All timestamps UTC end-to-end; assert at ingest |
| Type coercion (FLOAT vs DOUBLE) | Last-bit differences amplified by hashing | Pin schemas with `data_type` in the feature contract (W004) |
| Categorical encoding drift | New value in serving missing from training | One-hot on training set; reserve `_OOV_` token |
| Feature TTL expired silently online | Stale serving feature; training still up to date | Monitor cache hit rate per feature; alert on freshness gap (Playbook 13 §4) |
| Different default for missing values | NULL → 0 offline; NULL → -1 online | Document defaults in the feature definition; assert in CI |

---

## 4. Drift monitoring

Two distinct drifts matter:

### Feature drift (input distribution shift)

```python
# Population Stability Index (PSI) — flag when PSI > 0.2
def psi(reference: list[float], current: list[float], buckets: int = 10) -> float:
    edges = np.percentile(reference, np.linspace(0, 100, buckets + 1))
    ref_pct = np.histogram(reference, edges)[0] / len(reference)
    cur_pct = np.histogram(current, edges)[0] / len(current)
    ref_pct = np.where(ref_pct == 0, 1e-6, ref_pct)
    cur_pct = np.where(cur_pct == 0, 1e-6, cur_pct)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
```

### Label drift (target distribution shift)

`P(y)` changes — e.g., conversion rate dropped from 8% to 2% after a product launch. Same model, lower performance.

### Concept drift (input-output relationship shift)

`P(y | x)` changes — same features now predict different outcomes. The hardest to detect; usually requires offline back-testing with newer labels.

**Rule:** all three drifts emit metrics into the same observability backend as Playbook 13 (W007). Drift alerts feed the model-retrain pipeline, never directly to humans without auto-action.

---

## 5. Vector databases & embedding pipelines

### When to use a vector DB vs. SQL `vector_search`

```
Embedding count:
  < 1M vectors    → pgvector / DuckDB vss / SQLite vss / managed warehouse vector type
  1M – 100M       → pgvector with IVFFLAT / HNSW indexes; Qdrant; Weaviate self-host
  100M – 10B      → Pinecone managed; Milvus self-host; Vespa
  > 10B           → Custom (FAISS sharded; Vespa; Vald)

Latency requirement:
  > 200 ms acceptable     → warehouse-native vector_search (Snowflake / BQ / Databricks)
  20 – 200 ms             → pgvector / Qdrant / Weaviate
  < 20 ms                 → Pinecone / managed Milvus / in-memory FAISS
```

### Index choice

| Index | Build cost | Query cost | Recall | Use when |
|-------|------------|------------|--------|----------|
| **Flat (brute-force)** | None | O(N·d) | 100% | <100K vectors; recall matters more than latency |
| **IVF / IVFFLAT** | Cheap | O(√N·d) typical | ~95% | 1M-100M; tunable nprobe |
| **HNSW** | Medium | O(log N) | ~98% | 1M-1B; best general-purpose graph index |
| **DiskANN** | Expensive | O(log N) | ~98% | >100M, memory-constrained; SSD-resident |
| **Product Quantization (PQ)** | Cheap | O(√N·d) | ~80–90% | When memory budget dominates |

**Rule:** measure recall on a held-out query set with known nearest neighbors **before** picking an index. The default in most managed services is HNSW with reasonable recall — verify on your own data, don't assume.

### Hybrid search (lexical + dense + sparse)

Pure-dense retrieval misses exact-match queries (proper nouns, IDs, codes). Modern stacks combine three signals:

```
query
  ├──▶ dense (embedding) ──▶ top-K_d
  ├──▶ sparse (BM25/SPLADE) ─▶ top-K_s
  └──▶ lexical (filter)    ──▶ scope
                                 │
                                 ▼
                       Reciprocal Rank Fusion (RRF)
                              or learned reranker
                                 │
                                 ▼
                              top-K final
```

```python
def rrf(*ranked_lists, k: int = 60):
    """Reciprocal Rank Fusion — robust default for combining ranked lists."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])
```

---

## 6. Embedding pipelines

### The embedding contract

Every embedding column or vector index is a **versioned data contract**. The vector dimension, the model identity, the normalization, and the source text definition are all part of it.

```yaml
# extension to data_contract.yaml for vector tables
embedding:
  model_family: ""             # e.g., generic family name; the specific provider/model is host config
  model_version: ""            # e.g., "v3.2" — pin in production
  dimension: 1024              # vector dimension; must match index config
  normalization: "l2"          # l2 | none | mean
  pooling: "mean"              # mean | cls | last_token (where applicable)
  text_template: |             # exactly how source text is rendered before embedding
    Title: {title}
    Body:  {body}
    Tags:  {tags|join(', ')}
  chunking:
    strategy: "sliding"        # fixed | sliding | semantic | by_section
    size_tokens: 512
    overlap_tokens: 64
  reembed_strategy: "on_model_or_text_change"
  reembed_sla_hours: 168
```

**Versioning rule:** any change to `model_version`, `dimension`, `text_template`, or `chunking` is a breaking change. Bump the index version (`embeddings_v1` → `embeddings_v2`) and dual-write until consumers migrate. Never silently re-embed in place — recall metrics regress invisibly.

### RAG ingestion pipeline (standard pattern)

```
[ Source documents ] ──▶ [ Parse & chunk ] ──▶ [ Embed ] ──▶ [ Upsert vector + metadata ]
                              │                                       │
                              │                                       ▼
                              │                              [ Vector DB / index ]
                              ▼                                       │
                       [ Document store ]                             ▼
                       (raw text by id)                       [ At query time:
                                                              dense + sparse + filter
                                                              + rerank → grounded LLM ]
```

### Idempotency in re-embedding (W001)

```python
# Compute a content hash; only embed if hash differs from what's stored
def upsert_chunks(chunks: list[Chunk], db: VectorDB) -> None:
    for chunk in chunks:
        text_hash = sha256(chunk.text.encode()).hexdigest()
        existing = db.get_metadata(chunk.id)
        if existing and existing.get("text_hash") == text_hash \
           and existing.get("model_version") == CURRENT_MODEL_VERSION:
            continue                         # idempotent skip
        embedding = embed_one(chunk.text)
        db.upsert(
            id=chunk.id,
            vector=embedding,
            metadata={
                **chunk.metadata,
                "text_hash": text_hash,
                "model_version": CURRENT_MODEL_VERSION,
                "embedded_at": iso_now(),
            },
        )
```

### Deduplication

Cheap dedup (post-chunk, pre-embed):

```python
# MinHash / LSH for near-duplicate detection
from datasketch import MinHash, MinHashLSH

lsh = MinHashLSH(threshold=0.85, num_perm=128)
for chunk in chunks:
    mh = MinHash(num_perm=128)
    for token in tokenize(chunk.text):
        mh.update(token.encode())
    if lsh.query(mh):
        chunk.is_duplicate = True
    else:
        lsh.insert(chunk.id, mh)
```

Without dedup, you pay full embedding cost on duplicate copy/pasted boilerplate, and your retriever returns the same passage 5× — a poor user experience.

---

## 7. RAG observability

```python
# Per-query metrics (every query, every environment)
emit_gauge("rag.retrieval.latency_ms",   t_retrieve_ms,   tags=[index, mode])
emit_gauge("rag.rerank.latency_ms",      t_rerank_ms,     tags=[reranker])
emit_gauge("rag.retrieval.recall_at_k",  recall_at_k,     tags=[index])  # offline eval set
emit_gauge("rag.retrieval.empty_result", 1 if k == 0 else 0, tags=[index])
emit_gauge("rag.context.token_count",    context_tokens,  tags=[index])
emit_counter("rag.fallback_triggered",   1 if used_fallback else 0)
```

### Offline eval harness

Treat retrieval quality like data quality (Playbook 05). Maintain an eval set of (query, expected_doc_ids) pairs and run nightly:

```python
# Recall@K — fraction of golden answers in the top-K retrieval
def recall_at_k(retrieved: list[str], expected: set[str], k: int = 10) -> float:
    return len(set(retrieved[:k]) & expected) / max(len(expected), 1)

# Mean Reciprocal Rank — sensitive to position of first correct hit
def mrr(retrieved: list[str], expected: set[str]) -> float:
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in expected:
            return 1.0 / rank
    return 0.0
```

Alert when recall@10 drops by >5 points week-over-week — retrieval quality regresses on schema or chunking changes you didn't catch in CI.

---

## 8. Right-to-erasure for embeddings

Per Playbook 14 §6, vector indexes are erasure-relevant. Strategy:

1. Deletion request comes in with `subject_id`.
2. Look up the affected `chunk_id`s in the document store via `metadata.subject_id`.
3. `db.delete(ids=affected_chunk_ids)`.
4. Trigger an index re-build (most vector DBs need this for HNSW/IVF; Pinecone reclaims slots automatically).
5. Verify by query: a search for content from the deleted document must no longer return it.

**Rule:** the SLA for embedding erasure is typically longer than warehouse erasure. Document the actual hours in the data contract `subject_rights.erasure_sla_hours` and test it (Playbook 14 §6 erasure runbook).

---

## 9. Cost tuning for ML pipelines

Embedding compute and vector storage dominate AI-pipeline costs. The big levers:

| Lever | Typical impact |
|-------|----------------|
| Smaller embedding model on cold data | 5-10× cost reduction; rebuild on hot data with larger model |
| Quantize vectors (int8 / fp16) | 2-4× storage; ~1-2 point recall hit |
| Async batching of embed requests | 3-10× throughput; lower per-vector cost |
| Dedup before embed (§6) | 20-40% embedding-volume reduction on web-scale data |
| Cache embeddings by content_hash | 100% savings on repeated re-embeds (W001) |
| Drop low-information chunks | Many doc collections have 30% boilerplate; chunk filter pre-embed |
| Semantic chunking over fixed-size | Fewer chunks; better retrieval per dollar |

---

## 10. Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Different code computes features offline vs online | Training-serving skew baked in | Single feature definition in feature store |
| `MAX(updated_at)` in feature SQL | Future leakage at training time | Point-in-time joins; explicit asof timestamp |
| No TTL on online features | Stale-forever serving values | Set TTL per feature; alert on freshness gap |
| Re-embed in place when model changes | Recall regresses silently; no rollback | Versioned indexes (`embeddings_v1` / `v2`); dual-write; cut over after eval |
| HNSW chosen because "everyone uses it" | Wrong index for the data | Measure recall on held-out query set; pick by data |
| No dedup before embedding | Pay 2-5× embedding cost on copy-pasted boilerplate | MinHash / LSH dedup; chunk-content hashing |
| RAG returns empty result, system falls back silently | Users see hallucinations on missing context | Track empty-result rate; fail loudly when above SLO (W003) |
| One vector index for all tenants | RBAC bypass; one tenant sees another's data | Namespace per tenant; or per-tenant filter at query time (Playbook 14 §4) |
| Drift dashboards but no auto-retrain | Model rots between manual reviews | Drift signals trigger retrain pipeline; humans approve, not detect |
| Embedding pipeline lacks `principlesCited` linkage in lineage | Can't reason about contract changes downstream | Emit OpenLineage with `subject_id` namespace; reference principle IDs in runbook |
| Production prompts hardcoded in app code | Not versioned; A/B testing impossible; can't roll back | Prompts in version control with hash; emit prompt-hash in OpenLineage events |

---

## Quick Reference Checklist: ML & Vector Pipelines

Before any feature, model, or vector index reaches production:

- [ ] Single feature definition; offline and online materialization from the same source (W001)
- [ ] Point-in-time joins for training; no future leakage
- [ ] Feature contract: `team`, `owner`, `cost_center`, TTL, schema (W004)
- [ ] Training-serving skew monitor running daily; threshold defined
- [ ] Drift monitoring: feature, label, concept — with PSI / KS thresholds (W007)
- [ ] Vector index choice justified by recall measurement on held-out query set
- [ ] Embedding contract: `model_family`, `model_version`, `dimension`, `text_template`, `chunking` — pinned and versioned
- [ ] Re-embed flow is idempotent (`text_hash` + `model_version` skip) (W001)
- [ ] Dedup step before embedding for any web-scale ingest
- [ ] RAG observability: retrieval latency, recall@K, empty-result rate, fallback counter
- [ ] Right-to-erasure tested on embeddings; SLA documented in data contract
- [ ] Cost levers reviewed: dedup, quantization, batch size, smaller model on cold data

See the data contract template at [`../templates/data_contract.yaml`](../templates/data_contract.yaml) and DQ pattern at [`../templates/data_quality_report.md`](../templates/data_quality_report.md).
