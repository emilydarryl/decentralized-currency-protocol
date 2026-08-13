# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for repeated bounded recursive value regeneration."""

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
from contrib.pow_research_v1.repeated_recursive_regeneration import (
    reconstruct_repeatedly_recursively,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "repeated_recursive_regeneration_v0.json"


class _FullScratch:
    def __init__(self, size: int) -> None:
        self.data = bytearray(size)
        self.words = size // 8

    def read(self, selector: int, *_unused: int) -> int:
        return struct.unpack_from("<Q", self.data, (selector & (self.words - 1)) * 8)[0]

    def write(self, selector: int, value: int) -> None:
        struct.pack_into("<Q", self.data, (selector & (self.words - 1)) * 8, value & MASK64)


def _oracle_values(
    context: object,
    header: bytes,
    nonce: int,
    requests: set[tuple[int, int]],
) -> dict[tuple[int, int], int]:
    header_digest = hashlib.sha3_384(header).digest()
    nonce_bytes = struct.pack("<Q", nonce)
    registers, accumulator = _initial_machine_state(context, header_digest, nonce_bytes)
    scratch = _FullScratch(context.params.scratchpad_bytes)
    values: dict[tuple[int, int], int] = {}
    maximum_stop = max(stop for stop, _word in requests)
    for iteration in range(maximum_stop):
        accumulator = _mix_step(context, scratch, registers, accumulator, iteration)
        stop = iteration + 1
        for request_stop, word in requests:
            if request_stop == stop:
                values[(request_stop, word)] = scratch.read(word)
    return values


class RepeatedRecursiveRegenerationV1Test(unittest.TestCase):
    def test_standard_allocation_sweep(self) -> None:
        params, _ = profile("standard")
        context = prepare_epoch(seed_for(0), params)
        observed: dict[int, tuple[int, int]] = {}
        for denominator in (128, 64, 32, 16, 8):
            result = reconstruct_repeatedly_recursively(
                context, HEADER, 0, primary_denominator=denominator
            )
            self.assertEqual(result.status, "refused_recursive_regeneration_exhausted")
            self.assertIsNone(result.execution_result)
            self.assertEqual(result.regeneration_iterations, 1_000_000)
            self.assertGreater(result.reconstructed_misses, 1)
            observed[denominator] = (result.completed_iterations, result.reconstructed_misses)
        self.assertEqual(observed[64], (983, 51))
        self.assertEqual(observed[32], (999, 47))
        self.assertEqual(max(observed, key=lambda item: observed[item][0]), 32)

    def test_work_limit_fails_closed_before_first_recovery(self) -> None:
        params, _ = profile("smoke")
        result = reconstruct_repeatedly_recursively(
            prepare_epoch(seed_for(0), params), HEADER, 0, work_limit=100
        )
        self.assertEqual(result.status, "refused_recursive_regeneration_exhausted")
        self.assertEqual(result.exhaustion.reason, "work_limit")  # type: ignore[union-attr]
        self.assertEqual(result.reconstructed_misses, 0)
        self.assertIsNone(result.execution_result)

    def test_fixed_boundaries_and_full_memory_oracle(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = json.loads(FIXED.read_text(encoding="utf-8"))
        params = Params(**source["params"])
        for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
            self.assertEqual(vector["name"], expected["name"])
            header = bytes.fromhex(vector["header"])
            context = prepare_epoch(bytes.fromhex(vector["seed"]), params)
            result = reconstruct_repeatedly_recursively(
                context, header, vector["nonce"]
            ).to_dict()
            self.assertEqual(result["layout"], fixed["layout"])
            self.assertEqual(
                [result[field] for field in fixed["counter_fields"]], expected["counters"]
            )
            for key in ("first", "last"):
                self.assertEqual(
                    [result[f"{key}_reconstruction"][field] for field in fixed["boundary_fields"]],
                    expected[key],
                )
            self.assertEqual(
                [result["exhaustion"][field] for field in fixed["exhaustion_fields"]],
                expected["exhaustion"],
            )
            self.assertEqual(result["transcript_commitment"], expected["transcript_commitment"])
            requests = {
                (result["first_reconstruction"]["consumer"], result["first_reconstruction"]["word"]),
                (result["last_reconstruction"]["consumer"], result["last_reconstruction"]["word"]),
            }
            oracle = _oracle_values(context, header, vector["nonce"], requests)
            self.assertEqual(
                result["first_reconstruction"]["value"],
                oracle[(result["first_reconstruction"]["consumer"], result["first_reconstruction"]["word"])],
            )
            self.assertEqual(
                result["last_reconstruction"]["value"],
                oracle[(result["last_reconstruction"]["consumer"], result["last_reconstruction"]["word"])],
            )


if __name__ == "__main__":
    unittest.main()
