# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for the explicitly non-consensus PoW research harness."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from contrib.pow_research.benchmark import benchmark
from contrib.pow_research.generate_vectors import VECTOR_PARAMS, build_vectors
from contrib.pow_research.powvm import Params, evaluate, prepare_epoch
from contrib.pow_research.sweep import _powers_of_two


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VECTOR_FILE = REPOSITORY_ROOT / "contrib" / "pow_research" / "vectors" / "v0.json"


class PowVmResearchTest(unittest.TestCase):
    def test_checked_in_vectors_are_reproducible(self) -> None:
        expected = json.loads(VECTOR_FILE.read_text(encoding="utf-8"))
        self.assertEqual(build_vectors(), expected)

    def test_evaluation_is_deterministic_and_nonce_bound(self) -> None:
        context = prepare_epoch(bytes(range(48)), VECTOR_PARAMS)
        first = evaluate(context, b"deterministic header", 7)
        repeated = evaluate(context, b"deterministic header", 7)
        different_nonce = evaluate(context, b"deterministic header", 8)
        different_header = evaluate(context, b"different header", 7)
        self.assertEqual(first, repeated)
        self.assertNotEqual(first.digest, different_nonce.digest)
        self.assertNotEqual(first.digest, different_header.digest)
        self.assertEqual(len(first.digest), 48)

    def test_seed_changes_program_and_dataset(self) -> None:
        first = prepare_epoch(bytes(48), VECTOR_PARAMS)
        second = prepare_epoch(bytes.fromhex("01" * 48), VECTOR_PARAMS)
        self.assertNotEqual(first.program_digest, second.program_digest)
        self.assertNotEqual(first.dataset_digest, second.dataset_digest)

    def test_every_vector_program_has_balanced_opcodes(self) -> None:
        context = prepare_epoch(bytes(48), VECTOR_PARAMS)
        counts = [0] * 8
        for instruction in context.program:
            counts[instruction.opcode] += 1
        self.assertEqual(counts, [4] * 8)

    def test_parameter_and_input_bounds(self) -> None:
        with self.assertRaises(ValueError):
            Params(dataset_bytes=96 * 1024).validate()
        with self.assertRaises(ValueError):
            Params(scratchpad_bytes=1024).validate()
        with self.assertRaises(ValueError):
            prepare_epoch(bytes(47), VECTOR_PARAMS)
        context = prepare_epoch(bytes(48), VECTOR_PARAMS)
        with self.assertRaises(ValueError):
            evaluate(context, b"", 0)
        with self.assertRaises(ValueError):
            evaluate(context, b"header", 1 << 64)

    def test_benchmark_schema(self) -> None:
        report = benchmark(VECTOR_PARAMS, attempts=2)
        self.assertEqual(report["format"], "soveroot-pow-research-benchmark-v0")
        self.assertEqual(report["attempts"], 2)
        self.assertGreater(report["prepare_ns"], 0)
        self.assertGreater(report["attempt_ns"]["median"], 0)
        with self.assertRaises(ValueError):
            benchmark(VECTOR_PARAMS, attempts=0)

    def test_power_of_two_sweep(self) -> None:
        self.assertEqual(_powers_of_two(64, 512), [64, 128, 256, 512])
        with self.assertRaises(ValueError):
            _powers_of_two(64, 300)


if __name__ == "__main__":
    unittest.main()
