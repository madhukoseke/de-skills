# Roadmap

This file tracks remaining production-grade work for the multi-provider skill package.

## Next

- Add end-to-end live API smoke tests behind opt-in credentials so recorded fixtures are backed by real provider responses in CI or scheduled jobs.
- Add artifact publishing beyond GitHub workflow artifacts if you want downloadable release assets or package-registry distribution.
- Add explicit benchmark calibration for provider-specific wrappers if cross-provider formatting variance becomes material.

## Later

- Add signed release metadata for generated `dist/` artifacts.
- Add provider rate-limit/backoff handling and retry policies to the live benchmark transports.
- Add richer examples for SDK-based integrations, not just raw HTTP examples.
- Add optional JSON output contracts for consumers that want machine-parseable recommendations.
- Add per-provider token-budget guidance and automatic contract truncation safeguards for smaller models.

## Open Questions

- Whether generated `dist/` artifacts should always be committed or only published in release workflows.
- Whether provider adapters should stay YAML-only or also emit normalized JSON for downstream tooling.
- Whether the live benchmark should compare cross-provider performance on a single canonical prompt suite or maintain provider-tuned prompt wrappers.
