# Roadmap (Kanban backlog)

This file tracks production-grade work for the multi-provider skill package. **How to use it:** move cards by cut/paste between the Kanban sections below. Prefer small WIP in **In progress**. Update the **Current sprint** block at the top each iteration.

**ID convention:** `PKG-###` = package / repo infrastructure work (CI, adapters, benchmarks, docs—not canonical skill rewrites tracked here unless they unblock shipping).

---

## Current sprint


| Field      | Value                                                          |
| ---------- | -------------------------------------------------------------- |
| **Sprint** | `2026-S01`                                                     |
| **Dates**  | 2026-04-07 — 2026-04-20 (example; adjust when you run sprints) |
| **Theme**  | Harden live-provider CI and clarify fixture refresh path       |


### Definition of Ready

- Card has **Acceptance criteria** and a **Size**.
- Dependencies named or marked none.
- Linked paths exist or spike is explicitly time-boxed.

### Definition of Done

- Changes merged with checks green; follow [AGENTS.md](AGENTS.md) validation commands when touching skill text, adapters, or tests.
- If canonical skill or `agents/` metadata changed: `python3 scripts/build_adapters.py` run and any generated `dist/` expectations updated per [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md).
- Roadmap card moved to **Done** (or split: done scope here, follow-up card in **Backlog**).

---

## Phases (grouping, not columns)

Use the **Phase** field on each card to plan iterative delivery (e.g. “this sprint only Phase A”).


| Phase | Name                   | Focus                                                             |
| ----- | ---------------------- | ----------------------------------------------------------------- |
| **A** | CI & live providers    | Smoke workflows, secrets, recorded fixtures, provider transports  |
| **B** | Artifacts & releases   | Workflow artifacts, optional registry assets, signing             |
| **C** | Benchmarks & contracts | Cross-provider benchmarks, calibration, machine-parseable outputs |
| **D** | Docs & examples        | Operator/contributor docs, SDK-oriented examples, model budgets   |


---

## In progress

*(Limit to 1–3 cards.)*

---

## Ready

### PKG-001 — Extend live OpenAI smoke: fixtures + refresh path


| Field             | Value                    |
| ----------------- | ------------------------ |
| **ID**            | PKG-001                  |
| **Phase**         | A                        |
| **Priority**      | P1                       |
| **Sprint target** | `2026-S01`               |
| **Size**          | M                        |
| **Owner**         | TBD                      |
| **Area**          | CI, benchmarks, fixtures |
| **Type**          | Feature                  |


**Dependencies:** `OPENAI_API_KEY` available in CI for scheduled/manual runs.  
**Risks:** Fixture drift if provider output format changes; document refresh command.

**Acceptance criteria**

- `.github/workflows/live-provider-smoke.yml` path documented for refreshing recorded fixtures (command + when to run).
- Either automated refresh step in workflow (gated) or explicit checklist in [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) / [tests/benchmark/live/README.md](tests/benchmark/live/README.md).
- Smoke still runs with `--max-cases 1` without breaking main CI.

**Links:** [.github/workflows/live-provider-smoke.yml](.github/workflows/live-provider-smoke.yml), [tests/benchmark/live/](tests/benchmark/live/)

---

## Backlog

### PKG-002 — Artifact publishing beyond workflow artifacts


| Field             | Value        |
| ----------------- | ------------ |
| **ID**            | PKG-002      |
| **Phase**         | B            |
| **Priority**      | P2           |
| **Sprint target** | —            |
| **Size**          | L            |
| **Owner**         | TBD          |
| **Area**          | CI, releases |
| **Type**          | Feature      |


**Dependencies:** Release policy (what gets published, semver).  
**Risks:** Scope creep (registry vs GitHub Releases only).

**Acceptance criteria**

- Documented path for consumers to download release bundles (GitHub Release assets and/or package registry).
- Workflow or release job produces those artifacts from `scripts/build_adapters.py` output.

**Links:** [scripts/build_adapters.py](scripts/build_adapters.py), [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md)

---

### PKG-003 — Benchmark calibration for provider-specific wrappers


| Field             | Value      |
| ----------------- | ---------- |
| **ID**            | PKG-003    |
| **Phase**         | C          |
| **Priority**      | P2         |
| **Sprint target** | —          |
| **Size**          | M          |
| **Owner**         | TBD        |
| **Area**          | benchmarks |
| **Type**          | Feature    |


