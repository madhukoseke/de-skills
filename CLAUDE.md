# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This repository is a vendor-neutral agent skill package, not a traditional application codebase. The canonical contract is `skills/data-engineering-best-practices/SKILL.md`; Claude-specific behavior should stay in adapter files like this one rather than in the canonical skill content.

There are no build or runtime dependencies. Content is markdown/YAML documentation plus lightweight shell/python validation scripts under `tests/`.

## Architecture

- `skills/data-engineering-best-practices/SKILL.md` — Canonical skill entry point. Defines eleven operating modes (DESIGN, WAREHOUSE, AIRFLOW, STREAMING, PR_REVIEW, DBT, DATA_QUALITY, SQL, SPARK, DATA_MODELING, DIAGNOSE), input requirements, output format, and the twelve non-negotiable principles.
- `skills/data-engineering-best-practices/agents/` — Provider-specific adapter metadata (`openai.yaml`, `anthropic.yaml`, `gemini.yaml`, `generic.yaml`) and capability manifest.
- `skills/data-engineering-best-practices/dist/` — Generated provider-specific contract bundles built from the canonical skill.
- `skills/data-engineering-best-practices/playbooks/` — Detailed procedural guidance per domain, numbered 01–12.
- `skills/data-engineering-best-practices/templates/` — Fill-in templates output by the skill: data contract, DAG review, runbook, incident postmortem, dbt model review, data quality report, SQL review, Spark job review, data model design.
- `tests/` — E2E case definitions, captured-response fixtures, and validation harness scripts.

## Key Conventions

- Playbooks are numbered sequentially (`01_` through `12_`) and referenced by SKILL.md.
- Templates are referenced by both SKILL.md and playbooks; changes to template structure must be reflected in both.
- The twelve non-negotiable principles in SKILL.md are the authoritative source of truth — playbooks elaborate on them but must not contradict them.
- Keep the canonical skill, playbooks, and templates vendor-neutral. Agent-specific instructions belong in adapter files or repo-level docs, not inside the core skill contract.

## Installation

```bash
# Install all packaged skills from this repo in Claude-compatible workflows
npx skills add madhukoseke/de-skills

# Install only the data-engineering skill in Claude-compatible workflows
npx skills add madhukoseke/de-skills --skill data-engineering-best-practices
```
