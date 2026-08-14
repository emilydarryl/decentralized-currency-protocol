# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Fail closed unless GCC reports bounded stack use for a selected symbol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_SYMBOL = "RecursiveRegenerator::ValueAt"
DEFAULT_ALLOWANCE_BYTES = 2_048
BOUNDED_QUALIFIERS = frozenset(("static", "dynamic,bounded"))


def parse_stack_usage(
    paths: list[Path], symbol: str = DEFAULT_SYMBOL
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if symbol not in line:
                continue
            fields = line.rsplit("\t", 2)
            if len(fields) != 3:
                raise ValueError(f"unrecognized stack-usage line: {line}")
            identity, encoded_bytes, qualifier = fields
            records.append(
                {
                    "source": str(path),
                    "identity": identity,
                    "bytes": int(encoded_bytes),
                    "qualifier": qualifier,
                }
            )
    return records


def maximum_bounded_stack_usage(
    records: list[dict[str, object]], symbol: str = DEFAULT_SYMBOL
) -> int:
    """Return the maximum compiler-bounded frame size, rejecting ambiguity."""

    if not records:
        raise AssertionError(f"no stack-usage record found for {symbol}")
    unbounded = [
        record for record in records
        if record["qualifier"] not in BOUNDED_QUALIFIERS
    ]
    if unbounded:
        raise AssertionError(f"unbounded stack usage reported: {unbounded}")
    return max(int(record["bytes"]) for record in records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stack_usage", nargs="+", type=Path)
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--allowance", type=int, default=DEFAULT_ALLOWANCE_BYTES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.allowance <= 0:
        parser.error("--allowance must be positive")
    records = parse_stack_usage(args.stack_usage, args.symbol)
    maximum = maximum_bounded_stack_usage(records, args.symbol)
    report = {
        "format": "soveroot-pow-v1-recursive-stack-usage-v0",
        "warning": "COMPILER-SPECIFIC DIAGNOSTIC; not controlled-host gate evidence",
        "symbol": args.symbol,
        "allowance_bytes_per_frame": args.allowance,
        "accepted_bounded_qualifiers": sorted(BOUNDED_QUALIFIERS),
        "maximum_reported_bounded_frame_bytes": maximum,
        "within_allowance": maximum <= args.allowance,
        "records": records,
    }
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    if maximum > args.allowance:
        raise AssertionError(
            f"reported frame {maximum} exceeds {args.allowance}-byte allowance"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
