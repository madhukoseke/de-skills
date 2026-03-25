#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-$ROOT_DIR/tests/captured_responses}"
mkdir -p "$OUT_DIR"

case_ids=$(ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import importlib.util
import os
import pathlib
import sys

root = pathlib.Path(os.environ["ROOT_DIR"])
spec = importlib.util.spec_from_file_location(
    "validate_captured_responses",
    root / "tests" / "validate_captured_responses.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
for c in mod.CASE_CHECKS:
    print(c.case_id)
PY
)

for case_id in $case_ids; do
  file="$OUT_DIR/${case_id}.md"
  if [[ -f "$file" ]]; then
    continue
  fi
  cat >"$file" <<EOF
## Summary
<capture model response summary>

## Decision
<capture model decision>

## Rationale
<capture model rationale>

## Trade-offs
| Option | Pros | Cons | When to Use |
|--------|------|------|-------------|

## Next Steps
1. <capture action items>
EOF
done

echo "Scaffolded captured response files in: $OUT_DIR"
