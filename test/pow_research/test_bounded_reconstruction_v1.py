# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for first-miss bounded sparse reconstruction."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.bounded_reconstruction import reconstruct_first_miss
from contrib.pow_research_v1.powvm import prepare_epoch


ROOT = Path(__file__).resolve().parents[2]
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "bounded_reconstruction_v0.json"

class BoundedReconstructionV1Test(unittest.TestCase):
    def test_smoke_reconstructs_one_miss_and_advances(self) -> None:
        params, _ = profile("smoke")
        context = prepare_epoch(seed_for(0), params)
        result = reconstruct_first_miss(context, HEADER, 0)
        self.assertEqual(result.status, "refused_after_one_reconstruction")
        self.assertEqual(result.reconstructed_misses, 1)
        self.assertTrue(result.replay_state_matched)
        self.assertGreater(result.replayed_iterations, 0)
        self.assertGreater(result.completed_iterations, result.reconstruction_consumer or 0)
        self.assertIsNone(result.execution_result)
        self.assertEqual(result.layout.admitted_bytes, params.scratchpad_bytes // 2)
        self.assertLessEqual(result.replay_peak_entries, result.layout.replay_capacity)

    def test_reconstruction_is_deterministic(self) -> None:
        params, _ = profile("smoke")
        context = prepare_epoch(seed_for(1), params)
        self.assertEqual(
            reconstruct_first_miss(context, HEADER, 1 << 32),
            reconstruct_first_miss(context, HEADER, 1 << 32),
        )

    def test_fixed_smoke_boundary(self) -> None:
        params, _ = profile("smoke")
        result = reconstruct_first_miss(prepare_epoch(seed_for(0), params), HEADER, 0)
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        self.assertEqual(result.layout.replay_capacity, 135)
        self.assertEqual(result.reconstructed_misses, 1)
        self.assertTrue(result.replay_state_matched)


if __name__ == "__main__":
    unittest.main()
