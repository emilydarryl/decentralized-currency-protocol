# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the PoW v1 metadata-aware cache lower-bound report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _percent(ppm: int) -> str:
    return f"{ppm / 10_000:.2f}%"


def render(matrix_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix.get("format") != "soveroot-pow-v1-budgeted-cache-matrix-v0":
        raise ValueError("unsupported budgeted-cache matrix format")
    if method.get("format") != "soveroot-pow-v1-budgeted-cache-screen-v0":
        raise ValueError("unsupported budgeted-cache method format")
    config = matrix["config"]
    words = int(config["scratchpad_bytes"]) // 8
    lines = [
        f"# Soveroot PoW v1 Budgeted Cache Screen: {label}",
        "",
        "Status: **INFORMATIONAL LOWER BOUND — TIME-MEMORY GATE NOT ASSESSED**",
        "",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`",
        f"Source revision: `{matrix.get('source_revision', 'unrecorded')}`",
        f"Method: `{method['format']}` version `{method['version']}`",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}",
        "",
        "## Accounted half-memory layouts",
        "",
        f"The declared scratchpad contains {words:,} values ({int(config['scratchpad_bytes']):,} bytes). "
        f"Each simulated cache receives at most {int(config['scratchpad_bytes']) // 2:,} bytes including per-entry identity and replacement metadata.",
        "",
        "| Layout | Entry bytes | Cached values | Scratch words represented | LRU miss share | Offline-optimal miss share |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "compact_half_budget": "Compact",
        "conservative_half_budget": "Conservative",
    }
    for name, label_name in labels.items():
        summary = matrix["summaries"][name]
        capacity = int(summary["lru"]["capacity_words"]["median"])
        represented_ppm = capacity * 1_000_000 // words
        lines.append(
            f"| {label_name} | {summary['entry_bytes']} | {capacity:,} | "
            f"{_percent(represented_ppm)} | "
            f"{_percent(summary['lru']['miss_share_ppm']['median'])} | "
            f"{_percent(summary['offline_optimal']['miss_share_ppm']['median'])} |"
        )

    lines += [
        "",
        "The offline-optimal result is a lower bound for this completed trace: it knows every future access and refuses to retain values that will be overwritten before another read. A real online miner cannot know those value-dependent future addresses in advance.",
        "",
        "## Per-seed conservative layout",
        "",
        "| Seed | Materialized reads | LRU misses | LRU miss share | Oracle misses | Oracle miss share |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for case in matrix["cases"]:
        scenario = case["scenarios"]["conservative_half_budget"]
        lines.append(
            f"| {case['seed_index']} | {case['materialized_reads']:,} | "
            f"{scenario['lru']['materialized_read_misses']:,} | "
            f"{_percent(scenario['lru']['miss_share_ppm'])} | "
            f"{scenario['offline_optimal']['materialized_read_misses']:,} | "
            f"{_percent(scenario['offline_optimal']['miss_share_ppm'])} |"
        )

    lines += [
        "",
        "## Why this cannot decide the gate",
        "",
        "- Neither cache policy recomputes a missing value or produces an exact proof.",
        "- Offline-optimal replacement has future knowledge unavailable to an online miner.",
        "- An executable attacker must deduct control state, work queues, stack, checkpoints, and allocator overhead from the same budget.",
        "- A full scratch snapshot cannot fit inside the half-memory budget, while register-only checkpoints cannot resume the state machine.",
        "",
        "The oracle miss count is the most favorable cache-only lower bound under the stated entry representation. The next exact attack should be selected only after comparing its recomputation plan with that unavoidable missing-value workload. The mandatory time-memory gate remains open.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--method", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = render(args.matrix, args.method, args.label)
    except ValueError as error:
        parser.error(str(error))
    args.output.write_text(report, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
