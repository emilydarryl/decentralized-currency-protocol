# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the PoW v1 dependency-trace and batch-amortization screen."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _ratio(ppm: int) -> str:
    return f"{ppm / 1_000_000:.2f}x"


def _percent(part: int, whole: int) -> str:
    return f"{part * 100 / whole:.2f}%"


def _milliseconds(nanoseconds: int) -> str:
    return f"{nanoseconds / 1_000_000:.3f}"


def render(trace_path: Path, batch_path: Path, gates_path: Path, method_path: Path, label: str) -> str:
    trace_raw = trace_path.read_bytes()
    batch_raw = batch_path.read_bytes()
    trace = json.loads(trace_raw)
    batch = json.loads(batch_raw)
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if trace.get("format") != "soveroot-pow-v1-dependency-trace-matrix-v0":
        raise ValueError("unsupported dependency-trace format")
    if batch.get("format") != "soveroot-pow-v1-batch-amortization-matrix-v0":
        raise ValueError("unsupported batch-amortization format")
    if gates.get("format") != "soveroot-pow-evaluation-gates-v0":
        raise ValueError("unsupported gate format")
    if method.get("format") != "soveroot-pow-v1-dependency-batch-screen-v0":
        raise ValueError("unsupported diagnostic method format")
    if trace["source_revision"] != batch["source_revision"]:
        raise ValueError("trace and batch matrices use different source revisions")

    word_count = int(trace["config"]["scratchpad_bytes"]) // 8
    summaries = trace["summaries"]
    materialized = int(summaries["materialized_reads"]["median"])
    initial_zero = int(summaries["initial_zero_reads"]["median"])
    live = int(summaries["maximum_live_values"]["median"])
    cache = summaries["cache_simulations"]
    half_hits = int(cache["half_capacity_lru"]["materialized_read_hits"]["median"])
    half_misses = int(cache["half_capacity_lru"]["materialized_read_misses"]["median"])
    quarter_hits = int(cache["quarter_capacity_lru"]["materialized_read_hits"]["median"])
    quarter_misses = int(cache["quarter_capacity_lru"]["materialized_read_misses"]["median"])

    largest = batch["summaries"][-1]
    batch_size = int(largest["batch_size"])
    inclusive_advantage = int(largest["inclusive_advantage_ppm"]["median"])
    evaluation_advantage = int(largest["evaluation_only_advantage_ppm"]["median"])
    gate = next(gate for gate in gates["gates"] if gate["id"] == "facility_amortization")
    pass_ppm = int(float(gate["pass"]["per_attempt_advantage_after_occupancy_max"]) * 1_000_000)
    reject_ppm = int(float(gate["reject"]["per_attempt_advantage_after_occupancy_above"]) * 1_000_000)
    if inclusive_advantage <= pass_ppm:
        numerical_zone = "at or below the policy pass ceiling"
    elif inclusive_advantage > reject_ppm:
        numerical_zone = "above the policy rejection boundary"
    else:
        numerical_zone = "between the policy pass and rejection boundaries"

    lines = [
        f"# Soveroot PoW v1 Dependency and Batch Screen: {label}",
        "",
        "Status: **INFORMATIONAL DIAGNOSTICS — NO POW GATE PASSED**",
        "",
        f"Trace matrix SHA3-384: `{hashlib.sha3_384(trace_raw).hexdigest()}`",
        f"Batch matrix SHA3-384: `{hashlib.sha3_384(batch_raw).hexdigest()}`",
        f"Source revision: `{trace['source_revision']}`",
        f"Method: `{method['format']}` version `{method['version']}`",
        "",
        "## Dependency trace",
        "",
        f"Across {trace['seed_count']} seeds, the median trace had {initial_zero:,} reads of untouched zero values and {materialized:,} reads of values written earlier in the attempt.",
        "",
        f"The offline maximum live-value count was {live:,} words ({_percent(live, word_count)} of the scratchpad). This uses the completed trace and therefore is not an online attack strategy.",
        "",
        "| Simulated value cache | Materialized read hits | Materialized read misses | Miss share |",
        "|---|---:|---:|---:|",
        f"| Half capacity | {half_hits:,} | {half_misses:,} | {_percent(half_misses, half_hits + half_misses)} |",
        f"| Quarter capacity | {quarter_hits:,} | {quarter_misses:,} | {_percent(quarter_misses, quarter_hits + quarter_misses)} |",
        "",
        "These LRU simulations use a full-memory execution trace. A miss identifies a value that an online bounded-memory implementation must retain, compress, or recompute; the simulator itself does none of those and does not produce a proof.",
        "",
        "## Sequential batch amortization",
        "",
        "| Batch | Inclusive per attempt ms | Evaluation per attempt ms | Inclusive advantage | Evaluation-only advantage |",
        "|---:|---:|---:|---:|---:|",
    ]
    for summary in batch["summaries"]:
        lines.append(
            f"| {summary['batch_size']} | "
            f"{_milliseconds(summary['inclusive_per_attempt_ns']['median'])} | "
            f"{_milliseconds(summary['evaluation_per_attempt_ns']['median'])} | "
            f"{_ratio(summary['inclusive_advantage_ppm']['median'])} | "
            f"{_ratio(summary['evaluation_only_advantage_ppm']['median'])} |"
        )

    lines += [
        "",
        f"At batch {batch_size:,}, the inclusive advantage was {_ratio(inclusive_advantage)} and the evaluation-only advantage was {_ratio(evaluation_advantage)}. The inclusive value lies {numerical_zone} ({_ratio(pass_ppm)} pass ceiling; more than {_ratio(reject_ppm)} rejects).",
        "",
        "That comparison is numerical context only. The shared runner did not measure hardware occupancy, parallel miners, energy, temperature, or memory traffic, so the facility-amortization gate remains open.",
        "",
        "## Consequence for the recomputation attack",
        "",
        "The next implementation must reproduce exact outputs without external storage while accounting for all retained values, checkpoints, metadata, and stack state. The trace narrows that design problem but cannot substitute for it. A large miss share or live set is encouraging only until a reviewed online attack demonstrates the actual throughput tradeoff.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--gates", required=True, type=Path)
    parser.add_argument("--method", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = render(args.trace, args.batch, args.gates, args.method, args.label)
    except ValueError as error:
        parser.error(str(error))
    args.output.write_text(report, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
