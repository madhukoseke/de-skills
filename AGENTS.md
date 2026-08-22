# AGENTS.md

This repository contains one vendor-neutral data-engineering agent skill.

## Canonical source

- `skills/data-engineering/SKILL.md` defines behavior and routing.
- `skills/data-engineering/references/` contains progressively disclosed domain knowledge.
- `skills/data-engineering/assets/` contains reusable output forms and schemas.
- `skills/data-engineering/scripts/` contains deterministic, non-production utilities.
- `integrations/` contains dated provider metadata and bundle composition profiles.

Keep the canonical package vendor-neutral. When workflows, principles, reference
paths, or schemas change, update direct links, evaluation contracts, and generated
bundles together. Do not duplicate authoritative rule text in repository docs.

## Validation

Run from repository root:

```bash
python3 -m pip install -r tests/requirements.txt
python3 scripts/build_bundles.py
tests/run_e2e_harness.sh
python3 scripts/build_bundles.py --check
python3 scripts/package_release.py --out-dir /tmp/de-skills-release
python3 tests/validate_release_package.py --release-dir /tmp/de-skills-release
```
