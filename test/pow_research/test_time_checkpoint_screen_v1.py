# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for the offline time-checkpoint feasibility screen."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.powvm import Params, prepare_epoch
from contrib.pow_research_v1.time_checkpoint_screen import screen_time_checkpoints


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "time_checkpoint_screen_v0.json"


class TimeCheckpointScreenV1Test(unittest.TestCase):
    def test_smoke_rejects_single_checkpoint_models(self) -> None:
        params, _ = profile("smoke")
        result = screen_time_checkpoints(prepare_epoch(seed_for(0), params), HEADER, 0)
        self.assertEqual(len(result.cuts), 17)
        self.assertEqual(result.global_maximum_live_values, 411)
        self.assertFalse(result.any_naive_snapshot_delta_fits)
        self.assertTrue(result.any_optimistic_staged_fits)
        self.assertEqual({cut.staged_peak_live_values for cut in result.cuts}, {411})

    def test_fixed_boundaries(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params = Params(**source["params"])
        for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
            self.assertEqual(vector["name"], expected["name"])
            result = screen_time_checkpoints(
                prepare_epoch(bytes.fromhex(vector["seed"]), params),
                bytes.fromhex(vector["header"]), vector["nonce"],
            ).to_dict()
            self.assertEqual(result["layout"], fixed["layout"])
            self.assertEqual(result["global_maximum_live_values"], expected["global_maximum_live_values"])
            self.assertEqual(result["screen_commitment"], expected["screen_commitment"])
            self.assertEqual(
                [[cut[field] for field in fixed["cut_fields"]] for cut in result["cuts"]],
                expected["cuts"], vector["name"],
            )
            self.assertFalse(result["any_naive_snapshot_delta_fits"])
            self.assertFalse(result["any_optimistic_staged_fits"])


if __name__ == "__main__":
    unittest.main()
