# ADR 0001: one flagship data-engineering skill

- Status: accepted
- Date: 2026-08-22

## Decision

Keep `de-skills` as the repository root and ship one installable
`skills/data-engineering` package. Route intent through six workflows and load
domain references progressively. Provider integrations remain outside the
canonical package except for thin adapter metadata.

## Prior playbook audit

| v5 playbook | Disposition | v6 authority |
| --- | --- | --- |
| Pipeline design | Rewrite | architecture, ingestion, storage references |
| Airflow reliability | Relocate | orchestration and reliability references |
| PR review checklist | Rewrite | `REVIEW` workflow and code-review asset |
| dbt patterns | Relocate | transformation reference |
| Data quality | Rewrite | contracts, quality, and testing reference |
| Streaming architecture | Rewrite | streaming and distributed systems reference |
| SQL patterns | Rewrite | transformation and compute reference |
| Spark patterns | Relocate | transformation and compute reference |
| Data modeling | Rewrite | modeling and serving reference |
| Orchestration patterns | Rewrite | orchestration and delivery reference |
| Testing strategies | Rewrite | contracts, quality, and testing reference |
| Schema management | Rewrite | contracts, quality, and testing reference |
| Lineage and observability | Rewrite | reliability and operations reference |
| Governance and PII | Rewrite | governance, security, and lifecycle reference |
| Cost optimization | Rewrite | platform engineering and FinOps reference |
| ML and vector pipelines | Rewrite | ML and AI data systems reference |

Repeated universal prescriptions were removed. Useful conditional guidance was
retained only where source semantics, platform capabilities, failure impact, and
recovery requirements determine the choice.

## Consequences

The package has one activation surface and smaller task contexts. The v6 rename,
workflow vocabulary, JSON schema, and bundle interface are breaking changes.
