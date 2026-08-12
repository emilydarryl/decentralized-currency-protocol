# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Unit tests for the PoW v1 no-spill recomputation baseline."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from contrib.pow_research_cpp.recomputation_baseline_v1 import integer_summary, profile
from contrib.pow_research_cpp.render_recomputation_report_v1 import render


ROOT = Path(__file__).resolve().parents[2]
GATES = ROOT / "contrib" / "pow_research" / "gates_v0.json"
METHOD = ROOT / "contrib" / "pow_research_v1" / "recomputation_baseline_v0.json"


class RecomputationBaselineV1Test(unittest.TestCase):
    def test_profiles_are_intentionally_bounded(self) -> None:
        smoke, smoke_seeds, smoke_attempts = profile("smoke")
        pilot, pilot_seeds, pilot_attempts = profile("pilot")
        self.assertEqual((smoke.scratchpad_bytes, smoke_seeds, smoke_attempts), (8192, 2, 1))
        self.assertEqual(
            (pilot.dataset_bytes, pilot.scratchpad_bytes, pilot.passes),
            (256 * 1024, 32 * 1024, 1),
        )
        self.assertEqual((pilot_seeds, pilot_attempts), (4, 1))

    def test_unknown_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported profile"):
            profile("standard")

    def test_integer_summary(self) -> None:
        self.assertEqual(
            integer_summary([10, 20, 30]),
            {"min": 10, "median": 20, "mean": 20, "max": 30},
        )

    def test_method_discloses_peak_memory_disqualification(self) -> None:
        method = json.loads(METHOD.read_text(encoding="utf-8"))
        self.assertEqual(method["gate_mapping"]["status"], "INFORMATIONAL_ONLY")
        self.assertEqual(method["attack_model"]["peak_scratch_fraction"], "3/2")
        self.assertIn(
            "peak scratch allocation is 150% of the declared scratchpad rather than 50%",
            method["gate_mapping"]["why_not_decisive"],
        )

    def test_report_requires_exact_outputs_and_keeps_gate_open(self) -> None:
        backend = {
            "attempt_ns": {"median": 1_000_000},
            "digest_sequence_commitment": "aa",
            "digest_xor_64": "bb",
        }
        matrix = {
            "format": "soveroot-pow-v1-recomputation-baseline-matrix-v0",
            "profile": "smoke",
            "source_revision": "abc123",
            "config": {
                "name": "minimum",
                "dataset_bytes": 65536,
                "scratchpad_bytes": 8192,
                "passes": 1,
            },
            "all_exact_outputs_match": True,
            "normal_median_attempt_ns_across_seeds": {"median": 1_000_000},
            "recomputation_median_attempt_ns_across_seeds": {"median": 10_000_000},
            "throughput_fraction_ppm_across_seeds": {"median": 100_000},
            "replayed_iterations_across_seeds": {"median": 250_000},
            "cases": [{
                "seed_index": 0,
                "normal": backend,
                "half_retained_full_replay": {
                    **backend,
                    "attempt_ns": {"median": 10_000_000},
                    "recomputation_stats": {
                        "recomputed_reads": 500,
                        "replayed_iterations": 250_000,
                    },
                },
                "throughput_fraction_ppm": 100_000,
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            matrix_path = Path(directory) / "matrix.json"
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            report = render(matrix_path, GATES, METHOD, "unit test")
        self.assertIn("HALF-MEMORY GATE NOT ASSESSED", report)
        self.assertIn("same digest-sequence commitment", report)
        self.assertIn("Retained throughput: 10.00%", report)
        self.assertIn("150%", report)
        self.assertIn("mandatory gate remains open", report)


if __name__ == "__main__":
    unittest.main()
