# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Unit tests for the PoW v1 budgeted cache lower-bound screen."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from contrib.pow_research_cpp.budgeted_cache_screen_v1 import profile
from contrib.pow_research_cpp.render_budgeted_cache_report_v1 import render


ROOT = Path(__file__).resolve().parents[2]
METHOD = ROOT / "contrib" / "pow_research_v1" / "budgeted_cache_screen_v0.json"


class BudgetedCacheScreenV1Test(unittest.TestCase):
    def test_standard_profile_matches_candidate(self) -> None:
        config, seeds = profile("standard")
        self.assertEqual(seeds, 8)
        self.assertEqual(config["scratchpad_bytes"], 256 * 1024)
        self.assertEqual(config["passes"], 3)

    def test_unknown_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported profile"):
            profile("large")

    def test_method_keeps_gate_open_and_accounts_metadata(self) -> None:
        method = json.loads(METHOD.read_text(encoding="utf-8"))
        self.assertEqual(method["gate_mapping"]["status"], "NOT_ASSESSED")
        self.assertEqual(method["accounting"]["compact_entry_bytes"], 16)
        self.assertEqual(method["accounting"]["conservative_entry_bytes"], 24)
        self.assertIn(
            "cache misses do not recompute values or produce a valid proof",
            method["gate_mapping"]["why_not_decisive"],
        )

    def test_report_presents_oracle_as_lower_bound(self) -> None:
        def scenario(entry: int, capacity: int, lru_miss: int, oracle_miss: int) -> dict[str, object]:
            return {
                "budget_bytes": 4096,
                "entry_bytes": entry,
                "lru": {
                    "capacity_words": {"median": capacity},
                    "miss_share_ppm": {"median": lru_miss},
                },
                "offline_optimal": {
                    "capacity_words": {"median": capacity},
                    "miss_share_ppm": {"median": oracle_miss},
                },
            }
        matrix = {
            "format": "soveroot-pow-v1-budgeted-cache-matrix-v0",
            "source_revision": "abc",
            "profile": "smoke",
            "seed_count": 1,
            "config": {"scratchpad_bytes": 8192},
            "summaries": {
                "compact_half_budget": scenario(16, 256, 700_000, 500_000),
                "conservative_half_budget": scenario(24, 170, 800_000, 600_000),
            },
            "cases": [{
                "seed_index": 0,
                "materialized_reads": 1000,
                "scenarios": {
                    "conservative_half_budget": {
                        "lru": {"materialized_read_misses": 800, "miss_share_ppm": 800_000},
                        "offline_optimal": {"materialized_read_misses": 600, "miss_share_ppm": 600_000},
                    },
                },
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(json.dumps(matrix), encoding="utf-8")
            report = render(path, METHOD, "unit test")
        self.assertIn("TIME-MEMORY GATE NOT ASSESSED", report)
        self.assertIn("Offline-optimal miss share", report)
        self.assertIn("60.00%", report)
        self.assertIn("lower bound", report)
        self.assertIn("mandatory time-memory gate remains open", report)


if __name__ == "__main__":
    unittest.main()