**Dependencies:** Enough live runs to observe variance.  
**Risks:** Apples-to-oranges comparisons if prompts diverge per provider.

**Acceptance criteria**

- Document when/how to calibrate wrappers in [tests/benchmark/README.md](tests/benchmark/README.md) or live README.
- Optional threshold or baseline file if repo adopts numeric regression gates.

**Links:** [tests/benchmark/](tests/benchmark/), [tests/benchmark/live/](tests/benchmark/live/)

---

### PKG-004 — Signed release metadata for `dist/` artifacts


| Field             | Value              |
| ----------------- | ------------------ |
| **ID**            | PKG-004            |
| **Phase**         | B                  |
| **Priority**      | P3                 |
| **Sprint target** | —                  |
| **Size**          | L                  |
| **Owner**         | TBD                |
| **Area**          | security, releases |
| **Type**          | Feature            |


**Dependencies:** Key management, signing tool choice.  
**Risks:** Maintainer operational burden.

**Acceptance criteria**

- Release pipeline produces signatures and/or SBOM as agreed.
- [SECURITY.md](SECURITY.md) or operator guide documents verification steps.

**Links:** [SECURITY.md](SECURITY.md), [skills/data-engineering-best-practices/dist/](skills/data-engineering-best-practices/dist/)

---

### PKG-005 — Rate limits, backoff, retries on live benchmark transports


| Field             | Value      |
| ----------------- | ---------- |
| **ID**            | PKG-005    |
| **Phase**         | A          |
| **Priority**      | P2         |
| **Sprint target** | —          |
| **Size**          | M          |
| **Owner**         | TBD        |
| **Area**          | benchmarks |
| **Type**          | Feature    |


**Dependencies:** Provider API behavior documented.  
**Risks:** Flaky CI if backoff too aggressive or too weak.

**Acceptance criteria**

- Shared retry/backoff policy for live provider HTTP/SDK calls.
- Documented in benchmark README; CI remains reliable under transient 429/5xx.

**Links:** [tests/benchmark/live/](tests/benchmark/live/)

---

### PKG-006 — Richer SDK-based integration examples


| Field             | Value          |
| ----------------- | -------------- |
| **ID**            | PKG-006        |
| **Phase**         | D              |
| **Priority**      | P2             |
| **Sprint target** | —              |
| **Size**          | M              |
| **Owner**         | TBD            |
| **Area**          | docs, examples |
| **Type**          | Feature        |


**Dependencies:** None.  
**Risks:** SDK churn; pin versions in examples.

**Acceptance criteria**

- At least one additional example under [examples/](examples/) using an official SDK (not only raw HTTP).
- Cross-linked from [README.md](README.md) or [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md).

**Links:** [examples/](examples/)

---

### PKG-007 — Optional JSON output contracts for machine-parseable recommendations


| Field             | Value                   |
| ----------------- | ----------------------- |
| **ID**            | PKG-007                 |
| **Phase**         | C                       |
| **Priority**      | P2                      |
| **Sprint target** | —                       |
| **Size**          | L                       |
| **Owner**         | TBD                     |
| **Area**          | skill contract, schemas |
| **Type**          | Feature                 |


**Dependencies:** Consumer requirements; may align with existing schema.  
**Risks:** Contract versioning and backward compatibility.

**Acceptance criteria**

- Documented JSON shape (extend or complement [skills/data-engineering-best-practices/schemas/skill_response.schema.json](skills/data-engineering-best-practices/schemas/skill_response.schema.json) as appropriate).
- Operator/contributor docs describe how consumers opt in.

**Links:** [skills/data-engineering-best-practices/schemas/skill_response.schema.json](skills/data-engineering-best-practices/schemas/skill_response.schema.json)

---

### PKG-008 — Per-provider token budgets and truncation safeguards


| Field             | Value          |
| ----------------- | -------------- |
| **ID**            | PKG-008        |
| **Phase**         | D              |
| **Priority**      | P2             |
| **Sprint target** | —              |
| **Size**          | L              |
| **Owner**         | TBD            |
| **Area**          | adapters, docs |
| **Type**          | Feature        |


