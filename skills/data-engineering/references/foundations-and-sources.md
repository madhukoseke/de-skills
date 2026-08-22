# Foundations and Sources

Last reviewed: 2026-08-22. Review at least every six months and before major releases.

Use this reference when interpreting principles, resolving conflicting guidance, or contributing canonical knowledge. Do not load it for ordinary implementation unless provenance matters.

## Source policy

- Synthesize principles and decision methods; do not copy substantial copyrighted prose, diagrams, or examples.
- Prefer official standards, specifications, project documentation, and primary research for technical claims.
- Separate durable principles from version-specific product syntax.
- Record the edition/version and review date for sources that can change.
- Treat books as intellectual foundations, not normative specifications.
- Cite the authoritative source in references that rely on a standard or product capability.
- Validate consequential current claims before use; do not trust the review date alone.

## Foundational books and bodies of knowledge

| Source | Edition/status | Influence on this skill |
|---|---|---|
| Joe Reis and Matt Housley, *Fundamentals of Data Engineering* | O’Reilly, 2022 | End-to-end lifecycle; generation, ingestion, storage, transformation, serving, and cross-cutting concerns |
| Martin Kleppmann and Chris Riccomini, *Designing Data-Intensive Applications* | 2nd ed., O’Reilly, 2026 | Reliability, scalability, maintainability, data models, replication, partitioning, transactions, distributed systems, and streaming trade-offs |
| [Ralph Kimball and Margy Ross, *The Data Warehouse Toolkit*](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/books/data-warehouse-dw-toolkit/) | 3rd ed. | Dimensional modeling, grain, facts, dimensions, slowly changing dimensions, and business process focus |
| Tyler Akidau, Slava Chernyak, and Reuven Lax, *Streaming Systems* | O’Reilly, 2018 | Event time, watermarks, triggers, state, and correctness in stream processing |
| Alex Petrov, *Database Internals* | O’Reilly, 2019 | Storage engines, indexes, distributed database mechanisms, and failure trade-offs |
| [Google, *Site Reliability Engineering* and *The Site Reliability Workbook*](https://sre.google/workbook/part-I-foundations/) | Online books | SLOs, error budgets, monitoring, incident response, canarying, capacity, and pipeline operations |
| [DAMA International, DAMA-DMBOK](https://dama.org/about-dama/what-is-data-management/) | 2nd ed. revised; 3.0 evolving | Governance, architecture, modeling, storage/operations, security, integration, metadata, master/reference data, warehousing, and quality |

These sources can disagree or address different scopes. Resolve conflicts from consumer requirements, system semantics, evidence, risk, and current authoritative specifications.

## Open standards and primary specifications

| Standard | Version/status used | Purpose |
|---|---|---|
| [Agent Skills](https://agentskills.io/specification) | Current at review date | Skill package, metadata, references, assets, scripts, progressive disclosure |
| [Open Data Contract Standard](https://github.com/bitol-io/open-data-contract-standard) | 3.1.0 | Interoperable data contract structure |
| [OpenLineage spec](https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md?plain=1) | Current at review date | Job, run, and dataset lineage events/facets |
| [OpenTelemetry](https://opentelemetry.io/docs/specs/) | Current at review date | Metrics, logs, traces, context, and telemetry transport |
| [Apache Iceberg specification](https://iceberg.apache.org/spec/) | Current at review date | Open analytical table metadata and transaction semantics |
| [Apache Avro specification](https://avro.apache.org/docs/current/specification/) | Current at review date | Schema-based serialization and evolution concepts |

## Interpretation rules

1. Start with business and consumer requirements.
2. Use distributed-systems theory to expose failure and consistency trade-offs.
3. Use data-management disciplines to cover ownership, meaning, security, lifecycle, and quality.
4. Use SRE practices to make the system measurable, recoverable, and operable.
5. Use current product documentation only after the architecture decision narrows the implementation.
6. Verify with tests, plans, runtime evidence, and recovery exercises.

## Contribution evidence

For a new or changed rule, provide at least one of:

- An authoritative standard or official documentation
- A reproducible test or benchmark
- A public incident/postmortem or primary research result
- A clearly labeled, reviewed practitioner heuristic with scope and counterexamples

Reject rules framed as universal when known valid counterexamples exist. Replace them with a decision rule, required evidence, and conditions under which the advice changes.

## Licensing boundary

Repository-authored summaries, templates, and code are Apache-2.0-licensed. External works retain their own copyrights and licenses. Links and short factual references do not import external text or code into this repository. Before vendoring a schema or example, verify license compatibility, preserve required notices, and record provenance.
