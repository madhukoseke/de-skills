# Contributing to de-skills

Thank you for your interest in contributing. This document provides guidance for proposing changes and maintaining the skill structure.

## Scope

Contributions that are welcome:
- Fixes to incorrect, outdated, or misleading content in playbooks or templates
- New playbooks for data engineering patterns not yet covered
- New templates for modes that lack structured output
- CI/test harness improvements
- Clarity improvements to existing content

Out of scope (open an issue to discuss first):
- Adding vendor-specific lock-in (e.g., a playbook that only applies to one cloud provider)
- Changes to the 12 non-negotiable principles without a strong technical rationale
- Removing trust boundary guardrails

## How to Contribute

### Proposing Changes

1. **Open an Issue** — For significant changes or new playbooks/templates, open an issue first to discuss the approach.
2. **Submit a Pull Request** — For smaller fixes and clarifications, feel free to open a PR directly.

### Pull Request Process

1. Fork the repository and create a branch from `main`.
2. Make your changes following the skill structure below.
3. Ensure CI passes (frontmatter, file existence checks).
4. Update [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]` for user-facing changes.
5. Submit the PR with a clear description of what changed and why.

## Skill Structure

The skill lives under `skills/data-engineering-best-practices/`:

```
skills/data-engineering-best-practices/
├── SKILL.md              # Entry point — required frontmatter: name, description
├── playbooks/            # Procedural guidance (numbered for ordering)
└── templates/           # Output templates (YAML, Markdown)
```

### SKILL.md Requirements

- **Frontmatter:** Must include `name` and `description` (required by agent skill loaders).
- **Optional:** `metadata.version`, `metadata.tags`, `license`.
- **Links:** Use paths relative to the skill root (e.g. `playbooks/01_pipeline_design.md`, `templates/runbook.md`).

### Playbooks

- Use numbered prefixes for ordering (`01_`, `02_`, etc.).
- Include YAML frontmatter with `title`, `description`, `tags`.
- Cross-reference templates with `../templates/<name>`.
- Reference SKILL.md with `../SKILL.md` when tying back to principles.

### Templates

- Keep templates self-contained and fillable (placeholders like `{PIPELINE_NAME}`).
- Markdown templates should include YAML frontmatter (`title`, `description`, `tags`) for consistency.
- Ensure any new template is referenced from SKILL.md and the relevant playbook(s).

## Playbook Style Guide

When writing or editing a playbook:

- **Lead with a decision rule**, not options. "Use MERGE for dimension tables" not "You can use MERGE or INSERT".
- **Include working code examples** for every pattern. No pseudocode.
- **Reference the relevant principle(s)** from SKILL.md when a rule ties back to one (e.g., "Principle 1: Idempotency first").
- **Anti-patterns table required**: every playbook must have a section listing common anti-patterns with impact and fix.
- **Cross-reference templates**: if the playbook produces a template output, link to it with `../templates/<name>`.
- **Frontmatter required**: `title`, `description`, `tags` at the top of every playbook file.
- **No vendor lock-in**: use generic terms (object storage, warehouse, broker) unless the playbook is explicitly scope-limited.

## Test Harness

- E2E behavior checks live under `tests/`.
- Run full validation before opening a PR:

```bash
tests/run_e2e_harness.sh
```

- Run benchmark quality checks (skill vs baseline):

```bash
tests/benchmark/run_skill_vs_no_skill.sh
```

- Run live benchmark (same prompts/model, skill on/off):

```bash
tests/benchmark/live/run_live_benchmark.sh
```

## Updating References

When adding or renaming playbooks or templates:

1. Update the Playbook Index and Template Index in [SKILL.md](skills/data-engineering-best-practices/SKILL.md).
2. Update any `related_templates` in affected playbooks.
3. Add the new file path to [.github/workflows/validate-skill.yml](.github/workflows/validate-skill.yml) if it should be required.
4. Document the change in [CHANGELOG.md](CHANGELOG.md).

## Version History

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.

## Good First Issues

Looking for a way to contribute but not sure where to start? These are good entry points:

- **Fix a typo or clarity issue** in any playbook — no domain expertise required
- **Add a missing anti-pattern** to the table in any playbook (07_sql_patterns.md and 08_spark_patterns.md both have room)
- **Improve a template** — add a missing field or clarify a placeholder
- **Add a captured response fixture** for a test case that is missing one (`tests/captured_responses/`)

Search for issues labeled `good first issue` on the repository.
