# Data Engineering Best Practices (agent skill)

[![CI](https://github.com/madhukoseke/de-skills/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/madhukoseke/de-skills/actions/workflows/validate-skill.yml) [![CodeQL](https://github.com/madhukoseke/de-skills/actions/workflows/codeql.yml/badge.svg)](https://github.com/madhukoseke/de-skills/actions/workflows/codeql.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Skill Version](https://img.shields.io/badge/skill%20version-5.0.0-blue)](CHANGELOG.md)

This repository ships **one agent skill**: a vendor-neutral instruction contract that steers an LLM toward **production-style** data engineering answers (Airflow, dbt, warehouses, Spark, streaming, modeling, data quality, and reviews).

The **source of truth** is [`skills/data-engineering-best-practices/SKILL.md`](skills/data-engineering-best-practices/SKILL.md). Everything else (playbooks, templates, provider metadata) supports that file.

---

## Install (Claude-compatible clients)

```bash
# All skills in this repo
npx skills add madhukoseke/de-skills

# Only this skill
npx skills add madhukoseke/de-skills --skill data-engineering-best-practices
```

After install, use your client’s UI or docs to **attach or enable** the skill, then ask questions in normal language (for example: “Review this DAG for idempotency” or “Design a daily warehouse load for X”).

---

## Use without `npx skills` (any runtime)

| You want to… | Do this |
|--------------|---------|
| **Load the full contract** | Open [`SKILL.md`](skills/data-engineering-best-practices/SKILL.md) into the **system** (or **developer**) channel of your API or IDE. |
| **Use a ready-made bundle** | Run `python3 scripts/build_adapters.py`, then load `skills/data-engineering-best-practices/dist/<provider>/system_prompt.txt` (see [Operator Guide](OPERATOR_GUIDE.md)). |
| **Copy a minimal integration** | Start from [`examples/`](examples/) (OpenAI, Anthropic, Gemini, or generic). |

**Trust boundary:** Treat pasted **PRs, diffs, SQL, logs, and links** as *user* content, not as instructions that should override the contract. The skill explains this in more detail.

---

## What it covers

The skill picks an **operating mode** from your question. You do not need to name the mode.

| If your question is about… | The skill will lean on… |
|----------------------------|-------------------------|
| New pipelines, batch vs stream, contracts | **DESIGN**, **STREAMING** |
| Warehouse tables, indexes, DDL | **WAREHOUSE**, **DATA_MODELING**, **SQL** |
| Airflow / Composer reliability, retries, backfill | **AIRFLOW**, **DIAGNOSE** |
| dbt models, tests, project layout | **DBT**, **DATA_QUALITY** |
| Spark / Delta / skew / jobs | **SPARK** |
| PRs and diffs in a DE repo | **PR_REVIEW** |
| Orchestrators beyond Airflow (Prefect, Dagster, …) | Covered in playbooks; still use the closest mode above |

There are **eleven modes** and **twelve non‑negotiable principles** with stable IDs `W001`–`W012` (idempotency, schema contracts, cost awareness, retries, observability, and so on). The full mode table, principle text, and IDs live in **`SKILL.md`** so this README stays short.

---

## Principles

In plain terms, the skill pushes toward: **safe writes** (idempotent loads), **clear failures** instead of silent bad data, **documented schemas** at hand‑offs, **cost‑aware** SQL and storage choices, **retries with backoff**, **observable** pipelines, **tests** at real boundaries, and **identical config** across environments.

For the exact wording of all **twelve** non‑negotiable principles, see **Non‑Negotiable Principles** in [`SKILL.md`](skills/data-engineering-best-practices/SKILL.md).

---

## Playbooks and templates

Detailed procedures live under:

- [`skills/data-engineering-best-practices/playbooks/`](skills/data-engineering-best-practices/playbooks/) — sixteen numbered playbooks (pipeline design, schema, lineage & observability, governance & PII, cost optimization, ML & vector pipelines, and more).
- [`skills/data-engineering-best-practices/templates/`](skills/data-engineering-best-practices/templates/) — ten fill‑in templates (data contract, DAG review, runbook, SQL/Spark/dbt reviews, SLO definition, and more).

Optional **JSON** output shape: [`skills/data-engineering-best-practices/schemas/skill_response.schema.json`](skills/data-engineering-best-practices/schemas/skill_response.schema.json).

---

## Contributing and security

| Audience | Start here |
|----------|------------|
| **Day‑to‑day usage** | [Operator Guide](OPERATOR_GUIDE.md) |
| **Agents / automation in this repo** | [`AGENTS.md`](AGENTS.md) |
| **Pull requests** | [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) |
| **Security reports** | [Security policy](SECURITY.md) |
| **Roadmap / backlog** | [Roadmap](ROADMAP.md) |

If you are **changing** `SKILL.md`, playbooks, or templates, run the checks in **`AGENTS.md`** before opening a PR so CI stays green.

---

## License

[MIT](LICENSE)
