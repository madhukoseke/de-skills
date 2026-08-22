# Contributing

Contributions should make the skill safer, more correct, more useful, or more
context-efficient for working data engineers.

## Contribution contract

1. Open or reference an issue naming the lifecycle domain and proposed owner.
2. Ground durable rules in authoritative sources. Prefer standards, official
   documentation, research, and established engineering texts.
3. Put stable behavior in `SKILL.md` only when it applies across domains. Put
   detailed knowledge in one focused `references/` file, reusable output forms
   in `assets/`, and deterministic operations in `scripts/`.
4. Date technology-specific claims as `Last verified: YYYY-MM-DD`; recheck them
   before merging. Do not move vendor details into stable principles.
5. Add an ADR under `docs/decisions/` for changes to workflows, guardrails,
   routing, schemas, release gates, or package structure.
6. Add fixtures and deterministic assertions. Add or update benchmark cases
   when behavior changes.

Avoid universal prescriptions unless they are safety guardrails. A rule such as
“always partition,” “always merge,” or “every quality failure stops processing”
must instead identify the source semantics, platform capabilities, consequences,
and recovery conditions that determine the choice.

## Source and copyright policy

Record source title, edition/version, authoritative URL, influence, review date,
and licensing boundary in `foundations-and-sources.md`. Synthesize concepts in
original language. Do not reproduce paid text, diagrams, or extended passages.

## Validation

```bash
python3 -m pip install -r tests/requirements.txt
python3 scripts/build_bundles.py
tests/run_e2e_harness.sh
python3 scripts/build_bundles.py --check
python3 scripts/package_release.py --out-dir /tmp/de-skills-release
python3 tests/validate_release_package.py --release-dir /tmp/de-skills-release
```

Pull requests must complete the checklist in `.github/pull_request_template.md`.
Releases follow [the release checklist](docs/release-checklist.md) and semantic
versioning. Breaking workflow, schema, or skill-identity changes require a major
version.
