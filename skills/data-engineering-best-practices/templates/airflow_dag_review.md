---
title: "DAG Review Output"
description: "Template for structured Airflow DAG review findings"
tags: [airflow, dag-review, template]
---

# DAG Review: {DAG_ID}

**Reviewer:** {REVIEWER}
**Date:** {DATE}
**DAG File:** {FILE_PATH}
**Verdict:** {APPROVE | REQUEST_CHANGES | COMMENT}

## Review Summary

| Metric | Value |
|--------|-------|
| Total items checked | {N} |
| PASS | {N} |
| FAIL | {N} |
| WARN | {N} |
| N/A | {N} |
| Risk level | {LOW / MEDIUM / HIGH / CRITICAL} |

## Detailed Findings

| # | Section | Item | Status | Note |
|---|---------|------|--------|------|
| 1 | Idempotency | Tasks produce same result on re-run | {PASS/FAIL/WARN/N-A} | {details} |
| 2 | Idempotency | Uses MERGE or DELETE+INSERT (not bare INSERT) | {PASS/FAIL/WARN/N-A} | {details} |
| 3 | Idempotency | Partition overwrite uses `write_disposition=WRITE_TRUNCATE` with partition decorator | {PASS/FAIL/WARN/N-A} | {details} |
| 4 | Retries | `retries` is set (≥ 2 for external calls) | {PASS/FAIL/WARN/N-A} | {details} |
| 5 | Retries | `retry_delay` uses exponential backoff | {PASS/FAIL/WARN/N-A} | {details} |
| 6 | Retries | `retry_exponential_backoff=True` for external calls | {PASS/FAIL/WARN/N-A} | {details} |
| 7 | Retries | `max_retry_delay` is set and reasonable | {PASS/FAIL/WARN/N-A} | {details} |
| 8 | Retries | `execution_timeout` is set on all tasks | {PASS/FAIL/WARN/N-A} | {details} |
| 9 | Scheduling | Uses `{{ ds }}` / `{{ data_interval_start }}` for date logic | {PASS/FAIL/WARN/N-A} | {details} |
| 10 | Scheduling | No `datetime.now()` or `date.today()` in task logic | {PASS/FAIL/WARN/N-A} | {details} |
| 11 | Scheduling | `catchup` is explicitly set (True or False with reason) | {PASS/FAIL/WARN/N-A} | {details} |
| 12 | Scheduling | `start_date` is static (not `days_ago()`) | {PASS/FAIL/WARN/N-A} | {details} |
| 13 | Sensors | Sensors have `timeout` set | {PASS/FAIL/WARN/N-A} | {details} |
| 14 | Sensors | Sensors use `mode='reschedule'` for long waits (>5 min) | {PASS/FAIL/WARN/N-A} | {details} |
| 15 | Sensors | Sensors have `soft_fail=True` if non-critical | {PASS/FAIL/WARN/N-A} | {details} |
| 16 | Separation | No business logic in DAG file (SQL in .sql files, transforms in modules) | {PASS/FAIL/WARN/N-A} | {details} |
| 17 | Separation | DAG file only defines structure and dependencies | {PASS/FAIL/WARN/N-A} | {details} |
| 18 | Connections | Uses Airflow connections/variables (no hardcoded credentials) | {PASS/FAIL/WARN/N-A} | {details} |
| 19 | Connections | Secrets managed via Secret Backend (not Airflow Variables for sensitive data) | {PASS/FAIL/WARN/N-A} | {details} |
| 20 | Observability | `on_failure_callback` is configured | {PASS/FAIL/WARN/N-A} | {details} |
| 21 | Observability | Row count / data quality checks exist | {PASS/FAIL/WARN/N-A} | {details} |
| 22 | Observability | SLA / `sla_miss_callback` is configured for critical paths | {PASS/FAIL/WARN/N-A} | {details} |
| 23 | Dependencies | Task dependencies are correct (no circular, no missing) | {PASS/FAIL/WARN/N-A} | {details} |
| 24 | Dependencies | `trigger_rule` is appropriate for each task | {PASS/FAIL/WARN/N-A} | {details} |
| 25 | Performance | No top-level code that runs at DAG parse time | {PASS/FAIL/WARN/N-A} | {details} |
| 26 | Performance | Heavy imports are inside task callables, not at module level | {PASS/FAIL/WARN/N-A} | {details} |
| 27 | Documentation | DAG has `doc_md` or meaningful `description` | {PASS/FAIL/WARN/N-A} | {details} |
| 28 | Documentation | `tags` are set for filtering in Airflow UI | {PASS/FAIL/WARN/N-A} | {details} |

## Critical Issues (FAIL)

{List each FAIL item with:}
- **Item #{N}: {Item name}**
  - **Finding:** {What was found}
  - **Impact:** {Why this is a problem}
  - **Fix:** {Specific code change to resolve}

## Warnings (WARN)

{List each WARN item with:}
- **Item #{N}: {Item name}**
  - **Finding:** {What was found}
  - **Recommendation:** {Suggested improvement}

## Suggested Code Changes

```python
# For each FAIL/WARN with a code fix, show the before → after
# === Item #{N}: {description} ===
# BEFORE:
{original code}

# AFTER:
{fixed code}
```

## Approval Recommendation

**Verdict:** {APPROVE / REQUEST_CHANGES / COMMENT}

**Rationale:**
{1-2 sentences explaining the verdict}

**Blocking issues:** {count} FAIL items that must be resolved before merge.
**Non-blocking suggestions:** {count} WARN items recommended for improvement.
