# Sample Scenario Report

This report compares representative outputs produced **with the skill** versus **without the skill** using the repository's benchmark fixtures:

- With skill: `tests/captured_responses/`
- Without skill: `tests/benchmark/no_skill/`
- Benchmark contract: `tests/benchmark/contract/v2.json`

## Scope

The comparison focuses on five representative scenarios across different operating modes:

1. `TC-E2E-001` — DESIGN mode
2. `TC-E2E-005` — AIRFLOW reliability review
3. `TC-E2E-012` — DATA_QUALITY mode
4. `TC-E2E-018` — SPARK skew mitigation
5. `TC-E2E-024` — deploy strategy and rollback

These scenarios were chosen because they show the main differences the skill introduces:

- stronger structure
- more production-safe recommendations
- clearer operational follow-through
- better template/runbook grounding
- higher specificity under the same task framing

## Aggregate Benchmark Summary

From the full 30-case benchmark:

| Metric | With Skill | Without Skill | Delta |
|---|---:|---:|---:|
| Pass count | 30 | 23 | +7 |
| Required coverage avg | 1.000 | 0.892 | +0.108 |
| Any-group coverage avg | 1.000 | 0.861 | +0.139 |
| Rubric total avg | 73.02 | 60.97 | +12.05 |
| Correctness avg | 4.82 | 4.15 | +0.67 |
| Safety avg | 2.53 | 1.87 | +0.67 |
| Actionability avg | 4.13 | 3.56 | +0.58 |
| Cost awareness avg | 2.47 | 1.70 | +0.77 |
| Testability avg | 2.23 | 1.37 | +0.87 |
| Clarification quality avg | 3.58 | 2.60 | +0.98 |

## Scenario 1: DESIGN Mode

**Case:** `TC-E2E-001`

**Prompt:** Design a daily Salesforce to warehouse pipeline for 20M rows/day with 2-hour SLA.

**Benchmark result**

| Mode | Pass | Rubric Total |
|---|---:|---:|
| With skill | PASS | 74.00 |
| Without skill | FAIL | 58.96 |

**With skill**

- Recommends a specific batch EL architecture
- Calls out object storage landing, warehouse staging, and mart flow
- Explicitly requires idempotent partition loads
- Produces data contract and runbook follow-through

**Without skill**

- Recommends a reasonable batch architecture
- Stops at high-level extraction and staging guidance
- Omits the data contract deliverable
- Omits the runbook deliverable
- Omits explicit idempotency language

**Why the skill wins**

The skill converts a generic architecture answer into an implementation-grade design package. The biggest difference is not correctness of direction, but completeness of production requirements.

**Observed gap**

- No-skill failed because it missed `data contract`, `runbook`, and `idempot` coverage.

## Scenario 2: AIRFLOW Reliability Review

**Case:** `TC-E2E-005`

**Prompt:** Review this DAG for reliability: uses `datetime.now()`, no retries, and bare INSERT into target table.

**Benchmark result**

| Mode | Pass | Rubric Total |
|---|---:|---:|
| With skill | PASS | 70.10 |
| Without skill | FAIL | 62.00 |

**With skill**

- Flags `datetime.now()` as nondeterministic scheduling behavior
- Flags bare `INSERT` as non-idempotent
- Requires retry and backoff defaults
- Tells the operator to rerun the DAG review template and resolve all `FAIL` items
- Anchors the review to PASS/FAIL review semantics

**Without skill**

- Correctly identifies the same technical issues
- Recommends fixing idempotency and retry configuration
- Does not convert the answer into a structured review artifact
- Does not produce explicit PASS/FAIL review framing

**Why the skill wins**

The no-skill answer is technically competent, but it behaves like advice. The skill behaves like a review process with gates.

**Observed gap**

- No-skill failed because it missed the expected review language such as `dag review`, `pass`, or `fail`.

## Scenario 3: DATA_QUALITY Mode

**Case:** `TC-E2E-012`

**Prompt:** Design data quality checks for my orders fact table and define what to do on failures.

**Benchmark result**

| Mode | Pass | Rubric Total |
|---|---:|---:|
| With skill | PASS | 67.28 |
| Without skill | FAIL | 59.98 |

**With skill**

