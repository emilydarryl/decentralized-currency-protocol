# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for first bounded recursive value regeneration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import unittest

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.bounded_reconstruction import _initial_machine_state, _mix_step
from contrib.pow_research_v1.powvm import MASK64, Params, prepare_epoch
from contrib.pow_research_v1.recursive_regeneration import reconstruct_first_recursively


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "recursive_regeneration_v0.json"


class _FullScratch:
    def __init__(self, size: int) -> None:
        self.data = bytearray(size)
        self.words = size // 8

    def read(self, selector: int, *_unused: int) -> int:
        return struct.unpack_from("<Q", self.data, (selector & (self.words - 1)) * 8)[0]

    def write(self, selector: int, value: int) -> None:
        struct.pack_into("<Q", self.data, (selector & (self.words - 1)) * 8, value & MASK64)


def _oracle_value(context: object, header: bytes, nonce: int, stop: int, word: int) -> int:
    header_digest = hashlib.sha3_384(header).digest()
    nonce_bytes = struct.pack("<Q", nonce)
    registers, accumulator = _initial_machine_state(context, header_digest, nonce_bytes)
    scratch = _FullScratch(context.params.scratchpad_bytes)
    for iteration in range(stop):
        accumulator = _mix_step(context, scratch, registers, accumulator, iteration)
    return scratch.read(word)


class RecursiveRegenerationV1Test(unittest.TestCase):
    def test_standard_regenerates_one_value_then_refuses(self) -> None:
        params, _ = profile("standard")
        context = prepare_epoch(seed_for(0), params)
        result = reconstruct_first_recursively(context, HEADER, 0)
        self.assertEqual(result.status, "refused_after_first_recursive_regeneration")
        self.assertEqual(result.layout.admitted_bytes, params.scratchpad_bytes // 2)
        self.assertEqual(result.reconstructed_misses, 1)
        self.assertEqual(result.completed_iterations, 270)
        self.assertIsNotNone(result.first_reconstruction)
        boundary = result.first_reconstruction
        self.assertEqual(boundary.maximum_depth, 3)  # type: ignore[union-attr]
        self.assertEqual(
            boundary.value,  # type: ignore[union-attr]
            _oracle_value(context, HEADER, 0, boundary.consumer, boundary.word),  # type: ignore[union-attr]
        )

    def test_work_limit_fails_closed(self) -> None:
        params, _ = profile("smoke")
        result = reconstruct_first_recursively(
            prepare_epoch(seed_for(0), params), HEADER, 0, work_limit=100
        )
        self.assertEqual(result.status, "refused_recursive_regeneration_exhausted")
        self.assertEqual(result.exhaustion.reason, "work_limit")  # type: ignore[union-attr]
        self.assertEqual(result.reconstructed_misses, 0)

    def test_fixed_boundaries_and_oracle_values(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params = Params(**source["params"])
        for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
            self.assertEqual(vector["name"], expected["name"])
            context = prepare_epoch(bytes.fromhex(vector["seed"]), params)
            result = reconstruct_first_recursively(
                context, bytes.fromhex(vector["header"]), vector["nonce"]
            ).to_dict()
            self.assertEqual(result["layout"], fixed["layout"])
            self.assertEqual(
                [result[field] for field in fixed["counter_fields"]], expected["counters"]
            )
            self.assertEqual(
                [result["first_reconstruction"][field] for field in fixed["boundary_fields"]],
                expected["first"],
            )
            self.assertEqual(
                [result[field] for field in fixed["refusal_fields"]], expected["refusal"]
            )
            self.assertEqual(result["transcript_commitment"], expected["transcript_commitment"])
            boundary = result["first_reconstruction"]
            self.assertEqual(
                boundary["value"],
                _oracle_value(
                    context, bytes.fromhex(vector["header"]), vector["nonce"],
                    boundary["consumer"], boundary["word"],
                ),
            )


if __name__ == "__main__":
    unittest.main()
