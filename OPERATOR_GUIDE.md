# Operator guide

The canonical package is `skills/data-engineering`. Install it directly when the
host supports Agent Skills progressive disclosure.

For raw APIs, build a named profile from `integrations/profiles.json`:

```bash
python3 scripts/build_bundles.py --profile reliability
```

Send the resulting `dist/bundles/reliability.txt` as the provider's instruction
context. Put stable bundle text before task-specific content. Provider prompt
channels, current model examples, caching links, and verification dates live in
`integrations/providers.yaml` and must be rechecked before production use.

Do not load `full` by default. Prefer `core` and allow the host to open direct
references, or select the narrowest matching profile. Instrument loaded reference
count and output tokens so benchmark context gates are observable.

Run `tests/run_e2e_harness.sh` after source changes and use the release checklist
in `docs/release-checklist.md` before publishing.
