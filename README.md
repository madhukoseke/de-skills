# Data Engineering Best Practices — Claude Code Skill

[![CI](https://github.com/madhukoseke/de-skills/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/madhukoseke/de-skills/actions/workflows/validate-skill.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Skill Version](https://img.shields.io/badge/skill%20version-4.0-blue)](CHANGELOG.md)

A production-grade Claude Code skill that acts as a senior data engineering architect, reviewer, and playbook for the modern data stack (Airflow, dbt, SQL warehouses, Spark, streaming pipelines, data modeling, schema management, and data quality).

## Why This Skill?

Without the skill, a generic LLM gives you directionally correct but production-unsafe advice — it suggests `append` instead of idempotent `MERGE`, omits retry configuration, teaches SQL injection patterns as examples, and produces no cost estimates, failure tiers, or structured output.

With the skill active, every response is grounded in 12 non-negotiable principles, references the relevant playbook, produces copy-paste-ready code with exact configuration values, and includes a cost estimate and failure-action decision matrix.

In a head-to-head test across 4 modes (DESIGN, AIRFLOW, DBT, DATA_QUALITY), the skill identified **11 production bugs** in generic LLM responses that would have caused data corruption or silent data loss.

## Install

```bash
# Install all skills from this repo
npx skills add madhukoseke/de-skills

# Install only the data-engineering skill
npx skills add madhukoseke/de-skills --skill data-engineering-best-practices
```

## Requirements

| Requirement | Version |
|-------------|---------|
| Claude Code CLI | ≥ 1.0 |
| `npx skills` CLI | latest (`npx skills add ...`) |
| Claude model | Claude Sonnet or Opus (Haiku not recommended for complex design tasks) |

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

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and our [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Please report security vulnerabilities per our [Security Policy](SECURITY.md).

## License

MIT
