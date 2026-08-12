# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the informational PoW v1 no-spill recomputation report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _milliseconds(value: int) -> str:
    return f"{value / 1_000_000:.3f}"


def _percent(value: int) -> str:
    return f"{value / 10_000:.2f}%"


def render(matrix_path: Path, gates_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix.get("format") != "soveroot-pow-v1-recomputation-baseline-matrix-v0":
        raise ValueError("unsupported recomputation matrix format")
    if gates.get("format") != "soveroot-pow-evaluation-gates-v0":
        raise ValueError("unsupported gate format")
    if method.get("format") != "soveroot-pow-v1-recomputation-baseline-v0":
        raise ValueError("unsupported recomputation method format")
    if not matrix.get("all_exact_outputs_match"):
        raise ValueError("recomputation outputs do not match the normal backend")

    fraction = int(matrix["throughput_fraction_ppm_across_seeds"]["median"])
    config = matrix["config"]
    lines = [
        f"# Soveroot PoW v1 No-Spill Recomputation Baseline: {label}",
        "",
        "Status: **INFORMATIONAL EXACT-OUTPUT BASELINE — HALF-MEMORY GATE NOT ASSESSED**",
        "",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`",
        f"Source revision: `{matrix.get('source_revision', 'unrecorded')}`",
        f"Method: `{method['format']}` version `{method['version']}`",
        f"Profile: `{matrix['profile']}`",
        "",
        "## What was tested",
        "",
        f"The primary execution retained {config['scratchpad_bytes'] // 2048} KiB of its "
        f"{config['scratchpad_bytes'] // 1024} KiB scratchpad and used no external storage. "
        "Each read of a discarded odd-indexed word replayed the ordinary evaluator from iteration zero.",
        "",
        "Every paired attempt produced the same digest-sequence commitment and digest xor as the normal backend.",
        "",
        "## Aggregate result",
        "",
        f"- Normal attempt median: {_milliseconds(matrix['normal_median_attempt_ns_across_seeds']['median'])} ms",
        f"- Recomputation attempt median: {_milliseconds(matrix['recomputation_median_attempt_ns_across_seeds']['median'])} ms",
        f"- Retained throughput: {_percent(fraction)} of normal",
        f"- Replayed iterations per seed median: {matrix['replayed_iterations_across_seeds']['median']:,}",
        f"- Declared peak scratch allocation: {config['scratchpad_bytes'] * 3 // 2:,} bytes (150% of normal)",
        "",
        "## Per-seed evidence",
        "",
        "| Seed | Normal ms | Recompute ms | Retained throughput | Recomputed reads | Replayed iterations | Exact outputs |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for case in matrix["cases"]:
        normal = case["normal"]
        attack = case["half_retained_full_replay"]
        stats = attack["recomputation_stats"]
        lines.append(
            f"| {case['seed_index']} | {_milliseconds(normal['attempt_ns']['median'])} | "
            f"{_milliseconds(attack['attempt_ns']['median'])} | "
            f"{_percent(case['throughput_fraction_ppm'])} | {stats['recomputed_reads']} | "
            f"{stats['replayed_iterations']:,} | yes |"
        )

    lines += [
        "",
        "## Why this cannot decide the gate",
        "",
        "- The half-sized retained array stays live while each replay allocates a complete scratchpad, so peak scratch allocation is 150%, not 50%.",
        "- Resident memory, allocator overhead, metadata, stack use, power, and memory traffic were not measured.",
        "- Replaying from iteration zero is an auditable baseline, not an optimized checkpoint strategy.",
        "- Shared runners do not provide controlled thermal, power, or bandwidth conditions.",
        "",
        "The result establishes exact no-spill recomputation and its work counter only. A later attacker must replace the full replay workspace with explicitly budgeted checkpoints and keep measured total attack memory within the half-memory limit. The mandatory gate remains open.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--gates", required=True, type=Path)
    parser.add_argument("--method", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = render(args.matrix, args.gates, args.method, args.label)
    except ValueError as error:
        parser.error(str(error))
    args.output.write_text(report, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
