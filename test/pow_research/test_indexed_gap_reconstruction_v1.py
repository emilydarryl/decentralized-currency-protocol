# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for page-indexed, neighbor-rebalanced replay reconstruction."""

from __future__ import annotations

import json
from pathlib import Path
import random
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.indexed_gap_reconstruction import (
    _IndexedGapArena,
    _IndexedGapExhausted,
    _IndexedGapReplay,
    reconstruct_with_indexed_gaps,
)
from contrib.pow_research_v1.powvm import Params, prepare_epoch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "indexed_gap_reconstruction_v0.json"


class IndexedGapReconstructionV1Test(unittest.TestCase):
    def test_rebalanced_pages_preserve_exact_word_values(self) -> None:
        arena = _IndexedGapArena(8192, 4096)
        replay = _IndexedGapReplay(arena)
        words = list(range(1024))
        random.Random(20260813).shuffle(words)
        expected: dict[int, int] = {}
        for word in words:
            value = (word * 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
            try:
                replay.write(word, value)
            except _IndexedGapExhausted:
                break
            expected[word] = value
            if word % 7 == 0:
                updated = value ^ 0xA5A5A5A5A5A5A5A5
                replay.write(word, updated)
                expected[word] = updated
        self.assertGreater(replay.rebalances, 0)
        self.assertGreaterEqual(len(expected), 240)
        for word, value in expected.items():
            self.assertEqual(replay.read_exact_word(word), value)

    def test_smoke_improves_page_utilization_and_prefix(self) -> None:
        params, _ = profile("smoke")
        result = reconstruct_with_indexed_gaps(prepare_epoch(seed_for(0), params), HEADER, 0)
        self.assertEqual(result.status, "refused_indexed_gap_exhausted")
        self.assertEqual(result.completed_iterations, 150)
        self.assertGreaterEqual(result.max_replay_peak_values, 260)
        self.assertEqual(result.max_replay_peak_pages, result.layout.max_pages)
        self.assertGreater(result.cumulative_rebalances, 0)
        self.assertTrue(result.all_replay_states_matched)
        self.assertIsNone(result.execution_result)

    def test_indexed_gap_result_is_deterministic(self) -> None:
        params, _ = profile("smoke")
        context = prepare_epoch(seed_for(1), params)
        self.assertEqual(
            reconstruct_with_indexed_gaps(context, HEADER, 1 << 32),
            reconstruct_with_indexed_gaps(context, HEADER, 1 << 32),
        )

    def test_fixed_boundaries(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params = Params(**source["params"])
        for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
            result = reconstruct_with_indexed_gaps(
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
