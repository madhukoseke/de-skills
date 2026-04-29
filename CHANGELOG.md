# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [5.0.0] - 2026-04-29

### BREAKING

- **Stable principle IDs `W001`–`W012`.** SKILL.md non-negotiable principles now carry stable identifiers. Numbered list positions remain 1–12, but downstream tooling that already keyed on bare position numbers should migrate to IDs. The IDs are guaranteed not to move; new principles append (W013+). Playbooks, templates, and the JSON response schema reference principles by ID.
- **JSON response schema enriched** at `schemas/skill_response.schema.json`. New optional fields: `mode` (enum of the 11 modes), `principlesCited` (array of `W0NN` IDs), `risks` (array of `{severity, description, mitigation}`), `lineage` (`sources[]` / `targets[]`), `dataContract` (`path` or `inline`). Backwards compatible: every new field is optional and consumers that ignore them continue to work.

### Migration

- Search downstream for hardcoded "Principle 1" / "Principle 5" string matches; replace with `W001` / `W005` (or the descriptive form `Principle W001 — Idempotency first`).
- If you author JSON responses, you may opt into the new fields incrementally — none are required.

### Added

- **Playbook 13 — Lineage & Observability** (`playbooks/13_lineage_and_observability.md`): OpenLineage event spec, dbt manifest-as-catalog-input, vendor-neutral catalog plane comparison (DataHub / OpenMetadata / Marquez / Unity Catalog / Snowflake Horizon / BigQuery Lineage), the four standard data SLIs (freshness, completeness, validity, reconciliation), burn-rate alerting, on-call escalation chain.
- **Playbook 14 — Governance, PII, and Compliance** (`playbooks/14_governance_and_pii.md`): data classification taxonomy, PII subcategory mapping, masking strategy decision tree, RBAC + RLS + CLS layered access, audit log schema, GDPR right-to-erasure (tombstone-and-purge + crypto-erasure), data residency and cross-border transfer rules, governance CI gates.
- **Playbook 15 — Cost Optimization** (`playbooks/15_cost_optimization.md`): the four cost levers, attribution tagging via session tags / dbt query tags / Spark properties, partition-pruning verification, reserved vs on-demand strategy, storage tier lifecycle, time-travel as a cost lever, small-file/compaction loops, retention as the most underused lever, query-result caching, cost CI gates.
- **Playbook 16 — ML & Vector Pipelines** (`playbooks/16_ml_and_vector_pipelines.md`): offline/online plane separation, feature stores (Feast / Tecton / Databricks Feature Store / Vertex / SageMaker), point-in-time joins, training-serving skew detection, drift monitoring (feature / label / concept), vector DB selection by scale and latency, hybrid search with RRF, embedding contracts, RAG ingestion idempotency, deduplication, RAG observability, embedding right-to-erasure.
- **CDC expansion in playbook 06** — engine comparison (Debezium / Debezium Server / Fivetran HVR / Airbyte CDC / Striim / AWS DMS / cloud-native), initial-snapshot strategy table, schema-evolution decision matrix for CDC, transactional consistency across tables, idempotency in CDC consumers via LSN dedup + MERGE, heartbeats and lag monitoring, outbox pattern.
- **`templates/slo_definition.md`** — fillable SLO + SLI + error-budget + alert-policy template; tenth template in the index.
- **`templates/data_contract.yaml`** extended with three optional blocks: `retention` (`period_days`, `hard_delete_after`, `legal_hold`, `basis`, `deletion_method`), `governance` (classification, masking_policy, encryption-at-rest/in-transit, audit_log_dataset, data_residency, cross_border_transfer, consent_keyed/consent_column), `subject_rights` (right_to_erasure / access / portability, identifiable_by, erasure_strategy, erasure_sla_hours).
- **Principle ID validation in CI** — `tests/validate_skill_structure.py` now asserts each principle has a `(W0NN)` ID and that IDs run `W001..W{count}` contiguously.

### Changed

- **SKILL.md Playbook Index** — sixteen entries (was twelve); new rows for lineage+obs, governance+PII, cost, ML+vector.
- **SKILL.md Template Index** — ten entries (was nine); new row for SLO definition.
- **README** — copy updated to reflect 16 playbooks, 10 templates, and stable principle IDs.
- **In-playbook references to principles** — eleven references across playbooks 02 / 03 / 04 migrated from "Principle N" bare-number form to "Principle W0NN — Title" form.

### Notes

- Eleven operating modes and twelve principles unchanged in semantics — this release adds **content surface** and **stability guarantees**, not new contract surface.
- The `dist/<provider>/system_prompt.txt` bundles are regenerated from the new `SKILL.md`; their SHA changes. Consumers that pin SHA must bump.

## [4.1.0] - 2026-04-29

### Added

