# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render a narrowly scoped report for the v1 graph-only replay schedule."""

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
    if matrix["format"] != "soveroot-pow-v1-offline-pebbling-schedule-matrix-v0":
        raise ValueError("unsupported schedule matrix format")
    if method["format"] != "soveroot-pow-v1-offline-pebbling-schedule-method-v0":
        raise ValueError("unsupported schedule method format")

    def median(layout: str, field: str) -> int | float:
        return statistics.median(case["schedules"][layout][field] for case in matrix["cases"])

    def number(value: int | float) -> str:
        if isinstance(value, float) and not value.is_integer():
            return f"{value:,.1f}"
        return f"{int(value):,}"

    lines = [
        f"# Soveroot PoW v1 Offline Pebbling Schedule: {label}",
        "",
        "**NON-CONSENSUS OPTIMISTIC GRAPH-ONLY SCHEDULE - NO POW GATE ASSESSED**",
        "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`",
        "",
        "## Result",
        "",
        "| Layout | Capacity | Median replayed producers | Median max depth | Median peak retained | Median encoded schedule |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for layout in ("compact", "conservative"):
        capacity = matrix["budget"]["layouts"][layout]["capacity_values"]
        lines.append(
            f"| {layout.title()} ({matrix['budget']['layouts'][layout]['value_entry_bytes']} B/value) "
            f"| {capacity:,} | {number(median(layout, 'replayed_producers'))} "
            f"| {number(median(layout, 'maximum_replay_depth'))} "
            f"| {number(median(layout, 'peak_retained_values'))} "
            f"| {number(median(layout, 'schedule_bytes'))} B |"
        )
    lines.extend([
        "",
        "The action stream is concrete in the scratch-version DAG: each miss names producer ordinals in recursive dependency postorder. It is not executable against the v1 VM because historical machine and address state are absent from that DAG.",
        "",
        "## Excluded costs",
        "",
    ])
    lines.extend(f"- {item}" for item in matrix["relaxations"])
    lines.extend([
        "",
        "The schedule bytes are disclosed rather than hidden. Adding them to peak retained payload exceeds the half-memory budget whenever the per-case over-budget field is nonzero. The planner does not measure valid proof throughput, satisfy the exact-output requirement, or assess the mandatory time-memory gate.",
        "",
        "## Per-seed evidence",
        "",
        "| Seed | Graph commitment | Compact replay / depth / schedule | Conservative replay / depth / schedule |",
        "| ---: | --- | ---: | ---: | ---: |",
    ])
    for case in matrix["cases"]:
        compact = case["schedules"]["compact"]
        conservative = case["schedules"]["conservative"]
        lines.append(
            f"| {case['seed_index']} | `{case['graph_commitment']}` "
            f"| {compact['replayed_producers']:,} / {compact['maximum_replay_depth']:,} / {compact['schedule_bytes']:,} B "
            f"| {conservative['replayed_producers']:,} / {conservative['maximum_replay_depth']:,} / {conservative['schedule_bytes']:,} B |"
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
