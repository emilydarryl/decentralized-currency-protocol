# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for the optimistic v1 cut-set pebbling lower bound."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from contrib.pow_research_cpp.pebbling_lower_bound_v1 import build_matrix
from contrib.pow_research_cpp.render_pebbling_lower_bound_report_v1 import render
from contrib.pow_research_v1.pebbling_lower_bound import cut_set_lower_bound
from contrib.pow_research_v1.versioned_graph import CapturedVersionedGraph


ROOT = Path(__file__).resolve().parents[2]
METHOD = ROOT / "contrib" / "pow_research_v1" / "pebbling_lower_bound_v0.json"
VECTORS = ROOT / "contrib" / "pow_research_v1" / "vectors" / "pebbling_lower_bound_v0.json"


class PebblingLowerBoundV1Test(unittest.TestCase):
    def test_cut_groups_two_live_outputs_from_one_producer(self) -> None:
        graph = CapturedVersionedGraph(
            events=((1, 1), (1, 2), (1, 3), (1, 4), (0, 1), (0, 2), (0, 3), (0, 4)),
            version_producers=(None, 0, 0, 1, 1),
        )
        bound = cut_set_lower_bound(graph, budget_bytes=1, value_entry_bytes=1)
        self.assertEqual(bound.peak_live_values, 4)
        self.assertEqual(bound.values_over_capacity, 3)
        self.assertEqual(bound.paired_producers_at_strongest_cut, 2)
        self.assertEqual(bound.additional_producer_executions_min, 2)

    def test_invalid_budget_is_rejected(self) -> None:
        graph = CapturedVersionedGraph(events=(), version_producers=(None,))
        with self.assertRaisesRegex(ValueError, "budget_bytes"):
            cut_set_lower_bound(graph, budget_bytes=0, value_entry_bytes=16)
        with self.assertRaisesRegex(ValueError, "cannot hold"):
            cut_set_lower_bound(graph, budget_bytes=8, value_entry_bytes=16)

    def test_fixed_smoke_bounds(self) -> None:
        fixed = json.loads(VECTORS.read_text(encoding="utf-8"))["profiles"]["smoke"]
        matrix = build_matrix("smoke")
        self.assertEqual(matrix["budget"]["bytes"], fixed["budget_bytes"])
        self.assertEqual(matrix["budget"]["schedule_bytes_charged"], 0)
        for case, expected in zip(matrix["cases"], fixed["cases"], strict=True):
            self.assertEqual(case["seed_index"], expected["seed_index"])
            self.assertEqual(case["graph_commitment"], expected["graph_commitment"])
            self.assertEqual(case["bounds"]["compact"]["additional_producer_executions_min"], expected["compact_replay_min"])
            self.assertEqual(case["bounds"]["conservative"]["additional_producer_executions_min"], expected["conservative_replay_min"])

    def test_first_standard_bound_is_fixed(self) -> None:
        fixed = json.loads(VECTORS.read_text(encoding="utf-8"))["profiles"]["standard"]
        matrix = build_matrix("standard", seeds=1)
        case = matrix["cases"][0]
        expected = fixed["cases"][0]
        self.assertEqual(matrix["budget"]["bytes"], fixed["budget_bytes"])
        self.assertEqual(case["mix_iterations"], fixed["mix_iterations"])
        self.assertEqual(case["graph_commitment"], expected["graph_commitment"])
        self.assertEqual(case["bounds"]["compact"]["additional_producer_executions_min"], expected["compact_replay_min"])
        self.assertEqual(case["bounds"]["conservative"]["additional_producer_executions_min"], expected["conservative_replay_min"])

    def test_method_and_report_forbid_gate_claim(self) -> None:
        method = json.loads(METHOD.read_text(encoding="utf-8"))
        self.assertEqual(method["gate_mapping"]["time_memory_tradeoff"], "NOT_ASSESSED")
        matrix = build_matrix("smoke", seeds=1, source_revision="abc")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(json.dumps(matrix), encoding="utf-8")
            report = render(path, METHOD, "unit test")
        self.assertIn("NO POW GATE ASSESSED", report)
        self.assertIn("perfect knowledge", report)
        self.assertIn("mandatory time-memory gate remains open", report)


if __name__ == "__main__":
    unittest.main()
