# Contributing to de-skills

Thank you for your interest in contributing. This document provides guidance for proposing changes and maintaining the skill structure.

## Scope

Contributions that are welcome:
- Fixes to incorrect, outdated, or misleading content in playbooks or templates
- New playbooks for data engineering patterns not yet covered
- New templates for modes that lack structured output
- New agent adapter metadata under `skills/data-engineering-best-practices/agents/`
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

The canonical skill lives under `skills/data-engineering-best-practices/`:

```
skills/data-engineering-best-practices/
├── SKILL.md              # Canonical entry point — required frontmatter: name, description
├── agents/               # Product-specific adapter metadata (for example openai.yaml)
├── playbooks/            # Procedural guidance (numbered for ordering)
└── templates/            # Output templates (YAML, Markdown)
```

### SKILL.md Requirements

- **Frontmatter:** Must include `name` and `description` (required by agent skill loaders).
- **Optional:** `metadata.version`, `metadata.tags`, `license`.
- **Links:** Use paths relative to the skill root (e.g. `playbooks/01_pipeline_design.md`, `templates/runbook.md`).
- **Vendor neutrality:** Do not mention specific model providers or products in `SKILL.md`, playbooks, or templates unless the file is explicitly an adapter artifact under `agents/`.

### Agents

- Use `agents/` only for product-specific metadata or thin adapter files derived from the canonical skill.
- Do not fork the domain guidance across adapters; `SKILL.md` remains the source of truth.
- If adapter metadata becomes stale after updating `SKILL.md`, regenerate or update it in the same change.
- After changing canonical skill content or provider metadata, run `python3 scripts/build_adapters.py --check` before opening a PR. Generated `dist/` bundles are **not committed** (see `OPERATOR_GUIDE.md`); CI regenerates them for validation.
- `agents/model_compatibility.md` is **hand-curated**. When you refresh model lists, bump the `Last reviewed` / `Next review due` dates at the top of that file in the same PR.

### Playbooks

- Use numbered prefixes for ordering (`01_`, `02_`, etc.).
- Include YAML frontmatter with `title`, `description`, `tags`.
- Cross-reference templates with `../templates/<name>`.
- Reference SKILL.md with `../SKILL.md` when tying back to principles.

### Templates

- Keep templates self-contained and fillable (placeholders like `{PIPELINE_NAME}`).
- Markdown templates should include YAML frontmatter (`title`, `description`, `tags`) for consistency.
- Ensure any new template is referenced from SKILL.md and the relevant playbook(s).

## Checklist: adding or renaming a playbook

1. Add the markdown file under `skills/data-engineering-best-practices/playbooks/` with the next `NN_` prefix.
2. Update the **Playbook Index** table in `SKILL.md` and any cross-links in README / `tests/e2e_test_cases.md` if applicable.
3. Run `python3 tests/validate_vendor_neutrality.py` — canonical playbooks must stay vendor-neutral.
4. Run `python3 tests/validate_skill_structure.py` — mode and template references must stay consistent.
5. Run `python3 scripts/build_adapters.py --check` and the commands listed in `AGENTS.md`.

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

- Validate adapter manifests and generated artifacts:

```bash
python3 -m pip install -r tests/requirements.txt   # one-time
python3 scripts/build_adapters.py --check
python3 tests/validate_adapters.py
python3 tests/validate_provider_fixtures.py
python3 tests/validate_json_responses.py
python3 tests/validate_release_package.py
```

- Validate example and provider transport scripts:

```bash
python3 -m py_compile examples/*.py tests/benchmark/live/providers/*.py
```

- Run benchmark quality checks (skill vs baseline):

```bash
tests/benchmark/run_skill_vs_no_skill.sh
```

- Run live benchmark (same prompts/model, skill on/off):

```bash
tests/benchmark/live/run_live_benchmark.sh
```

## Security tooling

- **Secret scanning** is enabled at the repository level via GitHub-native secret scanning. No workflow file is required. If you commit a credential by mistake, rotate it immediately and follow [SECURITY.md](SECURITY.md) to report.
- **CodeQL** runs via [.github/workflows/codeql.yml](.github/workflows/codeql.yml) on every PR plus weekly. Open security alerts via the repository **Security** tab.
- Do not commit credentials, API keys, or `.env` files. Stage individual files (`git add path/to/file`) rather than `git add -A` to avoid sweeping in untracked secrets.

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
