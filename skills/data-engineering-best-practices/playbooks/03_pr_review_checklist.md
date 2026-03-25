---
title: "PR Review Checklist"
description: "Structured checklist for reviewing data engineering pull requests"
tags: [pr-review, code-review, checklist, quality]
related_templates:
  - ../templates/airflow_dag_review.md
  - ../templates/data_contract.yaml
  - ../templates/runbook.md
---

# PR Review Checklist

This checklist provides a structured, repeatable approach to reviewing data engineering pull requests. Use it every time you review a PR to ensure nothing slips through.

---

## How to Use This Checklist

When reviewing a PR, produce a **review summary table** with the following format:

```
| # | Section | Item | Status | Note |
|---|---------|------|--------|------|
| 1 | General | Unit tests added | PASS | Tests cover new transform logic |
| 2 | Warehouse | Partition defined | FAIL | Table missing partition column |
| 3 | Airflow | Retry config set | WARN | Using default retries=0, consider adding |
| 4 | Streaming | Dead-letter configured | N-A | Not a streaming PR |
```

**Status values**:
- **PASS** — Item satisfies requirements. No action needed.
- **FAIL** — Item does not meet requirements. PR must not be merged until resolved.
- **WARN** — Item is technically acceptable but poses a risk. Author should address or justify.
- **N-A** — Item is not applicable to this PR.

Only evaluate sections that are relevant to the PR. Skip entire sections that do not apply (e.g., skip Streaming for a pure Airflow DAG PR) and mark them N-A in the summary.

After the table, provide a final **Recommendation** (APPROVE, REQUEST_CHANGES, or COMMENT) with a one-line rationale.

---

## 1. General Data Engineering Review Items

### Code Quality

| # | Item | What to Check |
|---|------|---------------|
| 1.1 | Code follows team style guide | Linting passes, naming conventions, consistent formatting |
| 1.2 | No hardcoded values | Credentials, hostnames, schema names, bucket paths are parameterized |
| 1.3 | Functions are focused and testable | Single responsibility, pure functions where possible |
| 1.4 | Error handling is explicit | No bare `except:`, failures produce actionable error messages |
| 1.5 | Logging is sufficient | Key operations log start/end, record counts, and error context |
| 1.6 | No unnecessary complexity | Simpler approach would not suffice. YAGNI is respected. |

### Tests

| # | Item | What to Check |
|---|------|---------------|
| 1.7 | Unit tests cover new/changed logic | Every new function or transform has at least one test |
| 1.8 | Tests cover edge cases | NULL handling, empty datasets, boundary values |
| 1.9 | Integration tests for pipeline changes | End-to-end test with sample data exists or is updated |
| 1.10 | Tests are deterministic | No reliance on current time, random values, or external state |

### Documentation

| # | Item | What to Check |
|---|------|---------------|
| 1.11 | PR description explains the "why" | Not just what changed, but why it changed |
| 1.12 | Complex logic has inline comments | Non-obvious SQL, transforms, or business rules are explained |
| 1.13 | Runbook updated if operational behavior changes | New alerts, new failure modes, new dependencies documented |

### Backwards Compatibility

| # | Item | What to Check |
|---|------|---------------|
| 1.14 | Existing consumers are not broken | Schema changes are additive or have a migration path |
| 1.15 | Rollback plan exists | Author can describe how to revert if something goes wrong |
| 1.16 | Feature flags for risky changes | Large changes are behind a toggle for safe rollout |

---

## 2. SQL Warehouse-Specific Items

| # | Item | What to Check |
|---|------|---------------|
| 2.1 | Large tables are partitioned | Every table expected to exceed 1 GB must have a partition column (date/timestamp or integer range) |
| 2.2 | Frequently filtered columns are indexed or clustered | Tables filtered/joined on the same columns have appropriate sort keys or clustering |
| 2.3 | No `SELECT *` in production queries | All columns are explicitly listed. `SELECT *` prevents pruning and inflates costs. |
| 2.4 | Query cost impact assessed | Author has estimated bytes/compute scanned for new/changed queries (dry-run or EXPLAIN) |
| 2.5 | Schema changes have migration plan | Column renames, type changes, or removals include a migration script and rollback |
| 2.6 | Table/view descriptions populated | Description field set on tables and columns for discoverability |
| 2.7 | Appropriate table expiration | Staging/temp tables have expiration set. No orphaned tables. |
| 2.8 | Queries use WHERE on partition column | Queries against partitioned tables include a partition filter to avoid full scans |
| 2.9 | Cost attribution labels applied | New tables and jobs have labels for team, pipeline, and environment cost tracking |

