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
from contrib.pow_research_cpp.render_report_v1 import render as render_v1


ROOT = Path(__file__).resolve().parents[2]
GATES = ROOT / "contrib" / "pow_research" / "gates_v0.json"
RESEARCH_STATUS = ROOT / "contrib" / "pow_research" / "research_status_v0.json"
V1_SCREENING = ROOT / "contrib" / "pow_research_v1" / "screening_v0.json"


class EvaluationGatesTest(unittest.TestCase):
    def test_gate_ids_are_unique_and_all_are_mandatory(self) -> None:
        document = json.loads(GATES.read_text(encoding="utf-8"))
        self.assertEqual(document["format"], "soveroot-pow-evaluation-gates-v0")
        identifiers = [gate["id"] for gate in document["gates"]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(all(gate["mandatory"] for gate in document["gates"]))
        self.assertIn("cannot retroactively", document["decision_rule"])

    def test_research_dashboard_covers_every_gate_without_claiming_a_pass(self) -> None:
        policy = json.loads(GATES.read_text(encoding="utf-8"))
        status = json.loads(RESEARCH_STATUS.read_text(encoding="utf-8"))
        policy_ids = [gate["id"] for gate in policy["gates"]]
        dashboard_ids = [gate["id"] for gate in status["pow_gates"]]
        self.assertEqual(status["format"], "soveroot-research-status-v0")
        self.assertEqual(dashboard_ids, policy_ids)
        self.assertEqual(status["pow_gate_summary"]["passed"], 0)
        self.assertEqual(status["pow_gate_summary"]["open"], len(policy_ids))
        self.assertTrue(all(gate["state"] == "OPEN" for gate in status["pow_gates"]))
        self.assertTrue(all(gate["assessment"] == "NOT_ASSESSED" for gate in status["pow_gates"]))
        self.assertTrue(all(gate["gap"] for gate in status["pow_gates"]))

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
                "median_phase_ns_across_seeds": {
                    "input_setup": {"median": 100000},
                    "scratchpad_init": {"median": 900000},
                    "vm_execute": {"median": 100000},
                    "finalize": {"median": 900000},
                },
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
        self.assertIn("Median phase shares", report)
        self.assertIn("45.0%", report)

    def test_v1_screening_policy_matches_predeclared_bounds(self) -> None:
        document = json.loads(V1_SCREENING.read_text(encoding="utf-8"))
        self.assertEqual(document["format"], "soveroot-pow-v1-screening-objectives-v0")
        screens = document["screens"]
        self.assertEqual(screens["baseline_mix_share_percent"], {
            "advance_min": 60,
            "redesign_below": 50,
        })
        self.assertEqual(screens["passes_16x_attempt_ratio"], {
            "advance_min": 8,
            "redesign_below": 4,
        })
        self.assertTrue(screens["dataset_cache_tier_ratio"]["controlled_physical_hardware_required"])

    def test_v1_report_classifies_only_predeclared_software_screens(self) -> None:
        def result(name: str, attempt: int, phases: tuple[int, int, int, int]) -> dict[str, object]:
            return {
                "config": {
                    "name": name,
                    "dataset_bytes": 2 * 1024 * 1024,
                    "scratchpad_bytes": 256 * 1024,
                    "passes": 3,
                },
                "seed_count": 8,
                "prepare_ns_across_seeds": {"median": 1_000_000},
                "median_attempt_ns_across_seeds": {"median": attempt, "spread_ppm": 10_000},
                "median_phase_ns_across_seeds": {
                    "input_setup": {"median": phases[0]},
                    "scratchpad_init": {"median": phases[1]},
                    "mix_execute": {"median": phases[2]},
                    "finalize": {"median": phases[3]},
                },
                "cases": [{"working_set_bytes_estimate": 2_359_296}],
            }

        matrix = {
            "format": "soveroot-pow-research-matrix-v1",
            "profile": "standard",
            "source_revision": "v1abc",
            "host": {
                "platform": "test",
                "machine": "test",
                "cpu_model": "test",
                "logical_cpus": 2,
            },
            "results": [
                result("baseline", 1_000, (50, 100, 800, 50)),
                result("passes-1", 100, (5, 10, 80, 5)),
                result("passes-16", 900, (5, 10, 880, 5)),
                result("scratch-8k", 100, (5, 10, 80, 5)),
                result("scratch-512k", 2_000, (10, 20, 1_960, 10)),
                result("dataset-64k", 100, (5, 10, 80, 5)),
                result("dataset-4096k", 120, (5, 10, 100, 5)),
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            matrix_path = Path(directory) / "matrix-v1.json"
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            report = render_v1(matrix_path, GATES, V1_SCREENING, "v1 unit test")
        self.assertIn("NO POW GATE PASSED", report)
        self.assertIn("Baseline mixing share | 80.0% | **ADVANCE**", report)
        self.assertIn("16x pass-count response | 9.00x | **ADVANCE**", report)
        self.assertIn("64x scratchpad response | 20.00x | **ADVANCE**", report)
        self.assertIn("UNASSESSED ON SHARED RUNNER", report)
        self.assertIn("ADVANCE SOFTWARE SCREEN ONLY", report)


if __name__ == "__main__":
    unittest.main()
