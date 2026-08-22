# Generic API integration

Build the narrowest named profile and pass it as the provider's system or
instruction prompt:

```bash
python3 scripts/build_bundles.py --profile architecture
```

Use `dist/bundles/architecture.txt`. Keep the bundle before task-specific
context, and consult `integrations/providers.yaml` for dated channel, model, and
caching notes. An Agent Skills-compatible host should install
`skills/data-engineering` directly instead.
