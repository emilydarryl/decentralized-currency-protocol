# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Unit tests for PoW v1 dependency and batch diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from contrib.pow_research_cpp.batch_amortization_v1 import profile as batch_profile
from contrib.pow_research_cpp.dependency_trace_v1 import profile as trace_profile
from contrib.pow_research_cpp.render_dependency_batch_report_v1 import render


ROOT = Path(__file__).resolve().parents[2]
GATES = ROOT / "contrib" / "pow_research" / "gates_v0.json"
METHOD = ROOT / "contrib" / "pow_research_v1" / "dependency_batch_screen_v0.json"


class DependencyBatchV1Test(unittest.TestCase):
    def test_standard_batch_profile_reaches_gate_minimum(self) -> None:
        config, batches, seeds = batch_profile("standard")
        self.assertEqual(batches, [1, 4, 16, 64, 256, 1024, 4096])
        self.assertEqual(seeds, 8)
        self.assertEqual(config["scratchpad_bytes"], 256 * 1024)

    def test_trace_profile_matches_standard_candidate(self) -> None:
        config, seeds = trace_profile("standard")
        self.assertEqual(seeds, 8)
        self.assertEqual(config, {
            "name": "baseline",
            "dataset_bytes": 2 * 1024 * 1024,
            "scratchpad_bytes": 256 * 1024,
            "passes": 3,
        })

    def test_method_keeps_both_gates_open(self) -> None:
        method = json.loads(METHOD.read_text(encoding="utf-8"))
        self.assertEqual(method["gate_mapping"]["facility_amortization"], "INFORMATIONAL_ONLY")
        self.assertEqual(method["gate_mapping"]["time_memory_tradeoff"], "NOT_ASSESSED")
        self.assertIn("LRU misses are simulations and do not produce a valid PoW with reduced memory", method["limitations"])

    def test_report_labels_diagnostics_and_numerical_zone(self) -> None:
        trace = {
            "format": "soveroot-pow-v1-dependency-trace-matrix-v0",
            "source_revision": "abc",
            "seed_count": 8,
            "config": {"scratchpad_bytes": 256 * 1024},
            "summaries": {
                "initial_zero_reads": {"median": 100},
                "materialized_reads": {"median": 900},
                "maximum_live_values": {"median": 20_000},
                "cache_simulations": {
                    "half_capacity_lru": {
                        "materialized_read_hits": {"median": 300},
                        "materialized_read_misses": {"median": 600},
                    },
                    "quarter_capacity_lru": {
                        "materialized_read_hits": {"median": 100},
                        "materialized_read_misses": {"median": 800},
                    },
                },
            },
        }
        batch = {
            "format": "soveroot-pow-v1-batch-amortization-matrix-v0",
            "source_revision": "abc",
            "summaries": [
                {
                    "batch_size": 1,
                    "inclusive_per_attempt_ns": {"median": 10_000_000},
                    "evaluation_per_attempt_ns": {"median": 1_000_000},
                    "inclusive_advantage_ppm": {"median": 1_000_000},
                    "evaluation_only_advantage_ppm": {"median": 1_000_000},
                },
                {
                    "batch_size": 4096,
                    "inclusive_per_attempt_ns": {"median": 1_000_000},
                    "evaluation_per_attempt_ns": {"median": 900_000},
                    "inclusive_advantage_ppm": {"median": 10_000_000},
                    "evaluation_only_advantage_ppm": {"median": 1_111_111},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "trace.json"
            batch_path = Path(directory) / "batch.json"
            trace_path.write_text(json.dumps(trace), encoding="utf-8")
            batch_path.write_text(json.dumps(batch), encoding="utf-8")
            report = render(trace_path, batch_path, GATES, METHOD, "unit test")
        self.assertIn("NO POW GATE PASSED", report)
        self.assertIn("Half capacity", report)
        self.assertIn("66.67%", report)
        self.assertIn("above the policy rejection boundary", report)
        self.assertIn("facility-amortization gate remains open", report)


if __name__ == "__main__":
    unittest.main()
