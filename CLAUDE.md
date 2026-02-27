# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a **Claude Code skill** package — not a traditional code project. It contains markdown playbooks, templates, and a SKILL.md entry point that together form the `data-engineering-best-practices` skill for the Google Cloud data engineering stack (BigQuery, Airflow/Composer, Pub/Sub, Dataflow).

There are no build or runtime dependencies. Content is markdown/YAML documentation plus lightweight shell/python validation scripts under `tests/`.

## Architecture

- `skills/data-engineering-best-practices/SKILL.md` — Skill entry point. Defines nine operating modes (DESIGN, BQ_MODEL, AIRFLOW, STREAMING, PR_REVIEW, DBT, DATA_QUALITY, DIAGNOSE, COST_AUDIT), input requirements, output format, and the non-negotiable principles.
- `skills/data-engineering-best-practices/playbooks/` — Detailed procedural guidance per domain, numbered 01-08.
- `skills/data-engineering-best-practices/templates/` — Fill-in templates output by the skill: data contract, DAG review, runbook, incident postmortem, dbt model review, data quality report.
- `tests/` — E2E case definitions, captured-response fixtures, and validation harness scripts.

## Key Conventions

- Playbooks are numbered sequentially (`01_`, `02_`, etc.) and referenced by SKILL.md.
- Templates are referenced by both SKILL.md and playbooks; changes to template structure must be reflected in both.
- The eight non-negotiable principles in SKILL.md are the authoritative source of truth — playbooks elaborate on them but must not contradict them.

## Installation

```bash
# Install all skills from this repo
npx skills add madhukoseke/de-skills

# Install only the data-engineering skill
npx skills add madhukoseke/de-skills --skill data-engineering-best-practices
```
