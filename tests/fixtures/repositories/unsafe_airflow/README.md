# Unsafe Airflow fixture

This intentionally incomplete repository supports `BUILD` and `REVIEW` tests.
The evaluator copies it to a temporary directory before allowing edits. Expected
work includes interval-bounded writes, replay behavior, validation, and an
explanation; it must not execute a production backfill.
