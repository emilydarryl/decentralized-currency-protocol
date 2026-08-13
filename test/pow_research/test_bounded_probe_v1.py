# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for the fail-closed v1 online bounded probe."""

from __future__ import annotations

import unittest
import json
from pathlib import Path
import tempfile

from contrib.pow_research_cpp.bounded_probe_v1 import build_matrix
from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.render_bounded_probe_report_v1 import render
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.bounded_probe import probe_bounded_evaluator
from contrib.pow_research_v1.powvm import Params, prepare_epoch


ROOT = Path(__file__).resolve().parents[2]
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "bounded_probe_v0.json"
METHOD = ROOT / "contrib" / "pow_research_v1" / "bounded_probe_v0.json"
SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"


class BoundedProbeV1Test(unittest.TestCase):
    def test_smoke_probe_refuses_deterministically_within_budget(self) -> None:
        params, _ = profile("smoke")
        context = prepare_epoch(seed_for(0), params)
        first = probe_bounded_evaluator(context, HEADER, 0)
        second = probe_bounded_evaluator(context, HEADER, 0)
        self.assertEqual(first, second)
        self.assertEqual(first.status, "refused_materialized_miss")
        self.assertIsNone(first.execution_result)
        self.assertEqual(first.materialized_misses, 1)
        self.assertEqual(first.layout.admitted_bytes, params.scratchpad_bytes // 2)
        self.assertLessEqual(first.layout.admitted_bytes, first.layout.budget_bytes)
        self.assertEqual(len(first.state_commitment or ""), 96)

    def test_first_canonical_boundary_is_fixed(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        vector = source["vectors"][0]
        expected = fixed["cases"][0]
        context = prepare_epoch(bytes.fromhex(vector["seed"]), Params(**source["params"]))
        probe = probe_bounded_evaluator(
            context,
            bytes.fromhex(vector["header"]),
            vector["nonce"],
        )
        self.assertEqual(probe.completed_iterations, expected["completed_iterations"])
        self.assertEqual(probe.miss_word, expected["miss"]["word"])
        self.assertEqual(probe.state_commitment, expected["state_commitment"])

    def test_invalid_budget_fails_before_execution(self) -> None:
        params, _ = profile("smoke")
        context = prepare_epoch(seed_for(0), params)
        with self.assertRaisesRegex(ValueError, "budget_bytes"):
            probe_bounded_evaluator(context, HEADER, 0, budget_bytes=0)
        with self.assertRaisesRegex(ValueError, "fixed reserve"):
            probe_bounded_evaluator(context, HEADER, 0, budget_bytes=512)

    def test_standard_matrix_refuses_without_outputs(self) -> None:
        matrix = build_matrix("standard", seeds=2, source_revision="abc")
        self.assertTrue(matrix["all_runs_refused_without_digest"])
        for case in matrix["cases"]:
            self.assertEqual(case["status"], "refused_materialized_miss")
            self.assertIsNone(case["execution_result"])
            self.assertEqual(case["layout"]["budget_bytes"], 131072)
            self.assertEqual(case["layout"]["admitted_bytes"], 131072)

    def test_method_and_report_keep_gate_open(self) -> None:
        method = json.loads(METHOD.read_text(encoding="utf-8"))
        self.assertEqual(method["gate_mapping"]["time_memory_tradeoff"], "NOT_ASSESSED")
        matrix = build_matrix("smoke", seeds=1, source_revision="abc")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(json.dumps(matrix), encoding="utf-8")
            report = render(path, METHOD, "unit test")
        self.assertIn("NO POW GATE ASSESSED", report)
        self.assertIn("refused without a digest", report)
        self.assertIn("does not reconstruct", report)


if __name__ == "__main__":
    unittest.main()
