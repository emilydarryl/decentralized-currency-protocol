# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for repeated bounded sparse reconstruction."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.powvm import Params, prepare_epoch
from contrib.pow_research_v1.repeated_reconstruction import reconstruct_repeatedly


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "repeated_reconstruction_v0.json"


class RepeatedReconstructionV1Test(unittest.TestCase):
    def test_smoke_recovers_repeatedly_then_exhausts(self) -> None:
        params, _ = profile("smoke")
        result = reconstruct_repeatedly(prepare_epoch(seed_for(0), params), HEADER, 0)
        self.assertEqual(result.status, "refused_replay_workspace_exhausted")
        self.assertEqual(result.reconstruction_attempts, 3)
        self.assertEqual(result.reconstructed_misses, 2)
        self.assertEqual(result.completed_iterations, 75)
        self.assertTrue(result.all_replay_states_matched)
        self.assertIsNotNone(result.exhaustion)
        self.assertEqual(result.max_replay_peak_entries, result.layout.replay_capacity)
        self.assertIsNone(result.execution_result)

    def test_repeated_result_is_deterministic(self) -> None:
        params, _ = profile("smoke")
        context = prepare_epoch(seed_for(1), params)
        self.assertEqual(
            reconstruct_repeatedly(context, HEADER, 1 << 32),
            reconstruct_repeatedly(context, HEADER, 1 << 32),
        )

    def test_accounting_stays_inside_one_arena(self) -> None:
        params, _ = profile("smoke")
        result = reconstruct_repeatedly(prepare_epoch(seed_for(0), params), HEADER, 0)
        self.assertEqual(result.layout.admitted_bytes, params.scratchpad_bytes // 2)
        self.assertEqual(
            result.attempted_replay_iterations,
            result.successful_replayed_iterations
            + result.exhaustion.replay_completed_iterations,  # type: ignore[union-attr]
        )
        self.assertEqual(result.max_reconstruction_depth, 1)

    def test_fixed_boundaries(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params = Params(**source["params"])
        for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
            result = reconstruct_repeatedly(
                prepare_epoch(bytes.fromhex(vector["seed"]), params),
                bytes.fromhex(vector["header"]),
                vector["nonce"],
            ).to_dict()
            counters = [result[field] for field in fixed["counter_fields"]]
            self.assertEqual(counters, expected["counters"], vector["name"])
            self.assertEqual(
                result["transcript_commitment"], expected["transcript_commitment"]
            )
            self.assertEqual(
                [result["first_reconstruction"][field] for field in fixed["reconstruction_fields"]],
                expected["first"],
            )
            self.assertEqual(
                [result["last_reconstruction"][field] for field in fixed["reconstruction_fields"]],
                expected["last"],
            )
            self.assertEqual(
                [result["exhaustion"][field] for field in fixed["exhaustion_fields"]],
                expected["exhaustion"],
            )


if __name__ == "__main__":
    unittest.main()
