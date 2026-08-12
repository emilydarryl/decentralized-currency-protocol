# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Unit tests for the C++ v1 benchmark matrix orchestration."""

from __future__ import annotations

import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import (
    build_matrix,
    integer_summary,
    profile,
    seed_for,
)


class BenchmarkMatrixV1Test(unittest.TestCase):
    def test_smoke_profile_is_bounded(self) -> None:
        configs, seeds, attempts = profile("smoke")
        self.assertEqual((len(configs), seeds, attempts), (2, 2, 2))
        self.assertTrue(all(config.dataset_bytes <= 2 * 1024 * 1024 for config in configs))
        self.assertTrue(all(config.scratchpad_bytes <= 256 * 1024 for config in configs))

    def test_standard_profile_names_and_configs_are_unique(self) -> None:
        configs, seeds, attempts = profile("standard")
        self.assertEqual(len(configs), 9)
        self.assertEqual(len({config.name for config in configs}), len(configs))
        self.assertEqual(len({config for config in configs}), len(configs))
        self.assertEqual((seeds, attempts), (8, 20))
        self.assertNotIn("program_instructions", configs[0].__dict__)

    def test_seed_derivation_is_reproducible_and_version_separated(self) -> None:
        self.assertEqual(seed_for(7), seed_for(7))
        self.assertNotEqual(seed_for(7), seed_for(8))
        self.assertEqual(len(seed_for(7)), 48)

    def test_integer_summary_preserves_raw_scale(self) -> None:
        self.assertEqual(integer_summary([10, 20, 30]), {
            "min": 10,
            "median": 20,
            "mean": 20,
            "max": 30,
            "spread_ppm": 2_000_000,
        })

    def test_unknown_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported profile"):
            profile("unknown")

    def test_build_matrix_rejects_unbounded_samples_before_execution(self) -> None:
        with self.assertRaisesRegex(ValueError, "seeds must"):
            build_matrix(None, "smoke", seeds=129)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
