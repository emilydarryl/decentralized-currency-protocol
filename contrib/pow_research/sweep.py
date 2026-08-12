# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Sweep prototype memory and execution parameters and emit JSON results."""

from __future__ import annotations

import argparse
import json

from .benchmark import benchmark
from .powvm import Params


def _powers_of_two(start_kib: int, stop_kib: int) -> list[int]:
    if start_kib <= 0 or stop_kib < start_kib:
        raise ValueError("invalid sweep range")
    values = []
    value = start_kib
    while value <= stop_kib:
        values.append(value)
        value *= 2
    if values[-1] != stop_kib:
        raise ValueError("sweep endpoints must be connected by powers of two")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-kib", nargs=2, type=int, default=(64, 1024), metavar=("MIN", "MAX"))
    parser.add_argument("--scratchpad-kib", nargs=2, type=int, default=(8, 128), metavar=("MIN", "MAX"))
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--instructions", type=int, default=64)
    parser.add_argument("--passes", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.attempts <= 100:
        parser.error("--attempts must be in [1, 100]")

    try:
        datasets = _powers_of_two(*args.dataset_kib)
        scratchpads = _powers_of_two(*args.scratchpad_kib)
    except ValueError as error:
        parser.error(str(error))

    results = []
    for dataset_kib in datasets:
        for scratchpad_kib in scratchpads:
            params = Params(
                dataset_bytes=dataset_kib * 1024,
                scratchpad_bytes=scratchpad_kib * 1024,
                program_instructions=args.instructions,
                passes=args.passes,
            )
            try:
                params.validate()
            except ValueError as error:
                parser.error(str(error))
            results.append(benchmark(params, args.attempts))

    print(json.dumps({
        "format": "soveroot-pow-research-sweep-v0",
        "warning": "NON-CONSENSUS PROTOTYPE; compare trends, not absolute mining performance",
        "results": results,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
