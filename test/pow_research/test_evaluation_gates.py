# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Validate the machine-readable PoW gate policy and report renderer."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from contrib.pow_research_cpp.render_report import render


ROOT = Path(__file__).resolve().parents[2]
GATES = ROOT / "contrib" / "pow_research" / "gates_v0.json"


class EvaluationGatesTest(unittest.TestCase):
    def test_gate_ids_are_unique_and_all_are_mandatory(self) -> None:
        document = json.loads(GATES.read_text(encoding="utf-8"))
        self.assertEqual(document["format"], "soveroot-pow-evaluation-gates-v0")
        identifiers = [gate["id"] for gate in document["gates"]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(all(gate["mandatory"] for gate in document["gates"]))
        self.assertIn("cannot retroactively", document["decision_rule"])

    def test_report_is_explicitly_informational(self) -> None:
        matrix = {
            "format": "soveroot-pow-research-matrix-v0",
            "profile": "smoke",
            "source_revision": "abc123",
            "host": {"platform": "test", "machine": "test", "cpu_model": "test", "logical_cpus": 2},
            "results": [{
                "config": {"name": "minimum", "dataset_bytes": 65536, "scratchpad_bytes": 8192, "program_instructions": 16, "passes": 1},
                "seed_count": 2,
                "prepare_ns_across_seeds": {"median": 1000000},
                "median_attempt_ns_across_seeds": {"median": 2000000, "spread_ppm": 100000},
                "cases": [{"working_set_bytes_estimate": 73728}],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            matrix_path = Path(directory) / "matrix.json"
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            report = render(matrix_path, GATES, "unit test")
        self.assertIn("NO POW GATE PASSED", report)
        self.assertIn("used 2", report)
        self.assertIn("cannot evaluate energy efficiency", report)


if __name__ == "__main__":
    unittest.main()
