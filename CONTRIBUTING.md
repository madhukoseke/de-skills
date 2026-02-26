# Contributing to de-skills

Thank you for your interest in contributing. This document provides guidance for proposing changes and maintaining the skill structure.

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
- Ensure any new template is referenced from SKILL.md and the relevant playbook(s).

## Updating References

When adding or renaming playbooks or templates:

1. Update the Playbook Index and Template Index in [SKILL.md](skills/data-engineering-best-practices/SKILL.md).
2. Update any `related_templates` in affected playbooks.
3. Add the new file path to [.github/workflows/validate-skill.yml](.github/workflows/validate-skill.yml) if it should be required.
4. Document the change in [CHANGELOG.md](CHANGELOG.md).

## Version History

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.
