# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for the isolated, non-consensus PoW v1 research candidate."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from contrib.pow_research_v1.generate_vectors import VECTOR_PARAMS, build_vectors
from contrib.pow_research_v1.powvm import (
    ExecutionMetrics,
    FINAL_SAMPLE_WORDS,
    Params,
    evaluate,
    prepare_epoch,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VECTOR_FILE = REPOSITORY_ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"


class PowVmV1ResearchTest(unittest.TestCase):
    def test_checked_in_vectors_are_reproducible(self) -> None:
        expected = json.loads(VECTOR_FILE.read_text(encoding="utf-8"))
        self.assertEqual(build_vectors(), expected)

    def test_evaluation_is_deterministic_and_input_bound(self) -> None:
        context = prepare_epoch(bytes(range(48)), VECTOR_PARAMS)
        first = evaluate(context, b"deterministic v1 header", 7)
        repeated = evaluate(context, b"deterministic v1 header", 7)
        different_nonce = evaluate(context, b"deterministic v1 header", 8)
        different_header = evaluate(context, b"different v1 header", 7)
        self.assertEqual(first, repeated)
        self.assertNotEqual(first.digest, different_nonce.digest)
        self.assertNotEqual(first.digest, different_header.digest)
        self.assertEqual(len(first.digest), 48)
        self.assertEqual(len(first.memory_commitment), 48)

    def test_seed_changes_schedule_and_dataset(self) -> None:
        first = prepare_epoch(bytes(48), VECTOR_PARAMS)
        second = prepare_epoch(bytes.fromhex("01" * 48), VECTOR_PARAMS)
        self.assertNotEqual(first.schedule_digest, second.schedule_digest)
        self.assertNotEqual(first.dataset_digest, second.dataset_digest)

    def test_schedule_has_fixed_balanced_opcodes(self) -> None:
        context = prepare_epoch(bytes(48), VECTOR_PARAMS)
        counts = [0] * 8
        for entry in context.schedule:
            counts[entry.opcode] += 1
        self.assertEqual(counts, [8] * 8)

    def test_structural_work_counters_match_declared_memory(self) -> None:
        context = prepare_epoch(bytes(48), VECTOR_PARAMS)
        metrics = ExecutionMetrics()
        evaluate(context, b"v1 structural counters", 9, metrics=metrics)
        expected_iterations = VECTOR_PARAMS.scratchpad_bytes // 8 * VECTOR_PARAMS.passes
        self.assertEqual(metrics.mix_iterations, expected_iterations)
        self.assertEqual(metrics.mix_dataset_reads, expected_iterations)
        self.assertEqual(metrics.mix_scratchpad_reads, expected_iterations * 2)
        self.assertEqual(metrics.mix_scratchpad_writes, expected_iterations * 2)
        self.assertEqual(metrics.final_sample_reads, FINAL_SAMPLE_WORDS)
        self.assertLessEqual(metrics.finalization_input_bytes, 4096)

    def test_parameter_and_input_bounds(self) -> None:
        with self.assertRaises(ValueError):
            Params(dataset_bytes=96 * 1024).validate()
        with self.assertRaises(ValueError):
            Params(scratchpad_bytes=1024).validate()
        with self.assertRaises(ValueError):
            Params(passes=0).validate()
        with self.assertRaises(ValueError):
            prepare_epoch(bytes(47), VECTOR_PARAMS)
        context = prepare_epoch(bytes(48), VECTOR_PARAMS)
        with self.assertRaises(ValueError):
            evaluate(context, b"", 0)
        with self.assertRaises(ValueError):
            evaluate(context, b"header", 1 << 64)


if __name__ == "__main__":
    unittest.main()
