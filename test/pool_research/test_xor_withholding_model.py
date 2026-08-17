#!/usr/bin/env python3
# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for the idealized XOR-key worker-withholding model."""

import unittest

from contrib.pool_research.xor_withholding_model import (
    analyze_strategy,
    build_report,
    effective_mask,
    is_block,
    is_share,
    validate_parameters,
)


class XorWithholdingModelTest(unittest.TestCase):
    def test_mask_preserves_clear_prefix(self) -> None:
        width = 8
        clear_bits = 3
        for suffix in range(1 << (width - clear_bits)):
            mask = effective_mask(suffix, width, clear_bits)
            self.assertEqual(mask >> (width - clear_bits), 0)

    def test_visible_share_prefix_survives_mask(self) -> None:
        width = 8
        clear_bits = 3
        for raw in range(1 << width):
            for suffix in range(1 << (width - clear_bits)):
                final = raw ^ effective_mask(suffix, width, clear_bits)
                self.assertEqual(
                    is_share(raw, width, clear_bits),
                    is_share(final, width, clear_bits),
                )

    def test_visible_selection_does_not_improve_block_probability(self) -> None:
        expected = 1 / 8
        strategies = {
            "all": lambda _raw, _bits: True,
            "even": lambda raw, _bits: raw % 2 == 0,
            "one": lambda raw, _bits: raw == 7,
            "upper_half": lambda raw, bits: raw >= (1 << (bits - 1)),
        }
        for name, strategy in strategies.items():
            with self.subTest(name=name):
                result = analyze_strategy(
                    name,
                    strategy,
                    width=8,
                    clear_bits=2,
                    block_bits=5,
                )
                self.assertEqual(result.block_probability_given_selected, expected)
                self.assertEqual(result.expected_block_probability, expected)

    def test_report_is_explicitly_non_consensus(self) -> None:
        report = build_report(width=8, clear_bits=2, block_bits=5)
        self.assertEqual(report["status"], "idealized-non-consensus")
        self.assertEqual(report["parameters"]["hidden_network_target_bits"], 3)
        for result in report["strategies"]:
            self.assertEqual(
                result["block_probability_given_selected"],
                report["expected_block_probability_per_share"],
            )

    def test_network_target_is_harder_than_visible_share_target(self) -> None:
        self.assertTrue(is_share(7, width=8, clear_bits=2))
        self.assertFalse(is_block(7, width=8, block_bits=6))

    def test_invalid_parameters_fail_closed(self) -> None:
        for parameters in ((8, 4, 4), (8, 5, 4), (8, -1, 4), (21, 1, 4)):
            with self.subTest(parameters=parameters):
                with self.assertRaises(ValueError):
                    validate_parameters(*parameters)


if __name__ == "__main__":
    unittest.main()
