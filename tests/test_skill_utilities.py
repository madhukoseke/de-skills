#!/usr/bin/env python3
"""Behavior tests for shipped deterministic utilities."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "data-engineering" / "scripts"


class UtilitiesTest(unittest.TestCase):
    def run_json(self, *args: str) -> dict:
        result = subprocess.run([sys.executable, *args], cwd=ROOT, check=True, capture_output=True, text=True)
        return json.loads(result.stdout)

    def test_inventory_is_static_and_detects_stack(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("dbt_project.yml").write_text("name: fixture\n", encoding="utf-8")
            root.joinpath("requirements.txt").write_text("apache-airflow==3.0\n", encoding="utf-8")
            result = self.run_json(str(SCRIPTS / "inspect_project.py"), str(root), "--format", "json")
            self.assertIn("dbt", result["technologies"])
            self.assertIn("airflow", result["technologies"])

    def test_capacity_estimate_is_repeatable(self) -> None:
        args = [str(SCRIPTS / "estimate_capacity.py"), "--records-per-day", "86400000", "--avg-record-bytes", "500", "--retention-days", "30", "--backfill-days", "7", "--backfill-hours", "6", "--format", "json"]
        first = self.run_json(*args)
        second = self.run_json(*args)
        self.assertEqual(first, second)
        self.assertGreater(first["backfill"]["requiredRecordsPerSecond"], 0)

    def test_contract_fixtures(self) -> None:
        valid = subprocess.run([sys.executable, str(SCRIPTS / "validate_contract.py"), "tests/fixtures/contracts/valid.odcs.yaml"], cwd=ROOT)
        invalid = subprocess.run([sys.executable, str(SCRIPTS / "validate_contract.py"), "tests/fixtures/contracts/invalid.odcs.yaml"], cwd=ROOT)
        self.assertEqual(valid.returncode, 0)
        self.assertNotEqual(invalid.returncode, 0)


if __name__ == "__main__":
    unittest.main()