- Covers freshness, completeness, uniqueness, and validity/referential integrity
- Explicitly discusses failure actions: fail, alert, quarantine, or log
- Tells the user to publish a recurring Data Quality Report
- Connects operational response to reporting artifacts

**Without skill**

- Covers freshness, completeness, and uniqueness
- Includes alerting and quarantine language
- Stays generic and does not carry the solution into a formal DQ reporting workflow
- Misses explicit validity/integrity framing

**Why the skill wins**

The skill broadens DQ from “add checks” into “run a governed control system with failure policy and reporting.”

**Observed gap**

- No-skill failed because it missed the `validity/integrity` dimension and the `data quality report` output expectation.

## Scenario 4: SPARK Skew Mitigation

**Case:** `TC-E2E-018`

**Prompt:** My Spark join is skewed on `customer_id` and shuffle is huge. How should I fix it?

**Benchmark result**

| Mode | Pass | Rubric Total |
|---|---:|---:|
| With skill | PASS | 75.64 |
| Without skill | PASS | 57.18 |

**With skill**

- Treats the case as a production incident analysis
- Quantifies the skew and explains why one reducer becomes the bottleneck
- Prioritizes solutions: broadcast join first, salting fallback, AQE always on
- Includes concrete Spark config and code examples
- Adds monitoring, rollout, fallback, and documentation next steps

**Without skill**

- Identifies skew correctly
- Recommends repartitioning, broadcast joins, and adaptive execution
- Does not quantify trade-offs or operational limits
- Does not provide detailed implementation or decision ordering

**Why the skill wins**

Both answers are directionally correct. The skill answer is significantly more useful because it tells the operator exactly which mitigation to try first, what threshold matters, and what to do if the first fix stops working later.

**Observed gap**

- This is a good example of a case where no-skill passes, but still behaves more like a checklist than a production playbook.

## Scenario 5: Canary Deploy + Rollback

**Case:** `TC-E2E-024`

**Prompt:** Define a safe production deployment strategy with canary and rollback.

**Benchmark result**

| Mode | Pass | Rubric Total |
|---|---:|---:|
| With skill | PASS | 76.04 |
| Without skill | PASS | 64.78 |

**With skill**

- Defines a 5% canary with explicit promotion conditions
- Lists SLO guardrails and rollback triggers
- Provides implementation examples for routing and rollback
- Includes a runbook with pre-deploy checklist, deploy steps, rollback procedure, and promotion gates
- Treats deployment as an operational control problem

**Without skill**

- Recommends phased rollout, monitoring, and rollback preparation
- Identifies canary as a safer pattern
- Leaves the actual deploy process at a strategic level
- Does not provide the same guardrail thresholds or runnable workflow

**Why the skill wins**

The no-skill response is acceptable guidance. The skill response is closer to something an on-call engineer could actually run.

## Cross-Scenario Findings

### What the skill consistently improves

- **Operational completeness**: the skill includes contracts, runbooks, checklists, guardrails, and reporting outputs.
- **Decision discipline**: the skill tends to choose a specific path instead of listing options equally.
- **Production safety**: idempotency, retries, rollback, and trust-boundary handling appear more reliably.
- **Follow-through**: next steps are more execution-ready and usually tied to artifacts or templates.

### What no-skill still does reasonably well

- Basic architectural direction
- Surface-level issue identification
- Common best-practice recommendations
- Concise summaries for familiar problems

### Where no-skill breaks down

- Missing expected deliverables such as data contracts, reports, or templates
- Weaker review/process framing
- Less explicit failure policy and operational governance
- Lower specificity in implementation order, thresholds, and escalation mechanics

## Recommendation

Use the skill by default when:

- the task affects production systems
- the output should become an artifact someone will execute
- the task includes code review, reliability review, or incident response
- the answer must include operational controls, not just technical advice

Without-skill responses are still useful for:

- quick brainstorming
- lightweight ideation
- rough first-pass direction before converting into a governed plan

## Bottom Line

The core pattern across these scenarios is stable:

- **without the skill**, the model usually gives competent advice
- **with the skill**, the model behaves more like a production reviewer/operator

That is the real value of this repo. It does not merely improve answer quality in the abstract; it increases the probability that the output is safe to operationalize.