- **dbt 1.5+ Model Contracts** — playbook 04 §8 covers `config.contract.enforced: true`, column `data_type` + `constraints` declaration, and the rule that contract-breaking changes require a new model version (§10).
- **dbt 1.5+ Groups & Access (Mesh)** — playbook 04 §9 covers `groups:` ownership, `access: private | protected | public`, the per-access-level visibility matrix, and cross-project consumption via `dependencies.yml`.
- **dbt 1.5+ Model Versions** — playbook 04 §10 covers `latest_version`, per-version `deprecation_date`, `defined_in:` for SQL filename overrides, and `{{ ref('model', v=N) }}` consumer migration.
- **dbt 1.6+ Semantic Layer & Metrics** — playbook 04 §11 covers `semantic_models:`, `metrics:` (simple / cumulative / ratio), MetricFlow CLI usage, and the rule that metrics must reference contracted models.
- **Warehouse-Managed Incremental Tables** — playbook 04 §12 introduces a vendor-neutral feature-parity table (Snowflake Dynamic Tables, BigQuery Materialized Views / managed Iceberg, Databricks Live Tables, Redshift Materialized Views) with dbt 1.6+ adapter-specific materializations and decision rules vs. classic `incremental`.
- **Apicurio Registry coverage** — playbook 12 now has a code block for both the Confluent-compatible API and the Core REST API, plus a registry-selection table covering bundled / Glue / Apicurio / Confluent.
- **Provider optimization metadata** — `agents/capabilities.json` declares per-provider `optimization` (prompt caching strategy + structured-output mode). `scripts/build_adapters.py` propagates this to `dist/<provider>/metadata.json` so consumers can discover the right knob without parsing markdown.
- **Anthropic prompt caching** — `examples/anthropic_messages_api.py` now wraps the system block with `cache_control: {"type": "ephemeral"}` (toggleable via `ANTHROPIC_PROMPT_CACHING=0`). Cuts input cost ~90% on repeated requests within the 5-minute TTL; cache stats printed to stderr from `usage.cache_read_input_tokens`.
- **`agents/context_budget.md` "Prompt caching" subsection** — provider-by-provider table covering OpenAI automatic caching, Anthropic explicit `cache_control`, Gemini `cachedContents`, and the generic-runtime fallback.
- **JSON response fixture** — `tests/captured_responses/TC-E2E-001.json` mirrors the markdown fixture and is now validated by `validate_json_responses.py` in CI.
- **`templates/dbt_model_review.md`** — new checklist rows (#16–#22) for `group`, `access`, contract enforcement, version migration, semantic-layer wiring, materialized-incremental SLA, and `public`-access readiness.

### Changed

- **`playbooks/04_dbt_patterns.md`** — `profiles.yml` example replaced with a vendor-neutral skeleton plus warehouse-specific blocks for Snowflake, BigQuery, Databricks, Redshift, and Postgres/Trino/DuckDB. Every credential now uses `env_var(...)` with no defaults on secrets.
- **`examples/openai_responses_api.py`** — dropped the hardcoded `OPENAI_MODEL` default; the env var is now required, matching the Anthropic and Gemini examples.
- **Anthropic model recommendations** — `agents/model_compatibility.md` now also mentions prompt-caching as a first-class optimization (the "Notes" section), pointing to the new context-budget subsection.

### Notes

- No contract change: 11 modes, 12 principles, 12 playbooks, 9 templates unchanged.
- Backwards compatible with consumers reading `dist/<provider>/metadata.json` — the new `optimization` block is additive.

## [4.0.1] - 2026-04-29

### Security

- **Airflow example rewritten** — `examples/airflow/postgres_to_bq_orders.py` was renamed to `postgres_to_orders.py` and rewritten with the TaskFlow API. Eliminates f-string SQL injection (the previous version interpolated the `ds` macro into raw SQL), removes module-level `Variable.get()`, removes direct `settings.Session().query(Connection)`, and replaces all BigQuery operators with vendor-neutral Postgres hooks. Added schema-identifier whitelisting and idempotent DELETE+INSERT for partition loads.
- **`SECURITY.md`** — removed `[INSERT SECURITY EMAIL]` placeholder; GitHub private vulnerability advisories are now the documented channel with an issue-based fallback.
- **CI permissions hardened** — `validate-skill.yml` and `release-skill.yml` now declare explicit `permissions: { contents: read }` at workflow and job scope.
- **CodeQL workflow added** — `.github/workflows/codeql.yml` runs Python `security-and-quality` queries on every PR plus weekly.
- **`__pycache__` regression guard** — `validate-skill.yml` now fails if any `__pycache__` directory is committed.

### Fixed

- **`agents/model_compatibility.md`** — refreshed Anthropic model recommendations to current 2026 Claude family (`claude-opus-4-7`, `claude-opus-4-7[1m]`, `claude-sonnet-4-6`, `claude-haiku-4-5`); added a hand-curated review-date banner so the file's freshness is visible.

### Added

- `tests/validate_json_responses.py` — validates JSON response fixtures against `schemas/skill_response.schema.json` in CI.
- `tests/requirements.txt` — pins `jsonschema==4.23.0` and `PyYAML==6.0.2` for the validator harness.
- `live-provider-smoke.yml` now includes Anthropic and Gemini smoke jobs (gated on `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`); closes ROADMAP card PKG-011.
- `docs/plans/csv_agent_skill_package.md` — committed (was untracked despite being referenced from ROADMAP PKG-015).

### Changed

- `tests/validate_adapters.py` — replaced hand-rolled YAML parser with `yaml.safe_load`; declares `PyYAML` dependency in `tests/requirements.txt`.
- `CONTRIBUTING.md` / `OPERATOR_GUIDE.md` / `AGENTS.md` — validator command lists updated to reference the new JSON validator and dependency-install step.
- `examples/airflow/README.md` — updated to reflect the new filename and explicitly call out the security guarantees (no f-string SQL, parameterized queries, no BigQuery operators).

### Notes

- No contract change: 11 modes, 12 principles, 12 playbooks, 9 templates unchanged.
- Simplified `README.md` for clearer install/use paths and less duplication with `SKILL.md`
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
