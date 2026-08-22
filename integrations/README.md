# Integration profiles

The skill package is provider-neutral. This directory contains optional, dated
integration metadata and named context bundles for raw API consumers.

- `profiles.json` selects `SKILL.md` plus only the references needed for a class
  of work. `core` is the routing contract; `full` is intended for evaluation and
  offline study, not as the default runtime context.
- `providers.yaml` records current model and prompt-caching notes separately
  from durable data-engineering guidance.

Build bundles with `python3 scripts/build_bundles.py`. Reverify provider metadata
against the linked official documentation after its stated verification date.
