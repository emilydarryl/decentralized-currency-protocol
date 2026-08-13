# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the v1 offline time-checkpoint feasibility report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def render(matrix_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix["format"] != "soveroot-pow-v1-time-checkpoint-screen-matrix-v0":
        raise ValueError("unsupported time-checkpoint matrix format")
    if method["format"] != "soveroot-pow-v1-time-checkpoint-screen-method-v0":
        raise ValueError("unsupported time-checkpoint method format")
    lines = [
        f"# Soveroot PoW v1 Time-Checkpoint Screen: {label}", "",
        "**NON-CONSENSUS FULL-MEMORY OFFLINE SCREEN - NO POW GATE ASSESSED**", "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`", "",
        "| Seed | Half budget | Global live max | Optimistic bytes | Best naive bytes | Naive cut fits | Optimistic cut fits |",
        "| ---: | ---: | ---: | ---: | ---: | :---: | :---: |",
    ]
    for case in matrix["cases"]:
        layout = case["layout"]
        lines.append(
            f"| {case['seed_index']} | {layout['budget_bytes']:,} | "
            f"{case['global_maximum_live_values']:,} | "
            f"{min(cut['optimistic_staged_bytes'] for cut in case['cuts']):,} | "
            f"{min(cut['naive_snapshot_delta_bytes'] for cut in case['cuts']):,} | "
            f"{'yes' if case['any_naive_snapshot_delta_fits'] else 'no'} | "
            f"{'yes' if case['any_optimistic_staged_fits'] else 'no'} |"
        )
    lines.extend([
        "", "## Selected checkpoint cuts", "",
        "| Seed | Cut | Snapshot values | Delta values | Frontier | Capture peak | Resume peak | Staged peak |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    selected = {0, 4, 8, 12, 16}
    for case in matrix["cases"]:
        for division, cut in enumerate(case["cuts"]):
            if division not in selected:
                continue
            lines.append(
                f"| {case['seed_index']} | {division}/16 | "
                f"{cut['snapshot_materialized_values']:,} | "
                f"{cut['suffix_distinct_write_values']:,} | "
                f"{cut['checkpoint_frontier_values']:,} | "
                f"{cut['capture_peak_live_values']:,} | "
                f"{cut['resume_peak_live_values']:,} | "
                f"{cut['staged_peak_live_values']:,} |"
            )
    lines.extend([
        "", "The optimistic staged model reuses one value store between capture and resume, "
        "grants exact future knowledge, and charges neither a cache nor a schedule. Its peak "
        "is nevertheless the workload's global live-value maximum at every cut.",
        "", "## Interpretation", "",
    ])
    lines.extend(f"- {item}" for item in method["interpretation"])
    lines.extend([
        "", "Where both models exceed the ceiling, this rejects these conventional one-checkpoint "
        "representations. It is not a universal impossibility proof: the next executable construction "
        "must recursively regenerate exact values while explicitly accounting for its cache, "
        "identity metadata, work stack, and transient values.",
    ])
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
