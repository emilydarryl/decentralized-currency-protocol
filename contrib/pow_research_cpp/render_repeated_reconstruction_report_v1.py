# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the v1 repeated bounded reconstruction report."""

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
    if matrix["format"] != "soveroot-pow-v1-bounded-repeated-reconstruction-matrix-v0":
        raise ValueError("unsupported repeated reconstruction matrix format")
    if method["format"] != "soveroot-pow-v1-bounded-repeated-reconstruction-method-v0":
        raise ValueError("unsupported repeated reconstruction method format")
    cases = matrix["cases"]
    completed = [case["completed_iterations"] for case in cases]
    recovered = [case["reconstructed_misses"] for case in cases]
    replayed = [case["attempted_replay_iterations"] for case in cases]
    probes = [case["cumulative_replay_hash_probes"] for case in cases]
    lines = [
        f"# Soveroot PoW v1 Repeated Bounded Reconstruction: {label}",
        "",
        "**NON-CONSENSUS REPEATED RECONSTRUCTION - NO POW GATE ASSESSED**",
        "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`",
        "",
        "## Result",
        "",
        f"Every run reconstructed multiple values with matching machine state: `{str(matrix['all_runs_reconstructed_repeatedly']).lower()}`.  ",
        f"Every run exhausted the replay workspace without a digest: `{str(matrix['all_runs_exhausted_without_digest']).lower()}`.  ",
        f"Median successful reconstructions: {statistics.median(recovered):,.1f}.  ",
        f"Median exact prefix: {statistics.median(completed):,.1f} iterations.  ",
        f"Median attempted replay work: {statistics.median(replayed):,.1f} iterations.  ",
        f"Median cumulative replay hash probes: {statistics.median(probes):,.1f}.",
        "",
        "| Seed | Recoveries | Exact prefix | Attempted replay | Hash probes | Exhaustion replay prefix |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in cases:
        lines.append(
            f"| {case['seed_index']} | {case['reconstructed_misses']:,} "
            f"| {case['completed_iterations']:,} | {case['attempted_replay_iterations']:,} "
            f"| {case['cumulative_replay_hash_probes']:,} "
            f"| {case['exhaustion']['replay_completed_iterations']:,} / {case['exhaustion']['consumer']:,} |"
        )
    lines.extend([
        "",
        "Each successful recovery independently replays from genesis, matches the live registers and accumulator, commits the recovered value, and retries canonical execution. The terminal attempt fills the reserved sparse table and refuses without output.",
        "",
        "## Why the gate remains open",
        "",
    ])
    lines.extend(f"- {item}" for item in method["limitations"])
    lines.extend([
        "",
        "Repeated exact recovery materially extends the executable prefix, but the flat replay strategy cannot reach a proof. The mandatory time-memory gate remains open.",
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
