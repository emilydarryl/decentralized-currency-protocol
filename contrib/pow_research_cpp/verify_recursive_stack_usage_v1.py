# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Fail closed unless GCC reports bounded RecursiveRegenerator stack use."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SYMBOL = "RecursiveRegenerator::ValueAt"
ALLOWANCE_BYTES = 2_048
BOUNDED_QUALIFIERS = frozenset(("static", "dynamic,bounded"))


def parse_stack_usage(paths: list[Path]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if SYMBOL not in line:
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


def maximum_bounded_stack_usage(records: list[dict[str, object]]) -> int:
    """Return the maximum compiler-bounded frame size, rejecting ambiguity."""

    if not records:
        raise AssertionError(f"no stack-usage record found for {SYMBOL}")
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    records = parse_stack_usage(args.stack_usage)
    maximum = maximum_bounded_stack_usage(records)
    report = {
        "format": "soveroot-pow-v1-recursive-stack-usage-v0",
        "warning": "COMPILER-SPECIFIC DIAGNOSTIC; not controlled-host gate evidence",
        "symbol": SYMBOL,
        "allowance_bytes_per_frame": ALLOWANCE_BYTES,
        "accepted_bounded_qualifiers": sorted(BOUNDED_QUALIFIERS),
        "maximum_reported_bounded_frame_bytes": maximum,
        "within_allowance": maximum <= ALLOWANCE_BYTES,
        "records": records,
    }
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    if maximum > ALLOWANCE_BYTES:
        raise AssertionError(
            f"reported frame {maximum} exceeds {ALLOWANCE_BYTES}-byte allowance"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