**Dependencies:** [skills/data-engineering-best-practices/agents/context_budget.md](skills/data-engineering-best-practices/agents/context_budget.md) kept in sync.  
**Risks:** Over-truncation hurts answer quality.

**Acceptance criteria**

- Guidance per provider family for safe attachment sizes / truncation order.
- Optional automation or checklist in adapter build or validation scripts if feasible without harming vendor neutrality of canonical skill text.

**Links:** [skills/data-engineering-best-practices/agents/context_budget.md](skills/data-engineering-best-practices/agents/context_budget.md), [scripts/build_adapters.py](scripts/build_adapters.py)

---

### PKG-009 — Decision: YAML-only adapters vs normalized JSON export


| Field             | Value            |
| ----------------- | ---------------- |
| **ID**            | PKG-009          |
| **Phase**         | C                |
| **Priority**      | P3               |
| **Sprint target** | —                |
| **Size**          | S                |
| **Owner**         | TBD              |
| **Area**          | adapters         |
| **Type**          | Decision / Spike |


**Dependencies:** Downstream tooling interviews (if any).  
**Risks:** Maintaining two formats.

**Acceptance criteria**

- Written decision in ADR or `OPERATOR_GUIDE.md` subsection.
- Backlog updated: either close with “YAML only” or spawn implementation card(s).

**Links:** [skills/data-engineering-best-practices/agents/](skills/data-engineering-best-practices/agents/)

---

### PKG-010 — Decision: single canonical benchmark suite vs provider-tuned prompts


| Field             | Value            |
| ----------------- | ---------------- |
| **ID**            | PKG-010          |
| **Phase**         | C                |
| **Priority**      | P3               |
| **Sprint target** | —                |
| **Size**          | S                |
| **Owner**         | TBD              |
| **Area**          | benchmarks       |
| **Type**          | Decision / Spike |


**Dependencies:** PKG-003 insights optional.  
**Risks:** Benchmarks become harder to interpret if mixed strategies.

**Acceptance criteria**

- Documented strategy in [tests/benchmark/README.md](tests/benchmark/README.md).
- Benchmark harness structure matches the decision (one suite or explicit per-provider wrappers with rationale).

**Links:** [tests/benchmark/](tests/benchmark/)

---

### PKG-011 — Anthropic & Gemini parity in live-provider smoke CI


| Field             | Value         |
| ----------------- | ------------- |
| **ID**            | PKG-011       |
| **Phase**         | A             |
| **Priority**      | P2            |
| **Sprint target** | —             |
| **Size**          | M             |
| **Owner**         | TBD           |
| **Area**          | CI, providers |
| **Type**          | Feature       |


**Dependencies:** Repository secrets for `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` (names per workflow convention).  
**Risks:** Cost and flake rate vs OpenAI-only path.

**Acceptance criteria**

- Optional jobs (secret-gated) mirroring OpenAI smoke pattern.
- Documented secret names and how to run locally.

**Links:** [.github/workflows/live-provider-smoke.yml](.github/workflows/live-provider-smoke.yml)

---

### PKG-012 — Normalized JSON export from adapter build


| Field             | Value             |
| ----------------- | ----------------- |
| **ID**            | PKG-012           |
| **Phase**         | C                 |
| **Priority**      | P3                |
| **Sprint target** | —                 |
| **Size**          | M                 |
| **Owner**         | TBD               |
| **Area**          | adapters, tooling |
| **Type**          | Feature           |


**Dependencies:** PKG-009 decision preferred; can prototype behind flag.  
**Risks:** Duplication with YAML source of truth.

**Acceptance criteria**

- `build_adapters.py` (or companion script) emits JSON consumed by documented tooling path.
- Validation step ensures JSON stays in sync in CI if checked in, or JSON is generated-only and documented as such.

**Links:** [scripts/build_adapters.py](scripts/build_adapters.py), [tests/validate_adapters.py](tests/validate_adapters.py)

---

### PKG-013 — Cross-provider benchmark on one canonical prompt suite


| Field             | Value      |
| ----------------- | ---------- |
| **ID**            | PKG-013    |
| **Phase**         | C          |
| **Priority**      | P3         |
| **Sprint target** | —          |
| **Size**          | L          |
| **Owner**         | TBD        |
| **Area**          | benchmarks |
| **Type**          | Feature    |