---

## 3. Airflow-Specific Items

| # | Item | What to Check |
|---|------|---------------|
| 3.1 | DAG is idempotent | Re-running the same execution_date produces the same result without side effects |
| 3.2 | Retry configuration is set | `retries >= 3`, `retry_delay` is reasonable (not 0 seconds), `retry_exponential_backoff=True` for external calls |
| 3.3 | No business logic in DAG file | DAG file only defines structure. Logic lives in operators, hooks, or imported modules. |
| 3.4 | Dates use Airflow templates | Uses `{{ ds }}`, `{{ data_interval_start }}`, not `datetime.now()` or hardcoded dates |
| 3.5 | Sensor has timeout and poke_interval | `timeout` is set (not infinite), `poke_interval` is reasonable, `mode="reschedule"` for long waits |
| 3.6 | `start_date` is static | Not set to `datetime.now()` or `days_ago()`. Uses a fixed date. |
| 3.7 | `catchup` is explicitly set | Either `catchup=True` (for backfill-aware DAGs) or `catchup=False` (for snapshot DAGs), never left as default |
| 3.8 | Task dependencies are correct | No missing edges, no circular dependencies, critical path is clear |
| 3.9 | SLA or execution timeout set | `dagrun_timeout` or task-level `execution_timeout` prevents zombie runs |
| 3.10 | Alerting configured | `on_failure_callback` or `email_on_failure` is set. Silent failures are unacceptable. |

---

## 4. Streaming-Specific Items

| # | Item | What to Check |
|---|------|---------------|
| 4.1 | Exactly-once or idempotent processing | Pipeline either uses exactly-once semantics or consumer is idempotent |
| 4.2 | Dead-letter topic configured | Failed messages route to a DLT with monitoring, not silently dropped |
| 4.3 | Backpressure handled | Consumer has flow control settings; autoscaling has a max worker cap |
| 4.4 | Schema evolution safe | Message schema change is backward compatible or versioned topic strategy is used |
| 4.5 | Ack deadline is appropriate | Set to >= 2x p99 processing time, not left at default |
| 4.6 | Windowing strategy documented | Choice of fixed/sliding/session window is justified with business context |
| 4.7 | Late data handling defined | `allowedLateness` is set and documented. Late arrivals are either handled or explicitly dropped. |
| 4.8 | Max workers / autoscaling bounded | Stream processor `maxNumWorkers` (or equivalent) is set. Unbounded autoscaling is a cost risk. |

---

## 5. Data Contract Items

| # | Item | What to Check |
|---|------|---------------|
| 5.1 | Data contract exists for the dataset | A contract YAML/JSON defines schema, owner, SLA, and update frequency |
| 5.2 | PII fields are flagged | Personally identifiable information has `pii: true` tag and is handled per policy |
| 5.3 | SLA is defined and testable | Freshness SLA (e.g., "data available within 2 hours of event") is explicit and monitored |
| 5.4 | Breaking change notice issued | If the contract changes in a non-additive way, downstream consumers are notified before merge |
| 5.5 | Data quality checks defined | Contract includes expectations (not-null, accepted values, uniqueness) enforced in pipeline |
| 5.6 | Ownership is current | `owner` field in the contract matches a real, active team or individual |
| 5.7 | Lineage documented | Source tables and output tables are declared; column-level lineage for PII-adjacent fields |

---

## 6. Security Items

> Reference: Principle 9 (Lineage is not optional) and Principle 10 (Environments must be code-identical).

