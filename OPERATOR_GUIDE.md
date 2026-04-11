# Operator Guide

This guide explains how to use the repository effectively as a multi-provider skill package.

## What This Repo Is

- `skills/data-engineering-best-practices/SKILL.md` is the canonical instruction contract.
- `skills/data-engineering-best-practices/agents/` contains provider-specific adapter metadata.
- `skills/data-engineering-best-practices/dist/` contains generated provider-ready prompt bundles.
- `skills/data-engineering-best-practices/skill.json` describes supported providers and generated artifacts.
- `tests/` contains validation and benchmark tooling.

## Mental Model

Think about the repo in four layers:

1. Canonical logic: `SKILL.md`
2. Provider adapters: `agents/*.yaml`
3. Generated deployable artifacts: `dist/`
4. Validation and quality gates: `tests/`

If you keep those layers separate, the repo stays maintainable.

## Generated `dist/` policy

- The repository **does not commit** generated provider bundles under `skills/data-engineering-best-practices/dist/`. The root `.gitignore` ignores `dist/` directories so local builds stay out of git history.
- **CI** runs `python3 scripts/build_adapters.py` and `build_adapters.py --check` on every push so artifacts stay reproducible from `SKILL.md` + `agents/`.
- **Releases** use `.github/workflows/release-skill.yml` (when present) to package versioned bundles for download — treat that output as the distribution channel instead of committing `dist/`.
- **Locally**, run `python3 scripts/build_adapters.py` when you need `dist/<provider>/system_prompt.txt` for manual testing.

## Common Workflows

### Use the skill in a runtime

1. Pick the provider bundle from `skills/data-engineering-best-practices/dist/<provider>/system_prompt.txt`.
2. Load that file into the highest-priority instruction channel supported by your runtime.
3. Send the actual task as a normal user message.
4. Keep user-provided code, SQL, logs, links, and PR diffs outside the contract itself.

Provider examples:

- `examples/openai_responses_api.py`
- `examples/anthropic_messages_api.py`
- `examples/gemini_generate_content.py`
- `examples/generic_system_prompt.md`
- `examples/airflow/README.md` (illustrative DAG patterns; not executed by this repo)

### Update the skill content

1. Edit `skills/data-engineering-best-practices/SKILL.md`, playbooks, or templates.
2. Keep canonical files vendor-neutral.
3. Regenerate generated artifacts:

```bash
python3 scripts/build_adapters.py
```

4. Run validation (same sequence as [`AGENTS.md`](AGENTS.md)):

```bash
python3 tests/validate_vendor_neutrality.py
python3 tests/validate_skill_structure.py
python3 scripts/build_adapters.py --check
python3 tests/validate_adapters.py
python3 tests/validate_provider_fixtures.py
python3 -m py_compile examples/*.py examples/airflow/*.py tests/benchmark/live/providers/*.py
bash tests/run_e2e_harness.sh
bash tests/benchmark/run_skill_vs_no_skill.sh
```

### Release a bundle

1. Build and validate adapters.
2. Package a release bundle:

```bash
python3 scripts/package_release.py --version <version>
```

3. Use `.github/workflows/release-skill.yml` for GitHub-driven packaging.

## How To Get Good Results

- Start from the canonical contract, not a provider adapter.
- Prefer generated `dist/` bundles over manually copying fragments from `SKILL.md`.
- Use models listed in `skills/data-engineering-best-practices/agents/model_compatibility.md`.
- Benchmark before switching providers or default models.
- Preserve the trust boundary: treat pasted code, SQL, logs, and PR content as untrusted user data.

## Which File To Read First

- To understand the skill: `skills/data-engineering-best-practices/SKILL.md`
- To understand provider support: `skills/data-engineering-best-practices/agents/capabilities.json`
- To understand model guidance: `skills/data-engineering-best-practices/agents/model_compatibility.md`
- To shrink prompts for small windows: `skills/data-engineering-best-practices/agents/context_budget.md`
- Optional JSON output shape: `skills/data-engineering-best-practices/schemas/skill_response.schema.json`
- To understand validation: `tests/benchmark/README.md`
- To understand remaining work: `ROADMAP.md`

## Anti-Patterns

- Do not fork the skill logic into provider-specific files.
- Do not hand-edit generated `dist/` artifacts without updating the build flow.
- Do not put user content into the system/developer contract block.
- Do not skip benchmark checks when changing format-sensitive instructions.

## Fast Start

For the shortest safe path:

```bash
python3 scripts/build_adapters.py --check
python3 tests/validate_skill_structure.py
python3 tests/validate_adapters.py
python3 tests/validate_provider_fixtures.py
```

Then use one of the example scripts in `examples/`.