**Dependencies:** PKG-010; stable case set in [tests/e2e_test_cases.md](tests/e2e_test_cases.md) or benchmark harness.  
**Risks:** Provider capabilities differ; scoring rubric must be fair.

**Acceptance criteria**

- Single shared case list run against N providers with comparable reporting.
- README section explains metrics and limitations.

**Links:** [tests/benchmark/run_skill_vs_no_skill.sh](tests/benchmark/run_skill_vs_no_skill.sh), [tests/e2e_test_cases.md](tests/e2e_test_cases.md)

---

### PKG-014 — First-run guide for JSON / schema-backed consumers


| Field             | Value   |
| ----------------- | ------- |
| **ID**            | PKG-014 |
| **Phase**         | D       |
| **Priority**      | P3      |
| **Sprint target** | —       |
| **Size**          | S       |
| **Owner**         | TBD     |
| **Area**          | docs    |
| **Type**          | Docs    |


**Dependencies:** PKG-007 optional (can document current schema first).  
**Risks:** None significant.

**Acceptance criteria**

- Short “machine-parseable responses” section in operator guide or README linking to schema.
- Example payload or validator pointer.

**Links:** [skills/data-engineering-best-practices/schemas/skill_response.schema.json](skills/data-engineering-best-practices/schemas/skill_response.schema.json), [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md)

---

### PKG-015 — New skill: `csv-best-practices` (vendor-neutral CSV contract)


| Field             | Value                                  |
| ----------------- | -------------------------------------- |
| **ID**            | PKG-015                                |
| **Phase**         | C (tooling) / D (docs & skill content) |
| **Priority**      | P2                                     |
| **Sprint target** | —                                      |
| **Size**          | XL                                     |
| **Owner**         | TBD                                    |
| **Area**          | skills, CI, adapters, docs             |
| **Type**          | Epic                                   |


**Dependencies:** None. Split into follow-up cards if WIP is too large.  
**Risks:** Multi-skill CI and validator refactors touch critical paths; land `build_adapters` / `validate_`* changes with tight review.

**Acceptance criteria**

- New packaged skill at `skills/csv-best-practices/` per detailed plan (canonical `SKILL.md`, eight modes, ten principles, playbooks `01_`–`08_`, templates, `skill.json`, `agents/`*, optional JSON schema).
- `scripts/build_adapters.py`, `tests/validate_skill_structure.py`, `tests/validate_vendor_neutrality.py`, `tests/validate_adapters.py`, and `scripts/package_release.py` generalized for multiple skills under `skills/*/skill.json` without breaking the existing data-engineering skill.
- CI and contributor docs updated so both skills validate and markdownlint covers new paths as needed.
- Long-form spec remains available: repo copy [docs/plans/csv_agent_skill_package.md](docs/plans/csv_agent_skill_package.md) and Cursor plan file `.cursor/plans/csv_agent_skill_package_3167c806.plan.md` (do not delete the Cursor copy when iterating).

**Links:** [docs/plans/csv_agent_skill_package.md](docs/plans/csv_agent_skill_package.md)

---

## Blocked

*(Waiting on secrets, upstream, or explicit decisions.)*

---

## Done

### PKG-100 — Policy: generated `dist/` is not committed


| Field             | Value               |
| ----------------- | ------------------- |
| **ID**            | PKG-100             |
| **Phase**         | B                   |
| **Priority**      | —                   |
| **Sprint target** | (historical)        |
| **Size**          | —                   |
| **Owner**         | —                   |
| **Area**          | releases, CI        |
| **Type**          | Decision (resolved) |


**Outcome:** `dist/` artifacts are generated in CI; releases ship bundles via workflow artifacts. Documented in [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) (Generated `dist/` policy).

**Links:** [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md)

---

## Changelog (this board)


| Date       | Change                                                                                                                                   |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-04-12 | Replaced flat Next/Later/Open Questions with Kanban columns, phases, and card metadata; migrated prior bullets; added PKG-011–014 seeds. |
| 2026-04-12 | Added PKG-015 epic for `csv-best-practices` skill; linked repo plan doc `docs/plans/csv_agent_skill_package.md`.                         |


