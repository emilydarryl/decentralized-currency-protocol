#!/usr/bin/env python3
# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Exhaustive idealized model of an XOR-key withholding defense.

This is not a cryptographic implementation. It models fixed-width integers in
which the public high bits of a mask are zero. A worker can recognize shares
from those public bits but cannot observe the hidden mask suffix.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass


Strategy = Callable[[int, int], bool]


@dataclass(frozen=True)
class StrategyResult:
    name: str
    selected_shares: int
    total_shares: int
    hidden_masks: int
    selected_cases: int
    block_cases: int
    selected_fraction: float
    block_probability_given_selected: float
    expected_block_probability: float


def validate_parameters(width: int, clear_bits: int, block_bits: int) -> None:
    if width < 2:
        raise ValueError("width must be at least two bits")
    if not 0 <= clear_bits < block_bits <= width:
        raise ValueError("require 0 <= clear_bits < block_bits <= width")
    if width > 20:
        raise ValueError("width above 20 is intentionally refused by this exhaustive model")


def effective_mask(mask_suffix: int, width: int, clear_bits: int) -> int:
    """Return a mask whose clear_bits most-significant bits are zero."""
    if not 0 <= clear_bits <= width:
        raise ValueError("clear_bits must be within the modeled width")
    suffix_bits = width - clear_bits
    if not 0 <= mask_suffix < (1 << suffix_bits):
        raise ValueError("mask suffix does not fit")
    return mask_suffix


def is_share(raw_value: int, width: int, clear_bits: int) -> bool:
    """Use a power-of-two share target represented by clear leading bits."""
    return 0 <= raw_value < (1 << (width - clear_bits))


def is_block(final_value: int, width: int, block_bits: int) -> bool:
    """Use a power-of-two network target represented by block leading bits."""
    return 0 <= final_value < (1 << (width - block_bits))


def analyze_strategy(
    name: str,
    strategy: Strategy,
    *,
    width: int,
    clear_bits: int,
    block_bits: int,
) -> StrategyResult:
    validate_parameters(width, clear_bits, block_bits)
    shares = range(1 << (width - clear_bits))
    masks = range(1 << (width - clear_bits))
    selected = [raw for raw in shares if strategy(raw, width - clear_bits)]
    if not selected:
        raise ValueError(f"strategy {name!r} selects no shares")

    block_cases = 0
    for mask_suffix in masks:
        mask = effective_mask(mask_suffix, width, clear_bits)
        for raw in selected:
            assert is_share(raw, width, clear_bits)
            block_cases += is_block(raw ^ mask, width, block_bits)

    selected_cases = len(selected) * len(masks)
    return StrategyResult(
        name=name,
        selected_shares=len(selected),
        total_shares=len(shares),
        hidden_masks=len(masks),
        selected_cases=selected_cases,
        block_cases=block_cases,
        selected_fraction=len(selected) / len(shares),
        block_probability_given_selected=block_cases / selected_cases,
        expected_block_probability=1 / (1 << (block_bits - clear_bits)),
    )


def build_report(width: int, clear_bits: int, block_bits: int) -> dict[str, object]:
    suffix_bits = width - clear_bits
    strategies: dict[str, Strategy] = {
        "all_visible_shares": lambda _raw, _bits: True,
        "even_visible_values": lambda raw, _bits: raw % 2 == 0,
        "low_visible_quarter": lambda raw, bits: raw < (1 << max(bits - 2, 0)),
        "visible_suffix_zero": lambda raw, _bits: raw == 0,
    }
    results = [
        analyze_strategy(
            name,
            strategy,
            width=width,
            clear_bits=clear_bits,
            block_bits=block_bits,
        )
        for name, strategy in strategies.items()
    ]
    expected = 1 / (1 << (block_bits - clear_bits))
    return {
        "model": "xor-withholding-leading-zero-v0",
        "status": "idealized-non-consensus",
        "parameters": {
            "width": width,
            "clear_bits": clear_bits,
            "hidden_network_target_bits": block_bits - clear_bits,
            "block_bits": block_bits,
            "visible_suffix_bits": suffix_bits,
        },
        "claim": (
            "Under a uniform unknown suffix mask, selection using only the visible "
            "raw value does not improve the conditional block probability."
        ),
        "expected_block_probability_per_share": expected,
        "strategies": [asdict(result) for result in results],
        "limitations": [
            "power-of-two leading-zero targets only",
            "mask averaged uniformly rather than derived by a hash",
            "no adaptive share-response leakage",
            "no Stratum, key-release, payout, timing, or coordinator model",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=12)
    parser.add_argument("--clear-bits", type=int, default=4)
    parser.add_argument("--block-bits", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(build_report(args.width, args.clear_bits, args.block_bits), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
