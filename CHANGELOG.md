# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Reframed the repository as a vendor-neutral agent skill with `skills/data-engineering-best-practices/SKILL.md` as the canonical contract
- Updated README and CONTRIBUTING to separate canonical skill content from product-specific adapters
- Slimmed `CLAUDE.md` into a Claude-specific adapter document instead of treating Claude as the repo identity
- Generalized the live benchmark runner terminology from `skill-file` to `contract-file` while keeping backward compatibility

### Added

- `skills/data-engineering-best-practices/agents/openai.yaml` for OpenAI/Codex-facing metadata
- `AGENTS.md` for generic agent-facing repository guidance
- `tests/validate_vendor_neutrality.py` and CI enforcement to keep canonical skill content free of provider-specific branding
- Multi-provider adapter manifests for Anthropic, Gemini, and generic runtimes
- `skills/data-engineering-best-practices/skill.json` and `agents/capabilities.json` to describe supported providers and generated outputs
- `scripts/build_adapters.py` to build provider-specific contract bundles under `skills/data-engineering-best-practices/dist/`
- `tests/validate_adapters.py` and `tests/benchmark/live/provider_matrix.json` for adapter consistency checks
- Provider-pluggable live benchmark transports under `tests/benchmark/live/providers/`
- Provider integration examples under `examples/`
- `ROADMAP.md` to track remaining production-grade backlog and open questions
- `BENCHMARK_DRY_RUN=1` support in the live benchmark shell wrapper
- Dry-run benchmark shell mode now exits before validator/scoring so wrapper smoke tests succeed without live API output
- Provider fixture validation with recorded OpenAI, Anthropic, and Gemini payloads
- `agents/model_compatibility.md` with provider/model guidance and known quirks
- Release packaging workflow and `scripts/package_release.py` for versioned artifact bundles
- Benchmark contract `v2` with formatting compliance, clarification quality, and prompt-injection resilience dimensions
- CI `docs` job: `markdownlint-cli2` on canonical markdown plus `lychee` link checking (with fixture paths excluded)
- `.github/dependabot.yml` for weekly GitHub Actions updates
- `tests/validate_skill_structure.py` to assert modes, inputs, templates, and README principle counts stay aligned with `SKILL.md`
- `examples/airflow/` sample DAG + README (moved from ad-hoc `dags/`)
- Optional JSON response contract at `skills/data-engineering-best-practices/schemas/skill_response.schema.json`
- `agents/context_budget.md` for token-budget / truncation guidance across providers
- `.github/workflows/live-provider-smoke.yml` scheduled + manual OpenAI smoke (`--max-cases 1`) when `OPENAI_API_KEY` is set

## [4.0.0] - 2026-03-22

### Added

- **Three new operating modes:** SQL (window functions, EXPLAIN, idempotent DML, dialect portability), SPARK (PySpark patterns, Delta/Iceberg/Hudi, skew/shuffle), DATA_MODELING (Kimball, Data Vault, OBT, Medallion, SCD types)
- **Seven new playbooks:**
  - `06_streaming_architecture.md` — Kafka/Kinesis/Pulsar, Flink/Spark Streaming, CDC, windowing, exactly-once, DLQ
  - `07_sql_patterns.md` — Window functions, idempotent DML, EXPLAIN plans, incremental loads, cross-dialect portability
  - `08_spark_patterns.md` — Partitioning, skew mitigation, shuffle optimization, Delta/Iceberg/Hudi, Spark Streaming, PySpark testing
  - `09_data_modeling.md` — Kimball star schema, Data Vault 2.0, OBT, Lakehouse/medallion, SCD Types 0–3, naming conventions
  - `10_orchestration_patterns.md` — Airflow vs Prefect vs Dagster vs Temporal, DAG-as-code, dynamic tasks, CI/CD for orchestration
  - `11_testing_strategies.md` — DE testing pyramid, SQL/Spark/dbt unit tests, contract tests, integration tests, E2E validation
  - `12_schema_management.md` — Schema registry, evolution compatibility modes, migration patterns, drift detection, catalog-first
