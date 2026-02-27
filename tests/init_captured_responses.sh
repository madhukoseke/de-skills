#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-$ROOT_DIR/tests/captured_responses}"
mkdir -p "$OUT_DIR"

for id in $(seq 1 12); do
  case_id="$(printf 'TC-E2E-%03d' "$id")"
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
