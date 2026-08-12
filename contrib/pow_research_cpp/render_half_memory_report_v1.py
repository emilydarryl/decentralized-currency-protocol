# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render an informational report for the PoW v1 half-memory spill adversary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _milliseconds(nanoseconds: int) -> str:
    return f"{nanoseconds / 1_000_000:.3f}"


def _percent(ppm: int) -> str:
    return f"{ppm / 10_000:.2f}%"


def render(matrix_path: Path, gates_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix.get("format") != "soveroot-pow-v1-half-memory-attack-matrix-v0":
        raise ValueError("unsupported half-memory matrix format")
    if gates.get("format") != "soveroot-pow-evaluation-gates-v0":
        raise ValueError("unsupported gate format")
    if method.get("format") != "soveroot-pow-v1-half-memory-attack-v0":
        raise ValueError("unsupported half-memory method format")
    if not matrix.get("all_exact_outputs_match"):
        raise ValueError("half-memory attack outputs do not match the normal backend")

    gate = next(gate for gate in gates["gates"] if gate["id"] == "time_memory_tradeoff")
    fraction_ppm = int(matrix["throughput_fraction_ppm_across_seeds"]["median"])
    pass_ceiling = int(float(gate["pass"]["throughput_fraction_at_half_memory_max"]) * 1_000_000)
    reject_above = int(float(gate["reject"]["throughput_fraction_at_half_memory_above"]) * 1_000_000)
    if fraction_ppm <= pass_ceiling:
        numerical_zone = "at or below the policy pass ceiling"
    elif fraction_ppm > reject_above:
        numerical_zone = "above the policy rejection boundary"
    else:
        numerical_zone = "between the policy pass and rejection boundaries"

    config = matrix["config"]
    lines = [
        f"# Soveroot PoW v1 Half-Memory Spill Attack: {label}",
        "",
        "Status: **INFORMATIONAL EXACT-OUTPUT ATTACK — TIME-MEMORY GATE NOT ASSESSED**",
        "",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`",
        f"Source revision: `{matrix.get('source_revision', 'unrecorded')}`",
        f"Attack method: `{method['format']}` version `{method['version']}`",
        f"Profile: `{matrix['profile']}`",
        "",
        "## What was tested",
        "",
        f"The attacker retained exactly {config['scratchpad_bytes'] // 2048} KiB of the "
        f"declared {config['scratchpad_bytes'] // 1024} KiB scratchpad in its explicit byte array. "
        "Even-indexed words stayed in process; odd-indexed words were read from and written to a temporary random-access file.",
        "",
        "Every paired attempt produced the same digest-sequence commitment and digest xor as the normal backend.",
        "",
        "## Aggregate result",
        "",
        f"- Normal attempt median: {_milliseconds(matrix['normal_median_attempt_ns_across_seeds']['median'])} ms",
        f"- Half-spill attempt median: {_milliseconds(matrix['half_spill_median_attempt_ns_across_seeds']['median'])} ms",
        f"- Retained throughput: {_percent(fraction_ppm)} of normal",
        f"- Numerical location only: {numerical_zone} ({_percent(pass_ceiling)} pass ceiling; more than {_percent(reject_above)} rejects)",
        "",
        "That numerical comparison is context, not a gate outcome.",
        "",
        "## Per-seed evidence",
        "",
        "| Seed | Normal median ms | Half-spill median ms | Retained throughput | Exact outputs | Spill reads | Spill writes |",
        "|---:|---:|---:|---:|---|---:|---:|",
    ]
    for case in matrix["cases"]:
        normal = case["normal"]
        attack = case["half_spill"]
        spill = attack["spill_stats"]
        lines.append(
            f"| {case['seed_index']} | {_milliseconds(normal['attempt_ns']['median'])} | "
            f"{_milliseconds(attack['attempt_ns']['median'])} | "
            f"{_percent(case['throughput_fraction_ppm'])} | yes | "
            f"{spill['spill_reads']} | {spill['spill_writes']} |"
        )

    lines += [
        "",
        "## Why this cannot decide the gate",
        "",
        "- The operating system's page cache was neither measured nor bounded, so logical retained bytes are not physical peak memory.",
        "- The omitted half was stored externally; this implementation does not measure the required recomputation strategy.",
        "- Per-word file seeks are a transparent correctness baseline, not a strongest-known optimized attacker.",
        "- Shared runners do not provide controlled storage, thermal, power, or memory-bandwidth conditions.",
        "",
        "A decisive experiment needs a reviewed recomputation or bounded-memory attack, measured resident memory, controlled physical hosts, and the strongest optimized implementation available. Until then, the mandatory time-memory-tradeoff gate remains open.",
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