- **Three new templates:**
  - `templates/sql_review.md` — SQL query review checklist + EXPLAIN summary + cost impact
  - `templates/spark_job_review.md` — Spark job review checklist + performance analysis
  - `templates/data_model_design.md` — Data model design checklist + schema DDL + lineage
- **Two new principles** (10→12 total):
  - Principle 11: "Test at every layer"
  - Principle 12: "Schema-first design"

### Changed

- Renamed playbooks to fill numbering gaps left from GCP removal: `03→02`, `05→03`, `06→04`, `07→05`
- Updated SKILL.md Playbook Index, README, and e2e_test_cases.md to reflect new playbook numbers
- Bumped SKILL.md version `3.0 → 4.0`
- Updated metadata tags to include `spark`, `data-modeling`, `schema`, `orchestration`, `testing`
- CLAUDE.md updated: modes count 8→11, playbooks `01-07` → `01-12`

## [3.0.0] - 2026-03-22

### Removed

- All GCP-specific content: BigQuery, Cloud Composer, Pub/Sub, Dataflow, Dataplex, DataForm, Cloud DLP, Cloud Monitoring, GCS, Workload Identity, VPC-SC
- Three GCP-only playbooks: `02_bigquery_modeling_cost.md`, `04_streaming_pubsub.md`, `08_environments_and_iac.md`
- Operating modes: BQ_MODEL, COST_AUDIT

### Changed

- Skill identity: "Google Cloud specialist" → "modern data stack architect"
- SKILL.md principle 2: BQ partition-before-cluster → generic "partition/index strategically"
- SKILL.md principle 5: BQ cost formula removed → generic cost guidance
- Added generic WAREHOUSE mode replacing BQ_MODEL
- All playbooks generalized: GCS→object storage, Composer→Airflow, BQ→warehouse, Pub/Sub→broker, Dataflow→stream processor
- Templates generalized: BQ types (STRING/INT64) → generic (VARCHAR/INTEGER), BQ partition config → generic partition/index
- Data contract YAML: `destination.project` removed, `destination.dataset` → `destination.schema`
- Bumped version `2.0 → 3.0`

### Added

- Trust Boundary section in SKILL.md to mitigate indirect prompt injection (W011) when processing PR diffs, DAG code, or external links
- Security Considerations in SECURITY.md documenting untrusted content handling
- Reinforced W011 guardrails in `playbooks/02_airflow_reliability.md` (trust boundary callout at DAG review checklist entry point)
- Reinforced W011 guardrails in `playbooks/03_pr_review_checklist.md` (trust boundary callout at PR ingestion entry point)

## [2.0.0] - 2026-03-01

### Changed

- Updated CI validation to check playbook/template paths directly from `SKILL.md` references instead of a hardcoded file list
- Aligned E2E test specs and validator checks with current operating modes (`WAREHOUSE`, `DATA_QUALITY`) and current playbook set
- Updated smoke suite to include `TC-E2E-012` and refreshed captured response fixture for data quality mode
- Expanded benchmark suite to 30 E2E cases covering SQL, Spark, data modeling, schema management, deploy, and performance scenarios
- Added benchmark contract lock at `tests/benchmark/contract/v1.json` with verification script for versioned/auditable changes
- Added live benchmark harness (`tests/benchmark/live/`) for same-prompts, same-model skill on/off comparisons
- Updated rubric to contract-driven dimensions: correctness, safety, actionability, cost-awareness, and testability
- Added DBT and DATA_QUALITY operating modes
- Added playbooks: dbt Patterns (`06_dbt_patterns.md`), Data Quality (`07_data_quality.md`)
- Added templates: dbt Model Review, Data Quality Report

## [1.0.0] - 2026-02-25

### Added

- Initial release: Data Engineering Best Practices skill
- Five operating modes: DESIGN, BQ_MODEL, AIRFLOW, STREAMING, PR_REVIEW
- Playbooks: Pipeline Design, BigQuery Modeling, Airflow Reliability, Streaming & Pub/Sub, PR Review
- Templates: Data Contract, DAG Review, Runbook, Incident Postmortem