| # | Item | What to Check |
|---|------|---------------|
| 6.1 | No credentials or secrets in code | No API keys, passwords, or tokens in DAG files, SQL, config files, or environment variables in plain text. Must use a secrets manager or Airflow Connections. |
| 6.2 | Service account/role follows least privilege | The identity used by this pipeline has only the roles it needs. No overly broad permissions (admin/owner/editor). |
| 6.3 | PII columns are masked or encrypted | Any column tagged `pii: true` in the data contract is masked, encrypted, or tokenized as required by policy. |
| 6.4 | New schemas/datasets have access controls configured | Read and write roles are explicitly set. No public schemas unless intentional and documented. |
| 6.5 | Row-level security applied if required | Tables with multi-tenant or per-team data have row-level access policies or authorized views. |
| 6.6 | Audit logging enabled | Write and read audit logs are active on any schema containing sensitive data. |
| 6.7 | No cross-environment data access | Dev/staging pipelines do not reference production tables. Environments are isolated. |
| 6.8 | No long-lived credentials introduced | New service identities authenticate via short-lived tokens or federated identity. No static key files committed unless documented exception. |

---

## 7. Cost Items

> Reference: Principle 5 (Cost is a feature).

| # | Item | What to Check |
|---|------|---------------|
| 7.1 | Query cost estimated for new/changed queries | Author ran EXPLAIN or dry-run and documented estimated compute/bytes scanned. Any expensive query must be justified. |
| 7.2 | No `SELECT *` in scheduled or materialized queries | Full column selection on wide tables inflates cost. All production queries must list explicit columns. |
| 7.3 | Large tables have partition pruning enforced | Queries against partitioned tables must filter on the partition column. Accidental full scans should be prevented. |
| 7.4 | New stream processing jobs have worker cap set | Unbounded autoscaling is a billing incident. Every streaming job must cap workers. |
| 7.5 | Storage costs accounted for | New tables have expiration set if they do not need indefinite retention. Temp/staging tables have expiration. |
| 7.6 | Labels added for cost attribution | New tables, streaming jobs, and services have team, pipeline, and environment labels. |
| 7.7 | Materialized view vs scheduled query evaluated | If a new scheduled query runs more than hourly on a large table, the author has considered a materialized view. |

---

## 8. Risk Assessment Matrix

Rate every PR on these four dimensions to determine overall risk:

| Dimension | Low (1) | Medium (2) | High (3) | Critical (4) |
|---|---|---|---|---|
| **Scope** | Single task/query change | Multiple tasks or new DAG | New pipeline end-to-end | Cross-pipeline or infra change |
| **Data impact** | No production data touched | Modifies non-critical data | Modifies critical data | Could cause data loss or corruption |
| **Reversibility** | Instant rollback (revert commit) | Rollback within minutes | Rollback requires data repair | Irreversible (destructive migration) |
| **Blast radius** | Affects one team | Affects multiple teams | Affects external consumers | Affects customer-facing systems |

### Scoring

Sum the four dimension scores:

| Total Score | Risk Level | Review Requirements |
|---|---|---|
| 4-6 | **Low** | One reviewer, standard process |
| 7-9 | **Medium** | One reviewer with domain expertise, test evidence required |
| 10-12 | **High** | Two reviewers, one must be senior/staff, integration test required |
| 13-16 | **Critical** | Two reviewers + tech lead sign-off, deploy plan, rollback plan, staging validation |

Include the risk score in your review summary:

```
**Risk Assessment**: Medium (Score: 8 — Scope: 2, Data: 2, Reversibility: 2, Blast: 2)
```

---

## 9. Approval Recommendation

After completing the relevant checklist sections, issue one of the following:

### APPROVE

Issue when:
- All applicable items are PASS or N-A.
- Any WARN items have been acknowledged by the author or are documented risks.
- Risk level is Low or Medium with no outstanding concerns.

### REQUEST_CHANGES

Issue when:
- Any item is FAIL.
- Risk level is High or Critical without adequate test coverage or rollback plan.
- A data contract is missing or incomplete for a new public-facing dataset.
- Cost impact has not been assessed for queries touching large tables.

### COMMENT

Issue when:
- All items pass but you have suggestions for improvement that should not block the merge.
- You are not the required domain expert reviewer and want to add context.
- You have questions that need answers before you can make a final recommendation.

---

## Quick Reference: Minimum Review Standards

For any DE pull request to be merged, it must at minimum:

1. Have at least one PASS on test coverage (items 1.7-1.10).
2. Have no FAIL items unresolved.
3. Include a risk assessment score.
4. Have the required number of approvals based on risk level.
5. Have a PR description that explains the change and its motivation.
6. Have no FAIL items in the Security section (items 6.1-6.8).
7. Have query cost results documented if the PR touches SQL queries (item 7.1).

No exceptions. If the CI pipeline does not enforce these, the reviewer must.
