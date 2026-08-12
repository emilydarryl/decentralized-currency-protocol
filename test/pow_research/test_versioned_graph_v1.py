# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Unit tests for the exact versioned PoW v1 scratch-dependency graph."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from contrib.pow_research_cpp.versioned_graph_v1 import build_matrix
from contrib.pow_research_v1.powvm import Params, evaluate, prepare_epoch
from contrib.pow_research_v1.versioned_graph import evaluate_versioned_graph


ROOT = Path(__file__).resolve().parents[2]
METHOD = ROOT / "contrib" / "pow_research_v1" / "versioned_graph_v0.json"
CANONICAL_VECTORS = ROOT / "contrib" / "pow_research_v1" / "vectors" / "versioned_graph_v0.json"
PROFILE_VECTORS = ROOT / "contrib" / "pow_research_v1" / "vectors" / "versioned_graph_profiles_v0.json"


class VersionedGraphV1Test(unittest.TestCase):
    def test_observer_preserves_canonical_output_and_fixed_commitment(self) -> None:
        vectors = json.loads(CANONICAL_VECTORS.read_text(encoding="utf-8"))
        params = Params(**vectors["params"])
        vector = vectors["vectors"][0]
        context = prepare_epoch(bytes.fromhex(vector["seed"]), params)
        ordinary = evaluate(context, bytes.fromhex(vector["header"]), vector["nonce"])
        observed, graph = evaluate_versioned_graph(
            context,
            bytes.fromhex(vector["header"]),
            vector["nonce"],
        )
        self.assertEqual(observed, ordinary)
        self.assertEqual(graph["graph_commitment"], vector["graph_commitment"])
        self.assertEqual(graph["read_edges"], graph["initial_zero_edges"] + graph["materialized_edges"])
        self.assertEqual(graph["mix_iterations"], 2048)
        self.assertEqual(graph["write_versions"], 4096)

    def test_fixed_profile_commitments_and_byte_models(self) -> None:
        expected = json.loads(PROFILE_VECTORS.read_text(encoding="utf-8"))["profiles"]
        for profile_name in ("smoke", "standard"):
            matrix = build_matrix(profile_name)
            profile = expected[profile_name]
            self.assertEqual(matrix["params"], profile["params"])
            self.assertEqual(len(matrix["cases"]), len(profile["cases"]))
            for case, fixed in zip(matrix["cases"], profile["cases"], strict=True):
                graph = case["graph"]
                self.assertEqual(case["seed_index"], fixed["seed_index"])
                self.assertEqual(graph["graph_commitment"], fixed["graph_commitment"])
                self.assertEqual(graph["initial_zero_edges"], fixed["initial_zero_edges"])
                self.assertEqual(graph["materialized_edges"], fixed["materialized_edges"])
                self.assertEqual(graph["mix_iterations"], profile["mix_iterations"])
                self.assertEqual(graph["read_edges"], profile["read_edges"])
                self.assertEqual(graph["write_versions"], profile["write_versions"])
            if profile_name == "standard":
                graph = matrix["cases"][0]["graph"]
                self.assertEqual(graph["canonical_encoding"]["encoded_bytes"], profile["canonical_encoded_bytes"])
                self.assertEqual(graph["logical_layouts"]["packed"]["logical_model_bytes"], profile["packed_logical_model_bytes"])
                self.assertEqual(graph["logical_layouts"]["conservative"]["logical_model_bytes"], profile["conservative_logical_model_bytes"])

    def test_method_forbids_gate_claims(self) -> None:
        method = json.loads(METHOD.read_text(encoding="utf-8"))
        self.assertIn("FULL-MEMORY", method["status"])
        self.assertIn("no proof-of-work evaluation gate is assessed", method["limitations"])
        self.assertIn("never executable attack evidence", method["next_use"])


if __name__ == "__main__":
    unittest.main()
