# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render a narrowly scoped report for the v1 cut-set pebbling bound."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics


def render(matrix_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix["format"] != "soveroot-pow-v1-pebbling-lower-bound-matrix-v0":
        raise ValueError("unsupported pebbling matrix format")
    if method["format"] != "soveroot-pow-v1-pebbling-lower-bound-method-v0":
        raise ValueError("unsupported pebbling method format")

    def median(layout: str, field: str) -> int | float:
        return statistics.median(case["bounds"][layout][field] for case in matrix["cases"])

    def number(value: int | float) -> str:
        if isinstance(value, float) and not value.is_integer():
            return f"{value:,.1f}"
        return f"{int(value):,}"

    lines = [
        f"# Soveroot PoW v1 Offline Pebbling Lower Bound: {label}",
        "",
        "**NON-CONSENSUS OPTIMISTIC OFFLINE DIAGNOSTIC — NO POW GATE ASSESSED**",
        "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`",
        "",
        "## Result",
        "",
        "| Layout | Capacity | Median peak live | Median values over budget | Median unavoidable producer replays |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for layout in ("compact", "conservative"):
        capacity = matrix["budget"]["layouts"][layout]["capacity_values"]
        lines.append(
            f"| {layout.title()} ({matrix['budget']['layouts'][layout]['value_entry_bytes']} B/value) "
            f"| {capacity:,} | {number(median(layout, 'peak_live_values'))} "
            f"| {number(median(layout, 'values_over_capacity'))} "
            f"| {number(median(layout, 'additional_producer_executions_min'))} |"
        )
    lines.extend([
        "",
        "At the strongest cut, every value beyond capacity has a future read. It must be retained or regenerated. The bound groups two missing values into one replay whenever they share a producer, which is the most favorable possible accounting for this workload.",
        "",
        "## Why this is only a lower bound",
        "",
    ])
    lines.extend(f"- {item}" for item in matrix["relaxations"])
    lines.extend([
        "",
        "The planner holds the complete full-memory graph and uses future knowledge. It does not execute a valid proof with reduced memory, estimate throughput, or satisfy the two-model and controlled-hardware requirements. The mandatory time-memory gate remains open.",
        "",
        "## Per-seed evidence",
        "",
        "| Seed | Graph commitment | Compact replay minimum | Conservative replay minimum |",
        "| ---: | --- | ---: | ---: |",
    ])
    for case in matrix["cases"]:
        lines.append(
            f"| {case['seed_index']} | `{case['graph_commitment']}` "
            f"| {case['bounds']['compact']['additional_producer_executions_min']:,} "
            f"| {case['bounds']['conservative']['additional_producer_executions_min']:,} |"
        )
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
