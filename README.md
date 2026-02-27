# Data Engineering Best Practices — Claude Code Skill

A production-grade Claude Code skill that acts as a senior data engineering architect, reviewer, and playbook for the Google Cloud stack (BigQuery, Airflow/Composer, Pub/Sub, Dataflow, dbt/DataForm, Dataplex).

## Install

```bash
# Install all skills from this repo
npx skills add madhukoseke/de-skills

# Install only the data-engineering skill
npx skills add madhukoseke/de-skills --skill data-engineering-best-practices
```

## What It Does

When triggered, the skill operates in one of nine modes based on your request:

| Mode | Trigger Examples | Output |
|------|-----------------|--------|
| **DESIGN** | "Design a pipeline to ingest X into BQ" | Architecture diagram + data contract + runbook |
| **BQ_MODEL** | "Help me model a table for 50M events/day" | DDL + partition/cluster strategy + cost estimate |
| **AIRFLOW** | "Review this DAG for reliability issues" | Structured audit + code fixes + review template |
| **STREAMING** | "Architect a real-time pipeline with Pub/Sub" | Streaming architecture + capacity plan |
| **PR_REVIEW** | "Review this PR that adds a BQ load task" | Review table + risk assessment + verdict |
| **DBT** | "Create/review a dbt model and tests" | dbt model SQL + test strategy + review template |
| **DATA_QUALITY** | "Design DQ checks and reporting" | DQ rule set + checks + DQ report template |
| **DIAGNOSE** | "Pipeline failing, help debug" | Triage + root cause analysis + remediation |
| **COST_AUDIT** | "Audit BigQuery spend" | Ranked cost drivers + optimization plan |

## Principles

The skill enforces these non-negotiable principles:

1. **Idempotency first** — MERGE or DELETE+INSERT, never bare INSERT
2. **Partition before cluster** — Always partition BigQuery tables first
3. **Fail loud** — Silent data loss is worse than a failed run
4. **Schema is a contract** — Every boundary has a documented data contract
5. **Cost is a feature** — Every query decision considers `bytes * $6.25/TB`
6. **Retry with backoff** — Exponential backoff with jitter on all external calls
7. **Observability by default** — Row counts, duration, freshness on every pipeline
8. **Separation of concerns** — Orchestration ≠ business logic

## Repo Structure

```
skills/data-engineering-best-practices/
├── SKILL.md                          # Entry point — mode table, principles, examples
├── playbooks/
│   ├── 01_pipeline_design.md         # Batch/stream decision tree, architecture templates
│   ├── 02_bigquery_modeling_cost.md  # Partition/cluster strategy, cost formulas, DDL
│   ├── 03_airflow_reliability.md     # Retries, idempotency, sensors, backfill
│   ├── 04_streaming_pubsub.md        # Pub/Sub patterns, exactly-once, Dataflow
│   ├── 05_pr_review_checklist.md     # Structured PR review checklist
│   ├── 06_dbt_patterns.md            # dbt model/materialization/testing patterns
│   ├── 07_data_quality.md            # DQ framework and implementation patterns
│   └── 08_environments_and_iac.md    # Multi-env and Terraform playbook
└── templates/
    ├── data_contract.yaml            # Annotated data contract template
    ├── airflow_dag_review.md         # DAG review output template
    ├── runbook.md                    # Operational runbook template
    ├── incident_postmortem.md        # Postmortem with 5 Whys framework
    ├── dbt_model_review.md           # dbt model review template
    └── data_quality_report.md        # Data quality reporting template
```

## Playbooks

| Playbook | Description |
|----------|-------------|
| [Pipeline Design](skills/data-engineering-best-practices/playbooks/01_pipeline_design.md) | Batch vs stream decision tree, hybrid patterns, source-specific guidance, capacity planning |
| [BigQuery Modeling & Cost](skills/data-engineering-best-practices/playbooks/02_bigquery_modeling_cost.md) | Partition types, clustering strategy, cost formulas, DDL patterns, naming conventions |
| [Airflow Reliability](skills/data-engineering-best-practices/playbooks/03_airflow_reliability.md) | Retry strategy with code, idempotency patterns, sensor best practices, backfill guidance |
| [Streaming & Pub/Sub](skills/data-engineering-best-practices/playbooks/04_streaming_pubsub.md) | Topic design, subscription patterns, dead-letter, Dataflow windowing, exactly-once |
| [PR Review Checklist](skills/data-engineering-best-practices/playbooks/05_pr_review_checklist.md) | Structured review table, BQ/Airflow/streaming items, risk assessment matrix |
| [dbt Patterns](skills/data-engineering-best-practices/playbooks/06_dbt_patterns.md) | dbt model structure, materializations, tests, dbt+Airflow integration |
| [Data Quality](skills/data-engineering-best-practices/playbooks/07_data_quality.md) | DQ taxonomy, SQL assertions, dbt tests, anomaly detection, quarantine |
| [Environments & IaC](skills/data-engineering-best-practices/playbooks/08_environments_and_iac.md) | Multi-environment strategy, Terraform modules, CI/CD patterns |

## Templates

| Template | Used By |
|----------|---------|
| [Data Contract](skills/data-engineering-best-practices/templates/data_contract.yaml) | DESIGN, BQ_MODEL, PR_REVIEW |
| [DAG Review](skills/data-engineering-best-practices/templates/airflow_dag_review.md) | AIRFLOW, PR_REVIEW |
| [Runbook](skills/data-engineering-best-practices/templates/runbook.md) | DESIGN, AIRFLOW, STREAMING |
| [Incident Postmortem](skills/data-engineering-best-practices/templates/incident_postmortem.md) | All modes (failure investigation) |
| [dbt Model Review](skills/data-engineering-best-practices/templates/dbt_model_review.md) | DBT, PR_REVIEW |
| [Data Quality Report](skills/data-engineering-best-practices/templates/data_quality_report.md) | DATA_QUALITY, PR_REVIEW, DIAGNOSE |

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security

Please report security vulnerabilities per our [Security Policy](SECURITY.md).

## License

MIT
