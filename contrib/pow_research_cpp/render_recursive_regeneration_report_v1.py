# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the v1 first recursive value-regeneration report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def render(matrix_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix["format"] != "soveroot-pow-v1-recursive-regeneration-matrix-v0":
        raise ValueError("unsupported recursive-regeneration matrix format")
    if method["format"] != "soveroot-pow-v1-recursive-regeneration-method-v0":
        raise ValueError("unsupported recursive-regeneration method format")
    lines = [
        f"# Soveroot PoW v1 Recursive Value Regeneration: {label}", "",
        "**NON-CONSENSUS FIRST REGENERATION PILOT - NO POW GATE ASSESSED**", "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`", "",
        "| Seed | Primary entries | Memo entries | First miss | Replay iterations | Max depth | Exact prefix | Terminal status |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
    ]
    for case in matrix["cases"]:
        first = case["first_reconstruction"]
        first_miss = "none" if first is None else f"{first['consumer']}:{first['slot']}:{first['word']}"
        lines.append(
            f"| {case['seed_index']} | {case['layout']['primary_cache_capacity']:,} | "
            f"{case['layout']['memo_capacity']:,} | {first_miss} | "
            f"{case['regeneration_iterations']:,} | {case['maximum_depth']:,} | "
            f"{case['completed_iterations']:,} | `{case['status']}` |"
        )
    lines.extend([
        "", "The first-miss coordinate is `consumer:read-slot:word`. The value at that boundary is checked against an ordinary full-memory execution and independently committed by Python and C++ vectors.",
        "", "## Interpretation", "",
    ])
    lines.extend(f"- {item}" for item in method["interpretation"])
    lines.extend([
        "", "This demonstrates the core recursive exact-value operation without an offline trace or spill store. It deliberately stops at the next primary miss, emits no proof digest, and does not yet measure physical process memory or meaningful throughput.",
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
