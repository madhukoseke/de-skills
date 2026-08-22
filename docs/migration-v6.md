# Migrating to v6

Version 6.0.0 is intentionally breaking. The installable skill moved from
`data-engineering-best-practices` to `data-engineering`; no compatibility alias is
shipped because no tagged release or visible public adoption existed.

Update installations, explicit invocations, and repository paths. Replace the
eleven technology-shaped operating modes with one of `GUIDE`, `DESIGN`, `BUILD`,
`REVIEW`, `OPERATE`, or `MODERNIZE`; technology is now routed as a domain.

Consumers requesting JSON must adopt
`skills/data-engineering/assets/data-engineering-result.schema.json`. Markdown is
the default when a machine-readable contract is not requested. Static provider
bundles were replaced by named profiles in `integrations/profiles.json`.
