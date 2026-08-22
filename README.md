# Data Engineering Skill

[![Version](https://img.shields.io/badge/version-6.0.0-blue)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![skills.sh](https://skills.sh/b/madhukoseke/de-skills)](https://skills.sh/madhukoseke/de-skills)

`data-engineering` is one vendor-neutral agent skill for designing, building,
reviewing, operating, and modernizing production data systems. SQL, Python, dbt,
Spark, streaming, modeling, governance, and platform engineering are domains
routed inside the skill—not separate skills competing for activation.

The project does not call itself “the best” on aspiration alone. Releases are
judged against published safety, architecture, operations, evidence, trigger,
context, and concision gates. See [Quality](#how-quality-is-proven).

## What the skill does

The six intent workflows are:

| Workflow | Outcome |
| --- | --- |
| `GUIDE` | A bounded explanation or recommendation |
| `DESIGN` | An architecture, model, contract, pipeline, or platform design |
| `BUILD` | Repository-scoped implementation or refactoring with validation |
| `REVIEW` | Findings on code, SQL, DAGs, contracts, designs, or pull requests |
| `OPERATE` | Diagnosis, recovery, reconciliation, or a safe backfill plan |
| `MODERNIZE` | Migration, dual-run, cutover, and decommissioning |

It inspects available artifacts before asking discoverable questions, loads a
small task-specific reference set, and reports evidence and unresolved risk.
Production writes, deployments, destructive migrations, credential changes,
and live backfills require explicit authorization and a verified rollback path.

## Install and use

Install the `skills/data-engineering` directory with any client implementing the
[Agent Skills specification](https://agentskills.io/specification). With the
Skills CLI:

```bash
npx skills add madhukoseke/de-skills --skill data-engineering
```

Then ask the agent directly, for example:

```text
Use $data-engineering to design a replayable CDC pipeline for 4 TB/day with a
30-minute freshness SLO and regional residency constraints.
```

Raw API consumers can build named context bundles:

```bash
python3 scripts/build_bundles.py
python3 scripts/build_bundles.py --profile streaming --out-dir /tmp/de-bundle
```

`core` includes only the routing contract. Other profiles compose it with the
references relevant to architecture, batch, streaming, analytics, reliability,
governance, platform, or ML/AI workloads.

## Repository architecture

```text
skills/data-engineering/
├── SKILL.md                 # canonical behavior contract
├── agents/openai.yaml       # thin product adapter
├── references/              # progressively disclosed knowledge
├── assets/                  # output templates and schemas
└── scripts/                 # deterministic, non-production utilities
integrations/                # dated provider notes and bundle profiles
scripts/                     # repository build and release tooling
tests/                       # structure, fixtures, evals, and benchmark gates
```

The skill directory is the canonical installable package. Repository docs and
generated bundles link to it; they do not define competing copies of rules.

## How quality is proven

Version 6 uses benchmark v4: 48 scenarios over twelve lifecycle domains, 80
activation prompts, deterministic artifact and forbidden-action checks, and a
rubric for architecture, consumer fit, safety, replayability, operations,
security, cost, migration safety, evidence, and concision.

Release gates are:

- zero critical data-loss, security, or unsafe-production-action failures;
- at least 95% trigger precision and recall;
- at least 90% deterministic scenario pass rate and 4.2/5 expert score;
- at least ten points over the no-skill baseline;
- median of at most three loaded references per task; and
- at most 2× baseline output tokens for bounded tasks.

Offline validation runs on pull requests. Live, identical-model comparisons
against v5 and no-skill baselines are nightly or manual and must be published
before a release is described as benchmark-qualified.

```bash
python3 -m pip install -r tests/requirements.txt
tests/run_e2e_harness.sh
```

## How experts contribute

Contributions need a domain owner, source evidence, a decision record for
architectural changes, tests, and a current verification date for product-
specific guidance. Start with [CONTRIBUTING.md](CONTRIBUTING.md). The source
catalog and licensing boundaries are in
[foundations-and-sources.md](skills/data-engineering/references/foundations-and-sources.md).

## License

Apache License 2.0. Source material is synthesized; external books and standards
remain governed by their own licenses. See [LICENSE](LICENSE).
