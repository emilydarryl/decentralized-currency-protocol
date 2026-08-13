# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for paged-gap replay reconstruction."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.paged_gap_reconstruction import reconstruct_with_paged_gaps
from contrib.pow_research_v1.powvm import Params, prepare_epoch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "paged_gap_reconstruction_v0.json"


class PagedGapReconstructionV1Test(unittest.TestCase):
    def test_smoke_is_fail_closed_and_movement_is_bounded(self) -> None:
        params, _ = profile("smoke")
        result = reconstruct_with_paged_gaps(prepare_epoch(seed_for(0), params), HEADER, 0)
        self.assertEqual(result.status, "refused_paged_gap_exhausted")
        self.assertEqual(result.completed_iterations, 104)
        self.assertEqual(result.layout.page_slots, 32)
        self.assertTrue(result.all_replay_states_matched)
        self.assertEqual(result.max_replay_peak_pages, result.layout.max_pages)
        self.assertLess(result.cumulative_shifted_bytes, 200_000)
        self.assertIsNone(result.execution_result)

    def test_paged_result_is_deterministic(self) -> None:
        params, _ = profile("smoke")
        context = prepare_epoch(seed_for(1), params)
        self.assertEqual(
            reconstruct_with_paged_gaps(context, HEADER, 1 << 32),
            reconstruct_with_paged_gaps(context, HEADER, 1 << 32),
        )

    def test_fixed_boundaries(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params = Params(**source["params"])
        for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
            result = reconstruct_with_paged_gaps(
                prepare_epoch(bytes.fromhex(vector["seed"]), params),
                bytes.fromhex(vector["header"]), vector["nonce"],
            ).to_dict()
            self.assertEqual([result[field] for field in fixed["counter_fields"]], expected["counters"], vector["name"])
            self.assertEqual(result["transcript_commitment"], expected["transcript_commitment"])
            self.assertEqual([result["first_reconstruction"][field] for field in fixed["reconstruction_fields"]], expected["first"])
            self.assertEqual([result["last_reconstruction"][field] for field in fixed["reconstruction_fields"]], expected["last"])
            self.assertEqual([result["exhaustion"][field] for field in fixed["exhaustion_fields"]], expected["exhaustion"])


if __name__ == "__main__":
    unittest.main()
