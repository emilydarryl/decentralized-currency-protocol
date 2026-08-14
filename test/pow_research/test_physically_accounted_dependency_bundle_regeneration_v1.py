# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for physically accounted operation-bounded regeneration."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.checkpoint_recursive_regeneration import (
    reconstruct_repeatedly_with_physically_accounted_dependency_bundles,
)
from contrib.pow_research_v1.powvm import prepare_epoch


ROOT = Path(__file__).resolve().parents[2]
FIXED = (
    ROOT
    / "contrib"
    / "pow_research_v1"
    / "vectors"
    / "physically_accounted_dependency_bundle_regeneration_v0.json"
)


class PhysicallyAccountedDependencyBundleRegenerationV1Test(unittest.TestCase):
    def test_selected_standard_configuration_accounts_exact_half_scratch(self) -> None:
        params, _ = profile("standard")
        result = reconstruct_repeatedly_with_physically_accounted_dependency_bundles(
            prepare_epoch(seed_for(0), params), HEADER, 0
        )
        self.assertEqual(result.completed_iterations, 669)
        self.assertEqual(result.maximum_depth, 8)
        self.assertEqual(result.operation_counts.total, 5_000_000)  # type: ignore[union-attr]
        accounting = result.physical_memory_accounting
        self.assertIsNotNone(accounting)
        self.assertEqual(accounting.accounted_bytes, 131_072)  # type: ignore[union-attr]
        self.assertEqual(accounting.transcript_growth_bytes, 0)  # type: ignore[union-attr]
        self.assertIsNone(result.execution_result)

    def test_smoke_profile_fails_startup_because_reserves_do_not_fit(self) -> None:
        params, _ = profile("smoke")
        with self.assertRaisesRegex(ValueError, "external reserves"):
            reconstruct_repeatedly_with_physically_accounted_dependency_bundles(
                prepare_epoch(seed_for(0), params), HEADER, 0
            )

    def test_fixed_boundaries(self) -> None:
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params, _ = profile(fixed["profile"])
        for expected in fixed["cases"]:
            result = reconstruct_repeatedly_with_physically_accounted_dependency_bundles(
                prepare_epoch(seed_for(expected["seed_index"]), params),
                HEADER,
                fixed["nonce"],
                operation_limit=fixed["operation_limit"],
            ).to_dict()
            self.assertEqual(result["layout"], fixed["layout"])
            self.assertEqual(
                result["physical_memory_accounting"],
                fixed["physical_memory_accounting"],
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
            self.assertEqual(
                result["transcript_commitment"], expected["transcript_commitment"]
            )


if __name__ == "__main__":
    unittest.main()
