# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for compact direct-dependency checkpoint bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.bounded_reconstruction import (
    _initial_machine_state,
    _mix_step,
)
from contrib.pow_research_v1.checkpoint_recursive_regeneration import (
    reconstruct_repeatedly_with_dependency_bundles,
)
from contrib.pow_research_v1.powvm import MASK64, Params, prepare_epoch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = (
    ROOT
    / "contrib"
    / "pow_research_v1"
    / "vectors"
    / "dependency_bundle_regeneration_v0.json"
)


class _FullScratch:
    def __init__(self, size: int) -> None:
        self.data = bytearray(size)
        self.words = size // 8

    def read(self, selector: int, *_unused: int) -> int:
        return struct.unpack_from(
            "<Q", self.data, (selector & (self.words - 1)) * 8
        )[0]

    def write(self, selector: int, value: int) -> None:
        struct.pack_into(
            "<Q", self.data, (selector & (self.words - 1)) * 8, value & MASK64
        )


def _oracle_value(context: object, header: bytes, nonce: int, stop: int, word: int) -> int:
    header_digest = hashlib.sha3_384(header).digest()
    nonce_bytes = struct.pack("<Q", nonce)
    registers, accumulator = _initial_machine_state(context, header_digest, nonce_bytes)
    scratch = _FullScratch(context.params.scratchpad_bytes)
    for iteration in range(stop):
        accumulator = _mix_step(context, scratch, registers, accumulator, iteration)
    return scratch.read(word)


class DependencyBundleRegenerationV1Test(unittest.TestCase):
    def test_selected_standard_configuration_sets_new_prefix_record(self) -> None:
        params, _ = profile("standard")
        context = prepare_epoch(seed_for(0), params)
        result = reconstruct_repeatedly_with_dependency_bundles(
            context, HEADER, 0
        )
        self.assertEqual(
            result.status, "refused_dependency_bundle_regeneration_exhausted"
        )
        self.assertEqual(result.completed_iterations, 1_006)
        self.assertEqual(result.reconstructed_misses, 55)
        self.assertEqual(result.maximum_depth, 3)
        self.assertEqual(result.checkpoint_hits, 2)
        self.assertEqual(result.regeneration_iterations, 1_000_000)
        self.assertEqual(result.layout.checkpoint_entry_bytes, 120)
        self.assertEqual(result.layout.checkpoint_capacity, 12)
        self.assertIsNone(result.execution_result)
        boundary = result.first_reconstruction
        self.assertIsNotNone(boundary)
        self.assertEqual(
            boundary.value,  # type: ignore[union-attr]
            _oracle_value(
                context,
                HEADER,
                0,
                boundary.consumer,  # type: ignore[union-attr]
                boundary.word,  # type: ignore[union-attr]
            ),
        )

    def test_work_limit_fails_closed(self) -> None:
        params, _ = profile("smoke")
        result = reconstruct_repeatedly_with_dependency_bundles(
            prepare_epoch(seed_for(0), params), HEADER, 0, work_limit=100
        )
        self.assertEqual(
            result.status, "refused_dependency_bundle_regeneration_exhausted"
        )
        self.assertEqual(result.exhaustion.reason, "work_limit")  # type: ignore[union-attr]
        self.assertIsNone(result.execution_result)

    def test_bundle_width_is_bounded(self) -> None:
        params, _ = profile("smoke")
        context = prepare_epoch(seed_for(0), params)
        for width in (1, 5):
            with self.subTest(width=width), self.assertRaises(ValueError):
                reconstruct_repeatedly_with_dependency_bundles(
                    context, HEADER, 0, dependency_bundle_width=width
                )

    def test_fixed_boundaries(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params = Params(**source["params"])
        for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
            self.assertEqual(vector["name"], expected["name"])
            result = reconstruct_repeatedly_with_dependency_bundles(
                prepare_epoch(bytes.fromhex(vector["seed"]), params),
                bytes.fromhex(vector["header"]),
                vector["nonce"],
            ).to_dict()
            self.assertEqual(result["layout"], fixed["layout"])
            self.assertEqual(
                [result[field] for field in fixed["counter_fields"]],
                expected["counters"],
            )
            for key in ("first", "last"):
                boundary = result[f"{key}_reconstruction"]
                if expected[key] is None:
                    self.assertIsNone(boundary)
                else:
                    self.assertEqual(
                        [boundary[field] for field in fixed["boundary_fields"]],
                        expected[key],
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
