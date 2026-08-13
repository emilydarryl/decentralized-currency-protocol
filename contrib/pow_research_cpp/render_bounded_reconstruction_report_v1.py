# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the v1 one-miss bounded reconstruction report."""

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
    if matrix["format"] != "soveroot-pow-v1-bounded-first-reconstruction-matrix-v0":
        raise ValueError("unsupported reconstruction matrix format")
    if method["format"] != "soveroot-pow-v1-bounded-first-reconstruction-method-v0":
        raise ValueError("unsupported reconstruction method format")
    completed = [case["completed_iterations"] for case in matrix["cases"]]
    replayed = [case["replayed_iterations"] for case in matrix["cases"]]
    peak = [case["replay_peak_entries"] for case in matrix["cases"]]
    lines = [
        f"# Soveroot PoW v1 Bounded First Reconstruction: {label}",
        "",
        "**NON-CONSENSUS ONE-MISS RECONSTRUCTION - NO POW GATE ASSESSED**",
        "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`",
        "",
        "## Result",
        "",
        f"Every run reconstructed one value with matching machine state: `{str(matrix['all_runs_reconstructed_once']).lower()}`.  ",
        f"Every run later refused without a digest: `{str(matrix['all_runs_refused_without_digest']).lower()}`.  ",
        f"Median reconstruction replay: {statistics.median(replayed):,.1f} iterations.  ",
        f"Median exact prefix after recovery: {statistics.median(completed):,.1f} iterations.  ",
        f"Median replay-table high water: {statistics.median(peak):,.1f} entries.",
        "",
        "| Seed | Reconstructed read | Replay work / peak | Exact prefix after recovery | Next refused read |",
        "| ---: | --- | ---: | ---: | --- |",
    ]
    for case in matrix["cases"]:
        lines.append(
            f"| {case['seed_index']} "
            f"| iteration {case['reconstruction_consumer']}, slot {case['reconstruction_slot']}, word {case['reconstruction_word']} "
            f"| {case['replayed_iterations']:,} / {case['replay_peak_entries']:,} "
            f"| {case['completed_iterations']:,} "
            f"| iteration {case['refusal_consumer']}, slot {case['refusal_slot']}, word {case['refusal_word']} |"
        )
    lines.extend([
        "",
        "The sparse replay starts from the canonical initial state, retains every distinct word written in the replay prefix, and refuses if its preallocated table fills. The recovered value is accepted only after replayed registers and accumulator match the live pre-read state.",
        "",
        "## Why the gate remains open",
        "",
    ])
    lines.extend(f"- {item}" for item in method["limitations"])
    lines.extend([
        "",
        "This demonstrates one exact online reconstruction without a graph, trace, schedule, spill, or second allocation. It still emits no completed proof and supplies no throughput or measured-memory result. The mandatory time-memory gate remains open.",
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
