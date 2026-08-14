# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for the total-operation-bounded dependency-bundle experiment."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.checkpoint_recursive_regeneration import (
    reconstruct_repeatedly_with_operation_bounded_dependency_bundles,
)
from contrib.pow_research_v1.powvm import Params, prepare_epoch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = (
    ROOT
    / "contrib"
    / "pow_research_v1"
    / "vectors"
    / "operation_bounded_dependency_bundle_regeneration_v0.json"
)


class OperationBoundedDependencyBundleRegenerationV1Test(unittest.TestCase):
    def test_selected_standard_configuration_hits_exact_total_ceiling(self) -> None:
        params, _ = profile("standard")
        result = reconstruct_repeatedly_with_operation_bounded_dependency_bundles(
            prepare_epoch(seed_for(0), params), HEADER, 0
        )
        self.assertEqual(
            result.status,
            "refused_operation_bounded_dependency_bundle_exhausted",
        )
        self.assertEqual(result.completed_iterations, 999)
        self.assertEqual(result.reconstructed_misses, 53)
        self.assertEqual(result.exhaustion.reason, "operation_limit")  # type: ignore[union-attr]
        self.assertEqual(result.operation_limit, 5_000_000)
        self.assertEqual(result.operation_counts.total, 5_000_000)  # type: ignore[union-attr]
        self.assertEqual(
            result.operation_counts.total,  # type: ignore[union-attr]
            result.regeneration_calls
            + result.regeneration_iterations
            + result.memo_probes
            + result.checkpoint_probes,
        )
        self.assertIsNone(result.execution_result)

    def test_operation_limit_must_be_positive(self) -> None:
        params, _ = profile("smoke")
        context = prepare_epoch(seed_for(0), params)
        for limit in (0, -1):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                reconstruct_repeatedly_with_operation_bounded_dependency_bundles(
                    context, HEADER, 0, operation_limit=limit
                )

    def test_fixed_boundaries(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params = Params(**source["params"])
        for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
            self.assertEqual(vector["name"], expected["name"])
            result = reconstruct_repeatedly_with_operation_bounded_dependency_bundles(
                prepare_epoch(bytes.fromhex(vector["seed"]), params),
                bytes.fromhex(vector["header"]),
                vector["nonce"],
                operation_limit=fixed["operation_limit"],
            ).to_dict()
            self.assertEqual(result["layout"], fixed["layout"])
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
            self.assertEqual(
                result["transcript_commitment"], expected["transcript_commitment"]
            )


if __name__ == "__main__":
    unittest.main()
