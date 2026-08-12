# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Unit tests for the PoW v1 half-memory attack orchestration and report."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from contrib.pow_research_cpp.half_memory_attack_v1 import (
    build_matrix,
    integer_summary,
    profile,
)
from contrib.pow_research_cpp.render_half_memory_report_v1 import render


ROOT = Path(__file__).resolve().parents[2]
GATES = ROOT / "contrib" / "pow_research" / "gates_v0.json"
METHOD = ROOT / "contrib" / "pow_research_v1" / "half_memory_attack_v0.json"


class HalfMemoryAttackV1Test(unittest.TestCase):
    def test_profiles_freeze_bounded_defaults(self) -> None:
        smoke, smoke_seeds, smoke_attempts = profile("smoke")
        standard, standard_seeds, standard_attempts = profile("standard")
        self.assertEqual((smoke.scratchpad_bytes, smoke_seeds, smoke_attempts), (8192, 2, 1))
        self.assertEqual(
            (standard.dataset_bytes, standard.scratchpad_bytes, standard.passes),
            (2 * 1024 * 1024, 256 * 1024, 3),
        )
        self.assertEqual((standard_seeds, standard_attempts), (8, 3))

    def test_integer_summary_preserves_integer_scale(self) -> None:
        self.assertEqual(integer_summary([10, 20, 30]), {
            "min": 10,
            "median": 20,
            "mean": 20,
            "max": 30,
        })

    def test_unknown_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported profile"):
            profile("unknown")

    def test_build_matrix_rejects_unbounded_work_before_execution(self) -> None:
        with self.assertRaisesRegex(ValueError, "attempts must"):
            build_matrix(None, "smoke", attempts=101)  # type: ignore[arg-type]

    def test_method_is_explicitly_ineligible_for_gate_decision(self) -> None:
        method = json.loads(METHOD.read_text(encoding="utf-8"))
        self.assertEqual(method["format"], "soveroot-pow-v1-half-memory-attack-v0")
        self.assertEqual(method["gate_mapping"]["status"], "INFORMATIONAL_ONLY")
        self.assertIn("OS page-cache memory is not measured or bounded", method["gate_mapping"]["why_not_decisive"])

    def test_report_preserves_exactness_and_gate_limitations(self) -> None:
        backend = {
            "attempt_ns": {"median": 1_000_000},
            "digest_sequence_commitment": "aa",
            "digest_xor_64": "bb",
        }
        matrix = {
            "format": "soveroot-pow-v1-half-memory-attack-matrix-v0",
            "profile": "standard",
            "source_revision": "abc123",
            "config": {
                "name": "baseline",
                "dataset_bytes": 2 * 1024 * 1024,
                "scratchpad_bytes": 256 * 1024,
                "passes": 3,
            },
            "all_exact_outputs_match": True,
            "normal_median_attempt_ns_across_seeds": {"median": 1_000_000},
            "half_spill_median_attempt_ns_across_seeds": {"median": 4_000_000},
            "throughput_fraction_ppm_across_seeds": {"median": 250_000},
            "cases": [{
                "seed_index": 0,
                "normal": backend,
                "half_spill": {
                    **backend,
                    "attempt_ns": {"median": 4_000_000},
                    "spill_stats": {"spill_reads": 100, "spill_writes": 50},
                },
                "throughput_fraction_ppm": 250_000,
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            matrix_path = Path(directory) / "matrix.json"
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            report = render(matrix_path, GATES, METHOD, "unit test")
        self.assertIn("TIME-MEMORY GATE NOT ASSESSED", report)
        self.assertIn("Every paired attempt produced the same", report)
        self.assertIn("Retained throughput: 25.00%", report)
        self.assertIn("page cache", report)
        self.assertIn("recomputation", report)


if __name__ == "__main__":
    unittest.main()
