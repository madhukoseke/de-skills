# Published benchmark evidence

A release-qualified version requires both `<version>.json` and `<version>.md` in
this directory. Generate the JSON from blinded v6, v5, and no-skill evaluation,
then validate it with:

```bash
python3 tests/benchmark/validate_published_report.py 6.0.0
```

Do not create placeholder passing results. Until evidence passes every v4 gate,
the package may be described as a release candidate but not benchmark-qualified
or “the best.”
