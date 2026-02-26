# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a **Claude Code skill** package — not a traditional code project. It contains markdown playbooks, templates, and a SKILL.md entry point that together form the `data-engineering-best-practices` skill for the Google Cloud data engineering stack (BigQuery, Airflow/Composer, Pub/Sub, Dataflow).

There are no build steps, tests, or dependencies. All content is markdown/YAML documentation.

## Architecture

- `skills/data-engineering-best-practices/SKILL.md` — Skill entry point. Defines five operating modes (DESIGN, BQ_MODEL, AIRFLOW, STREAMING, PR_REVIEW), input requirements, output format, and the eight non-negotiable principles.
- `skills/data-engineering-best-practices/playbooks/` — Detailed procedural guidance per domain (pipeline design, BQ modeling/cost, Airflow reliability, streaming/Pub/Sub, PR review checklist). Numbered 01-05.
- `skills/data-engineering-best-practices/templates/` — Fill-in templates output by the skill: data contract (YAML), DAG review, runbook, incident postmortem.

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
