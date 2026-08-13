# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for the optimistic graph-only v1 replay schedule."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from contrib.pow_research_cpp.offline_pebbling_schedule_v1 import build_matrix
from contrib.pow_research_cpp.render_offline_pebbling_schedule_report_v1 import render
from contrib.pow_research_v1.offline_pebbling_schedule import search_offline_pebbling_schedule
from contrib.pow_research_v1.versioned_graph import CapturedVersionedGraph


ROOT = Path(__file__).resolve().parents[2]
METHOD = ROOT / "contrib" / "pow_research_v1" / "offline_pebbling_schedule_v0.json"
VECTORS = ROOT / "contrib" / "pow_research_v1" / "vectors" / "offline_pebbling_schedule_v0.json"


class OfflinePebblingScheduleV1Test(unittest.TestCase):
    def test_recursive_schedule_replays_dependencies_in_postorder(self) -> None:
        # p0: 0,0 -> 1,2; p1: 1,0 -> 3,4; p2: 0,0 -> 5,6.
        # The final read order makes the oracle evict 3, forcing p0 then p1.
        graph = CapturedVersionedGraph(
            events=(
                (0, 0), (0, 0), (1, 1), (1, 2),
                (0, 1), (0, 0), (1, 3), (1, 4),
                (0, 0), (0, 0), (1, 5), (1, 6),
                (0, 5), (0, 6), (0, 3),
            ),
            version_producers=(None, 0, 0, 1, 1, 2, 2),
        )
        schedule = search_offline_pebbling_schedule(graph, budget_bytes=2, value_entry_bytes=1)
        self.assertEqual(schedule.capacity_values, 2)
        self.assertEqual(schedule.canonical_reads, 9)
        self.assertEqual(schedule.canonical_read_misses, 1)
        self.assertEqual(schedule.replayed_producers, 2)
        self.assertEqual(schedule.schedule_actions, 2)
        self.assertEqual(schedule.maximum_replay_depth, 2)
        self.assertLessEqual(schedule.peak_retained_values, 2)
        self.assertGreaterEqual(schedule.peak_transient_values, 3)
        self.assertEqual(schedule.schedule_bytes, len(b"Soveroot/PowResearch/OfflinePebblingSchedule/v1\x00") + 24 + 9 + 8)

    def test_schedule_is_deterministic(self) -> None:
        graph = CapturedVersionedGraph(
            events=((0, 0), (0, 0), (1, 1), (1, 2), (0, 1)),
            version_producers=(None, 0, 0),
        )
        first = search_offline_pebbling_schedule(graph, budget_bytes=2, value_entry_bytes=1)
        second = search_offline_pebbling_schedule(graph, budget_bytes=2, value_entry_bytes=1)
        self.assertEqual(first, second)

    def test_malformed_or_impossible_graph_is_rejected(self) -> None:
        malformed = CapturedVersionedGraph(events=((1, 1),), version_producers=(None, 0))
        with self.assertRaisesRegex(ValueError, "two outputs"):
            search_offline_pebbling_schedule(malformed, budget_bytes=2, value_entry_bytes=1)
        empty = CapturedVersionedGraph(events=(), version_producers=(None,))
        with self.assertRaisesRegex(ValueError, "at least two"):
            search_offline_pebbling_schedule(empty, budget_bytes=1, value_entry_bytes=1)

    def test_fixed_smoke_schedules(self) -> None:
        fixed = json.loads(VECTORS.read_text(encoding="utf-8"))["profiles"]["smoke"]
        matrix = build_matrix("smoke")
        self.assertEqual(matrix["budget"]["bytes"], fixed["budget_bytes"])
        self.assertEqual(matrix["budget"]["schedule_bytes_charged_to_value_capacity"], 0)
        fields = ("canonical_read_misses", "replayed_producers", "maximum_replay_depth", "schedule_bytes", "schedule_commitment")
        for case, expected in zip(matrix["cases"], fixed["cases"], strict=True):
            self.assertEqual(case["seed_index"], expected["seed_index"])
            self.assertEqual(case["graph_commitment"], expected["graph_commitment"])
            for layout in ("compact", "conservative"):
                self.assertEqual(tuple(case["schedules"][layout][field] for field in fields), tuple(expected[layout]))

    def test_method_and_report_forbid_gate_claim(self) -> None:
        method = json.loads(METHOD.read_text(encoding="utf-8"))
        self.assertEqual(method["gate_mapping"]["time_memory_tradeoff"], "NOT_ASSESSED")
        matrix = build_matrix("smoke", seeds=1, source_revision="abc")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(json.dumps(matrix), encoding="utf-8")
            report = render(path, METHOD, "unit test")
        self.assertIn("NO POW GATE ASSESSED", report)
        self.assertIn("not executable", report)
        self.assertIn("schedule bytes are disclosed", report)


if __name__ == "__main__":
    unittest.main()
