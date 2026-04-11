# AGENTS.md

This repository contains a vendor-neutral agent skill package for data engineering workflows.

## Canonical Source

- `skills/data-engineering-best-practices/SKILL.md` is the source of truth.
- `playbooks/` and `templates/` elaborate on the canonical contract.
- `agents/` contains thin product-specific adapter metadata derived from the canonical skill.

## Working Rules

- Keep `SKILL.md`, playbooks, and templates vendor-neutral.
- Put provider-specific behavior in adapter files such as `skills/data-engineering-best-practices/agents/openai.yaml` or repo-level agent docs.
- If you change modes, principles, playbook paths, or template paths, update all references in `SKILL.md`, docs, and validation scripts together.
- Regenerate adapter artifacts after changing the canonical skill or provider metadata.

## Validation

Run these from repo root before shipping changes:

```bash
python3 tests/validate_vendor_neutrality.py
python3 tests/validate_skill_structure.py
python3 scripts/build_adapters.py --check
python3 tests/validate_adapters.py
python3 tests/validate_provider_fixtures.py
python3 -m py_compile examples/*.py tests/benchmark/live/providers/*.py
tests/run_e2e_harness.sh
tests/benchmark/run_skill_vs_no_skill.sh
```
