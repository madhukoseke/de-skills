# Release checklist

- [ ] Version follows semantic versioning and `VERSION` matches the release tag.
- [ ] Domain owners approved changed references and assets.
- [ ] Technology-specific sources have current verification dates.
- [ ] ADRs document architectural, workflow, schema, or release-gate changes.
- [ ] `tests/run_e2e_harness.sh` passes from a clean checkout.
- [ ] Generated bundle drift check passes.
- [ ] v6, v5, and no-skill runs used identical models and scenarios.
- [ ] Critical-failure, trigger, deterministic, expert-score, improvement,
      reference-count, and token gates all pass.
- [ ] Blinded grading was calibrated against human data engineers.
- [ ] Benchmark report and unresolved limitations are published.
- [ ] `tests/benchmark/validate_published_report.py` passes for this version.
- [ ] Release archive, checksum metadata, migration note, and changelog are complete.
- [ ] Claims do not describe the project as “best” unless published gates pass.
