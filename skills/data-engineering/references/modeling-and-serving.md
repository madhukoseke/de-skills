# Modeling and Serving

Use this reference for dimensional modeling, Data Vault, data products, semantic layers, APIs, extracts, reverse ETL, and consumer-facing datasets.

## Begin with decisions and grain

List the questions, decisions, or service operations the model must support. State the grain in one sentence before listing columns. Define keys, measures, dimensions, time semantics, update behavior, and expected access paths.

A model is correct only relative to its consumers. Do not choose Kimball, Data Vault, one-big-table, or medallion as an organizational identity.

## Select a modeling approach

| Approach | Prefer when | Watch for |
|---|---|---|
| Dimensional/star | Stable analytical processes and BI aggregation | Mixed grain, incorrect additive measures, SCD ambiguity |
| Normalized/core | Shared operational or integration semantics | Consumer joins and slow delivery of usable marts |
| Data Vault | Many changing sources, audit/history, parallel loading | Complexity, query usability, hash consistency |
| Wide/OBT | One dominant access pattern and cheap recomputation | Duplication, update anomalies, inconsistent metrics |
| Data product | Domain ownership and explicit consumer contracts | Duplicated platform concerns, weak interoperability |

Use layered models only when each layer changes responsibility, quality, semantics, ownership, access, or performance.

## Model dimensional data carefully

- Declare fact grain and enforce it with a candidate key test.
- Separate additive, semi-additive, and non-additive measures.
- Use conformed dimensions only when business meaning is truly shared.
- Choose SCD behavior per attribute, not per table by habit.
- Handle unknown, late-arriving, and inferred members explicitly.
- Use bridge tables for genuine many-to-many relationships and define weighting/allocation semantics.
- Preserve event/effective time separately from warehouse load time.

Surrogate keys help warehouse history and joins but do not replace source business keys or source-system identity.

## Model history and corrections

For SCD Type 2, define business key, effective start/end, current marker, version ordering, overlap prevention, late corrections, deletes, and point-in-time join behavior. A two-step expire/insert is unsafe without a transaction or equivalent atomic publication.

Use bitemporal modeling when both real-world effective history and system knowledge history are required. Do not approximate bitemporality with one timestamp pair.

## Establish metric semantics

Define each governed metric with owner, business definition, base measure, dimensions, filters, time grain/timezone, aggregation behavior, late-data policy, version, and tests. Keep metric definitions in one governed semantic layer or generate downstream forms from one canonical definition.

Validate totals across BI, notebooks, APIs, and ML features. A semantic layer that only one tool can interpret is an integration boundary and should be treated as such.

## Design serving paths

Choose a serving form from query pattern and SLO:

- Warehouse/lakehouse table for flexible analytical scans
- Aggregate/materialized view for repeated bounded queries
- Extract/cache for dashboards with controlled staleness
- Search/vector index for retrieval patterns
- Operational database/API for low-latency point access and mutations
- Reverse ETL for controlled synchronization into operational tools

Every derived serving copy needs an owner, freshness path, reconciliation, access policy, deletion propagation, and retirement process.

## Treat data products as operational products

Publish discoverable contracts, examples, SLOs, ownership, lineage, support channel, access request, cost attribution, compatibility, and deprecation policy. Measure adoption and consumer outcomes, not merely table count.

## Review gate

Require consumer use cases, explicit grain and keys, time semantics, history/correction behavior, measure additivity, contract and compatibility, access patterns, physical design evidence, reconciliation, and deprecation ownership.
