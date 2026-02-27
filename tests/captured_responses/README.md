# Captured Responses Contract

Store one markdown file per test case ID:

- `TC-E2E-001.md`
- `TC-E2E-002.md`
- ...
- `TC-E2E-012.md`

Each file should contain the model response captured for that test prompt.

## Minimum structure expected

Responses should include these headings:

- `## Summary`
- `## Decision`
- `## Rationale`
- `## Trade-offs`
- `## Next Steps`

Optional sections can be present based on case needs:

- `## Cost Estimate`
- `## Template`

## Run validation

From repository root:

```bash
tests/run_e2e_harness.sh
```

Or provide a custom response directory:

```bash
tests/run_e2e_harness.sh /path/to/responses
```
