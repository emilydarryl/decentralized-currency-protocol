# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the v1 paged-gap reconstruction report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def render(matrix_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix["format"] != "soveroot-pow-v1-paged-gap-reconstruction-matrix-v0":
        raise ValueError("unsupported paged-gap matrix format")
    if method["format"] != "soveroot-pow-v1-paged-gap-reconstruction-method-v0":
        raise ValueError("unsupported paged-gap method format")
    lines = [
        f"# Soveroot PoW v1 Paged-Gap Reconstruction: {label}", "",
        "**NON-CONSENSUS PAGED-GAP PILOT - NO POW GATE ASSESSED**", "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`", "",
        "| Seed | Pages used | Values used | Recoveries | Exact prefix | Directory probes | Shifted bytes |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in matrix["cases"]:
        lines.append(
            f"| {case['seed_index']} | {case['max_replay_peak_pages']:,} "
            f"| {case['max_replay_peak_values']:,} | {case['reconstructed_misses']:,} "
            f"| {case['completed_iterations']:,} | {case['cumulative_directory_probes']:,} "
            f"| {case['cumulative_shifted_bytes']:,} |"
        )
    lines.extend([
        "", "Fixed-size pages bound insertion movement to a page suffix plus a small logical-directory suffix. Every terminal case refuses without a digest when another split needs a physical page and none remains.",
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
