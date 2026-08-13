# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the v1 indexed-gap reconstruction report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def render(matrix_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix["format"] != "soveroot-pow-v1-indexed-gap-reconstruction-matrix-v0":
        raise ValueError("unsupported indexed-gap matrix format")
    if method["format"] != "soveroot-pow-v1-indexed-gap-reconstruction-method-v0":
        raise ValueError("unsupported indexed-gap method format")
    lines = [
        f"# Soveroot PoW v1 Indexed-Gap Reconstruction: {label}", "",
        "**NON-CONSENSUS INDEXED-GAP PILOT - NO POW GATE ASSESSED**", "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`", "",
        "| Seed | Pages | Values | Utilization | Recoveries | Exact prefix | Index probes | Rebalances | Shifted bytes |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in matrix["cases"]:
        capacity = case["layout"]["replay_value_slots"]
        utilization = 100 * case["max_replay_peak_values"] / capacity
        lines.append(
            f"| {case['seed_index']} | {case['max_replay_peak_pages']:,} | {case['max_replay_peak_values']:,} "
            f"| {utilization:.2f}% | {case['reconstructed_misses']:,} | {case['completed_iterations']:,} "
            f"| {case['cumulative_index_probes']:,} | {case['cumulative_rebalances']:,} "
            f"| {case['cumulative_shifted_bytes']:,} |"
        )
    lines.extend([
        "", "The page-count index replaces linear page scans. Neighbor borrowing consumes adjacent gaps before a split, while every index probe, rebalance, and shifted byte remains charged.",
        "", "## Why the gate remains open", "",
    ])
    lines.extend(f"- {item}" for item in method["limitations"])
    lines.extend(["", "This is representation evidence, not a completed reduced-memory proof or controlled throughput benchmark."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--method", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = render(args.matrix, args.method, args.label)
    if args.output:
        args.output.write_text(report, encoding="utf-8", newline="\n")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
