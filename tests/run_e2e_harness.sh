#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 tests/validate_skill_structure.py
python3 tests/validate_vendor_neutrality.py
python3 tests/validate_content_hygiene.py
python3 tests/validate_assets.py
python3 tests/validate_adapters.py
python3 tests/validate_json_responses.py
python3 tests/validate_eval_contracts.py
python3 -m unittest tests/test_skill_utilities.py
python3 scripts/build_bundles.py --check

echo "v6 offline validation passed"
