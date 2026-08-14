# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for arena-resident iterative regeneration."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.checkpoint_recursive_regeneration import (
    _IterativeDependencyBundleRegenerator,
    reconstruct_repeatedly_with_iterative_work_stack,
)
from contrib.pow_research_v1.powvm import prepare_epoch


ROOT = Path(__file__).resolve().parents[2]
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "iterative_work_stack_regeneration_v0.json"


class IterativeWorkStackRegenerationV1Test(unittest.TestCase):
    def test_iterative_worker_does_not_call_itself(self) -> None:
        source = inspect.getsource(_IterativeDependencyBundleRegenerator.value_at)
        self.assertNotIn("self.value_at(", source)

    def test_fixed_boundaries_and_exact_accounting(self) -> None:
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params, _ = profile(fixed["profile"])
        for expected in fixed["cases"]:
            result = reconstruct_repeatedly_with_iterative_work_stack(
                prepare_epoch(seed_for(expected["seed_index"]), params),
                HEADER,
                fixed["nonce"],
                operation_limit=fixed["operation_limit"],
            ).to_dict()
            self.assertEqual(result["layout"], fixed["layout"])
            self.assertEqual(
                result["iterative_memory_accounting"],
                fixed["iterative_memory_accounting"],
            )
            self.assertEqual(
                [result[field] for field in fixed["counter_fields"]],
                expected["counters"],
            )
            self.assertEqual(
                [result["operation_counts"][field] for field in fixed["operation_fields"]],
                expected["operations"],
            )
            self.assertEqual(
                [result["exhaustion"][field] for field in fixed["exhaustion_fields"]],
                expected["exhaustion"],
            )
            self.assertEqual(result["transcript_commitment"], expected["transcript_commitment"])
            self.assertIsNone(result["execution_result"])


if __name__ == "__main__":
    unittest.main()
