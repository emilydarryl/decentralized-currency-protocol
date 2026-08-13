# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the v1 packed-checkpoint reconstruction report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def render(matrix_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix["format"] != "soveroot-pow-v1-packed-checkpoint-reconstruction-matrix-v0":
        raise ValueError("unsupported packed checkpoint matrix format")
    if method["format"] != "soveroot-pow-v1-packed-checkpoint-reconstruction-method-v0":
        raise ValueError("unsupported packed checkpoint method format")
    lines = [
        f"# Soveroot PoW v1 Packed Checkpoint Reconstruction: {label}", "",
        "**NON-CONSENSUS PACKED CHECKPOINT PILOT - NO POW GATE ASSESSED**", "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`", "",
        "| Seed | Packed capacity | Recoveries | Exact prefix | Attempted replay | Shifted bytes |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in matrix["cases"]:
        lines.append(
            f"| {case['seed_index']} | {case['layout']['replay_value_capacity']:,} "
            f"| {case['reconstructed_misses']:,} | {case['completed_iterations']:,} "
            f"| {case['attempted_replay_iterations']:,} | {case['cumulative_shifted_bytes']:,} |"
        )
    lines.extend([
        "", "The bitmap-ranked layout removes per-value 64-bit tags and spends those bytes on exact values. It charges rank work and every byte shifted by sorted insertion. Every terminal case refuses without a digest when the packed value area is full.",
        "", "## Why the gate remains open", "",
    ])
    lines.extend(f"- {item}" for item in method["limitations"])
    lines.extend(["", "This is capacity and boundary evidence, not a completed reduced-memory proof or controlled benchmark."])
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
