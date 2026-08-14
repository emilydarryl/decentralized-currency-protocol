# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for target-aware checkpoint regeneration."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.checkpoint_recursive_regeneration import (
    reconstruct_repeatedly_with_target_checkpoints,
)
from contrib.pow_research_v1.powvm import Params, prepare_epoch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "target_checkpoint_regeneration_v0.json"


class TargetCheckpointRegenerationV1Test(unittest.TestCase):
    def test_standard_selected_configuration_ties_global_record(self) -> None:
        params, _ = profile("standard")
        result = reconstruct_repeatedly_with_target_checkpoints(
            prepare_epoch(seed_for(0), params), HEADER, 0
        )
        self.assertEqual(
            result.status, "refused_target_checkpoint_regeneration_exhausted"
        )
        self.assertEqual(result.completed_iterations, 999)
        self.assertEqual(result.reconstructed_misses, 53)
        self.assertEqual(result.maximum_depth, 4)
        self.assertEqual(result.checkpoint_hits, 31)
        self.assertEqual(result.regeneration_iterations, 1_000_000)
        self.assertIsNone(result.execution_result)

    def test_work_limit_fails_closed(self) -> None:
        params, _ = profile("smoke")
        result = reconstruct_repeatedly_with_target_checkpoints(
            prepare_epoch(seed_for(0), params), HEADER, 0, work_limit=100
        )
        self.assertEqual(
            result.status, "refused_target_checkpoint_regeneration_exhausted"
        )
        self.assertEqual(result.exhaustion.reason, "work_limit")  # type: ignore[union-attr]
        self.assertIsNone(result.execution_result)

    def test_fixed_boundaries(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params = Params(**source["params"])
        for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
            self.assertEqual(vector["name"], expected["name"])
            result = reconstruct_repeatedly_with_target_checkpoints(
                prepare_epoch(bytes.fromhex(vector["seed"]), params),
                bytes.fromhex(vector["header"]), vector["nonce"],
            ).to_dict()
            self.assertEqual(result["layout"], fixed["layout"])
            self.assertEqual(
                [result[field] for field in fixed["counter_fields"]], expected["counters"]
            )
            for key in ("first", "last"):
                boundary = result[f"{key}_reconstruction"]
                if expected[key] is None:
                    self.assertIsNone(boundary)
                else:
                    self.assertEqual(
                        [boundary[field] for field in fixed["boundary_fields"]],
                        expected[key],
                    )
            self.assertEqual(
                [result["exhaustion"][field] for field in fixed["exhaustion_fields"]],
                expected["exhaustion"],
            )
            self.assertEqual(result["transcript_commitment"], expected["transcript_commitment"])


if __name__ == "__main__":
    unittest.main()
