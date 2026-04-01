# Data Engineering Best Practices Agent Skill

[![CI](https://github.com/madhukoseke/de-skills/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/madhukoseke/de-skills/actions/workflows/validate-skill.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Skill Version](https://img.shields.io/badge/skill%20version-4.0-blue)](CHANGELOG.md)

A production-grade agent skill and instruction contract that acts as a senior data engineering architect, reviewer, and playbook for the modern data stack (Airflow, dbt, SQL warehouses, Spark, streaming pipelines, data modeling, schema management, and data quality).

## Quick Start

1. Verify generated artifacts and adapters:

```bash
python3 scripts/build_adapters.py --check
python3 tests/validate_adapters.py
python3 tests/validate_provider_fixtures.py
```

2. Use a provider bundle from `skills/data-engineering-best-practices/dist/<provider>/system_prompt.txt`.

3. Start from one of the runtime examples in `examples/`.

4. Read `OPERATOR_GUIDE.md` for the full workflow.

## Why This Skill?

Without the skill, a generic LLM gives you directionally correct but production-unsafe advice — it suggests `append` instead of idempotent `MERGE`, omits retry configuration, teaches SQL injection patterns as examples, and produces no cost estimates, failure tiers, or structured output.

With the skill active, every response is grounded in 12 non-negotiable principles, references the relevant playbook, produces copy-paste-ready code with exact configuration values, and includes a cost estimate and failure-action decision matrix.

In a head-to-head test across 4 modes (DESIGN, AIRFLOW, DBT, DATA_QUALITY), the skill identified **11 production bugs** in generic LLM responses that would have caused data corruption or silent data loss.

## How to Use

```bash
# Claude-compatible packaged install
npx skills add madhukoseke/de-skills

# Claude-compatible install for only the data-engineering skill
npx skills add madhukoseke/de-skills --skill data-engineering-best-practices
```

The canonical contract lives at `skills/data-engineering-best-practices/SKILL.md`.

You can consume it in three ways:

- As a packaged skill via `npx skills add ...` in Claude-compatible workflows
- As a direct system/developer instruction contract by loading `SKILL.md` into an agent runtime or API call
- As provider-specific adapter metadata and generated bundles under `skills/data-engineering-best-practices/agents/` and `skills/data-engineering-best-practices/dist/`
- As copy-paste integration examples under `examples/`

## Compatibility

| Surface | Status | Notes |
|---------|--------|-------|
| Canonical skill contract | Supported | `skills/data-engineering-best-practices/SKILL.md` is the source of truth |
| Claude-compatible skill loaders | Supported | Uses the packaged `npx skills add ...` flow |
| OpenAI/Codex direct prompting | Supported | Load `SKILL.md` or `dist/openai/system_prompt.txt` |
| Anthropic direct prompting | Supported | Use `agents/anthropic.yaml` and `dist/anthropic/system_prompt.txt` |
| Gemini direct prompting | Supported | Use `agents/gemini.yaml` and `dist/gemini/system_prompt.txt` |
| Generic runtime | Supported | Use `agents/generic.yaml` and `dist/generic/system_prompt.txt` |

## What It Does

When triggered, the skill operates in one of eleven modes based on your request:

| Mode | Trigger Examples | Output |
|------|-----------------|--------|
| **DESIGN** | "Design a pipeline to ingest X into the warehouse" | Architecture diagram + data contract + runbook |
| **WAREHOUSE** | "Help me model a table for 50M events/day" | DDL + partition/index strategy + storage estimate |
| **AIRFLOW** | "Review this DAG for reliability issues" | Structured audit + code fixes + review template |
| **STREAMING** | "Architect a real-time pipeline with Kafka" | Streaming architecture + capacity plan |
| **PR_REVIEW** | "Review this PR that adds a new load task" | Review table + risk assessment + verdict |
| **DBT** | "Create/review a dbt model and tests" | dbt model SQL + test strategy + review template |
| **DATA_QUALITY** | "Design DQ checks and reporting" | DQ rule set + checks + DQ report template |
| **SQL** | "Review this SQL / write a window function / optimize this query" | SQL + EXPLAIN guidance + SQL review template |
| **SPARK** | "Review this PySpark job / fix skew / Delta Lake patterns" | Spark code + skew/shuffle guidance + Spark review template |
| **DATA_MODELING** | "Design a star schema / SCD Type 2 / medallion architecture" | DDL + modeling rationale + data model design template |
| **DIAGNOSE** | "Pipeline failing, help debug" | Triage + root cause analysis + remediation |

## Principles

The skill enforces these non-negotiable principles:

1. **Idempotency first** — MERGE or DELETE+INSERT, never bare INSERT
2. **Partition/index strategically** — Large tables must be partitioned based on primary query patterns
3. **Fail loud** — Silent data loss is worse than a failed run
4. **Schema is a contract** — Every boundary has a documented data contract
5. **Cost is a feature** — Every query decision considers compute and storage cost
6. **Retry with backoff** — Exponential backoff with jitter on all external calls
7. **Observability by default** — Row counts, duration, freshness on every pipeline
8. **Separation of concerns** — Orchestration ≠ business logic
9. **Lineage is not optional** — Every transformation declares sources and outputs
10. **Environments must be code-identical** — Dev/staging/prod differ only in data volume and access
11. **Test at every layer** — Unit, contract, integration, and idempotency tests at every level
12. **Schema-first design** — Design and register schemas before writing pipeline code; detect drift at ingest

## Repo Structure

```
skills/data-engineering-best-practices/
├── SKILL.md                              # Entry point — mode table, principles, examples
├── agents/
│   ├── openai.yaml                       # OpenAI/Codex-facing adapter metadata
│   ├── anthropic.yaml                    # Anthropic/Claude-facing adapter metadata
│   ├── gemini.yaml                       # Gemini-facing adapter metadata
│   ├── generic.yaml                      # Generic runtime adapter metadata
│   └── capabilities.json                 # Provider capability manifest
├── dist/
│   ├── openai/                           # Generated OpenAI/Codex contract bundle
│   ├── anthropic/                        # Generated Anthropic contract bundle
│   ├── gemini/                           # Generated Gemini contract bundle
│   └── generic/                          # Generated generic contract bundle
├── playbooks/
│   ├── 01_pipeline_design.md             # Batch/stream decision tree, architecture templates
│   ├── 02_airflow_reliability.md         # Retries, idempotency, sensors, backfill
│   ├── 03_pr_review_checklist.md         # Structured PR review checklist
│   ├── 04_dbt_patterns.md                # dbt model/materialization/testing patterns
│   ├── 05_data_quality.md                # DQ framework and implementation patterns
│   ├── 06_streaming_architecture.md      # Kafka, Flink, CDC, windowing, exactly-once, DLQ
│   ├── 07_sql_patterns.md                # Window functions, idempotent DML, EXPLAIN, dialect portability
│   ├── 08_spark_patterns.md              # Partitioning, skew, Delta/Iceberg, Spark Streaming, testing
│   ├── 09_data_modeling.md               # Kimball, Data Vault, OBT, Medallion, SCD types
│   ├── 10_orchestration_patterns.md      # Airflow vs Prefect vs Dagster, DAG-as-code, CI/CD
│   ├── 11_testing_strategies.md          # DE testing pyramid, SQL/Spark/dbt/contract/E2E tests
│   └── 12_schema_management.md           # Schema registry, evolution, migrations, drift detection
└── templates/
    ├── data_contract.yaml                # Annotated data contract template
    ├── airflow_dag_review.md             # DAG review output template
    ├── runbook.md                        # Operational runbook template
    ├── incident_postmortem.md            # Postmortem with 5 Whys framework
    ├── dbt_model_review.md               # dbt model review template
    ├── data_quality_report.md            # Data quality reporting template
    ├── sql_review.md                     # SQL query review template
    ├── spark_job_review.md               # Spark job review template
    └── data_model_design.md              # Data model design template
```

## Playbooks

| Playbook | Description |
|----------|-------------|
| [Pipeline Design](skills/data-engineering-best-practices/playbooks/01_pipeline_design.md) | Batch vs stream decision tree, hybrid patterns, source-specific guidance, capacity planning |
| [Airflow Reliability](skills/data-engineering-best-practices/playbooks/02_airflow_reliability.md) | Retry strategy with code, idempotency patterns, sensor best practices, backfill guidance |
| [PR Review Checklist](skills/data-engineering-best-practices/playbooks/03_pr_review_checklist.md) | Structured review table, warehouse/Airflow/streaming items, risk assessment matrix |
| [dbt Patterns](skills/data-engineering-best-practices/playbooks/04_dbt_patterns.md) | dbt model structure, materializations, tests, dbt+Airflow integration |
| [Data Quality](skills/data-engineering-best-practices/playbooks/05_data_quality.md) | DQ taxonomy, SQL assertions, dbt tests, anomaly detection, quarantine |
| [Streaming Architecture](skills/data-engineering-best-practices/playbooks/06_streaming_architecture.md) | Kafka/Kinesis/Pulsar, Flink/Spark Streaming, CDC, windowing, exactly-once, DLQ |
| [SQL Patterns](skills/data-engineering-best-practices/playbooks/07_sql_patterns.md) | Window functions, idempotent DML, EXPLAIN plans, incremental loads, dialect portability |
| [Spark Patterns](skills/data-engineering-best-practices/playbooks/08_spark_patterns.md) | Partitioning, skew/shuffle, Delta/Iceberg/Hudi, Spark Streaming, PySpark testing |
| [Data Modeling](skills/data-engineering-best-practices/playbooks/09_data_modeling.md) | Kimball, Data Vault, OBT, Medallion architecture, SCD types, naming conventions |
| [Orchestration Patterns](skills/data-engineering-best-practices/playbooks/10_orchestration_patterns.md) | Airflow vs Prefect vs Dagster vs Temporal, DAG-as-code, dynamic tasks, CI/CD |
| [Testing Strategies](skills/data-engineering-best-practices/playbooks/11_testing_strategies.md) | DE testing pyramid, SQL/Spark/dbt unit tests, contract tests, integration, E2E |
| [Schema Management](skills/data-engineering-best-practices/playbooks/12_schema_management.md) | Schema registry, evolution compatibility, migration patterns, drift detection, catalog-first |

## Templates

| Template | Used By |
|----------|---------|
| [Data Contract](skills/data-engineering-best-practices/templates/data_contract.yaml) | DESIGN, WAREHOUSE, PR_REVIEW, DATA_MODELING |
| [DAG Review](skills/data-engineering-best-practices/templates/airflow_dag_review.md) | AIRFLOW, PR_REVIEW |
| [Runbook](skills/data-engineering-best-practices/templates/runbook.md) | DESIGN, AIRFLOW, STREAMING |
| [Incident Postmortem](skills/data-engineering-best-practices/templates/incident_postmortem.md) | All modes (failure investigation) |
| [dbt Model Review](skills/data-engineering-best-practices/templates/dbt_model_review.md) | DBT, PR_REVIEW |
| [Data Quality Report](skills/data-engineering-best-practices/templates/data_quality_report.md) | DATA_QUALITY, PR_REVIEW, DIAGNOSE |
| [SQL Review](skills/data-engineering-best-practices/templates/sql_review.md) | SQL, PR_REVIEW |
| [Spark Job Review](skills/data-engineering-best-practices/templates/spark_job_review.md) | SPARK, PR_REVIEW |
| [Data Model Design](skills/data-engineering-best-practices/templates/data_model_design.md) | DATA_MODELING, DESIGN |

## Build Adapters

Generate or verify provider bundles from the canonical contract:

```bash
python3 scripts/build_adapters.py
python3 scripts/build_adapters.py --check
python3 tests/validate_adapters.py
```

## Examples

- `examples/openai_responses_api.py`
- `examples/anthropic_messages_api.py`
- `examples/gemini_generate_content.py`
- `examples/generic_system_prompt.md`

Operator-facing usage guidance lives in `OPERATOR_GUIDE.md`.

Provider compatibility notes live in `skills/data-engineering-best-practices/agents/model_compatibility.md`.

## Pending Items

The remaining production backlog is tracked in `ROADMAP.md`.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and our [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Please report security vulnerabilities per our [Security Policy](SECURITY.md).

## License

MIT
