# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the v1 repeated recursive-regeneration allocation report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def render(matrix_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix["format"] != "soveroot-pow-v1-repeated-recursive-regeneration-matrix-v0":
        raise ValueError("unsupported repeated recursive-regeneration matrix format")
    if method["format"] != "soveroot-pow-v1-repeated-recursive-regeneration-method-v0":
        raise ValueError("unsupported repeated recursive-regeneration method format")
    lines = [
        f"# Soveroot PoW v1 Repeated Recursive Regeneration: {label}", "",
        "**NON-CONSENSUS REPEATED REGENERATION SCREEN - NO POW GATE ASSESSED**", "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`", "",
        "| Seed | Primary allocation | Primary entries | Memo entries | Recoveries | Exact prefix | Replay work | Max depth | Memo evictions |",
        "| ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in matrix["cases"]:
        for allocation in case["allocations"]:
            lines.append(
                f"| {case['seed_index']} | {allocation['allocation']} | "
                f"{allocation['layout']['primary_cache_capacity']:,} | "
                f"{allocation['layout']['memo_capacity']:,} | "
                f"{allocation['reconstructed_misses']:,} | "
                f"{allocation['completed_iterations']:,} | "
                f"{allocation['regeneration_iterations']:,} | "
                f"{allocation['maximum_depth']:,} | "
                f"{allocation['memo_evictions']:,} |"
            )
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {item}" for item in method["interpretation"])
    lines.extend([
        "", "Every screened allocation preserves exact primary execution until its deterministic work boundary, then fails closed without a proof digest. The longest prefix is a screen result for this seed and work limit, not a generally optimal allocation.",
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
