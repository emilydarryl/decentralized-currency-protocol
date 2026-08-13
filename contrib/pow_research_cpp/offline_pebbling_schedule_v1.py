# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Collect deterministic graph-only replay schedules for PoW v1."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from .benchmark_matrix_v1 import HEADER, cpu_model, seed_for
    from .versioned_graph_v1 import profile
except ImportError:  # Direct script execution places this directory on sys.path.
    from benchmark_matrix_v1 import HEADER, cpu_model, seed_for
    from versioned_graph_v1 import profile

from contrib.pow_research_v1.offline_pebbling_schedule import search_offline_pebbling_schedule
from contrib.pow_research_v1.powvm import prepare_epoch
from contrib.pow_research_v1.versioned_graph import evaluate_captured_versioned_graph


FORMAT = "soveroot-pow-v1-offline-pebbling-schedule-matrix-v0"
LAYOUTS = {"compact": 16, "conservative": 24}


def build_matrix(
    profile_name: str,
    seeds: int | None = None,
    source_revision: str = "unrecorded",
) -> dict[str, object]:
    params, default_seeds = profile(profile_name)
    seed_count = default_seeds if seeds is None else seeds
    if not 1 <= seed_count <= 128:
        raise ValueError("seeds must be in [1, 128]")
    budget_bytes = params.scratchpad_bytes // 2
    cases: list[dict[str, object]] = []
    for seed_index in range(seed_count):
        started = time.perf_counter_ns()
        context = prepare_epoch(seed_for(seed_index), params)
        result, graph_summary, captured = evaluate_captured_versioned_graph(
            context,
            HEADER,
            seed_index << 32,
        )
        schedules: dict[str, dict[str, object]] = {}
        for name, entry_bytes in LAYOUTS.items():
            schedule = search_offline_pebbling_schedule(
                captured,
                budget_bytes=budget_bytes,
                value_entry_bytes=entry_bytes,
            ).to_dict()
            schedule["replay_work_fraction_ppm"] = (
                int(schedule["replayed_producers"]) * 1_000_000
                // int(graph_summary["mix_iterations"])
            )
            schedule["abstract_total_work_fraction_ppm"] = (
                (int(graph_summary["mix_iterations"]) + int(schedule["replayed_producers"]))
                * 1_000_000
                // int(graph_summary["mix_iterations"])
            )
            schedule["peak_retained_payload_bytes"] = int(schedule["peak_retained_values"]) * entry_bytes
            schedule["retained_plus_schedule_bytes"] = (
                int(schedule["peak_retained_payload_bytes"]) + int(schedule["schedule_bytes"])
            )
            schedule["retained_plus_schedule_over_budget_bytes"] = max(
                0,
                int(schedule["retained_plus_schedule_bytes"]) - budget_bytes,
            )
            schedules[name] = schedule
        cases.append({
            "seed_index": seed_index,
            "nonce": seed_index << 32,
            "digest": result.digest.hex(),
            "graph_commitment": graph_summary["graph_commitment"],
            "mix_iterations": graph_summary["mix_iterations"],
            "captured_events": len(captured.events),
            "captured_versions": len(captured.version_producers) - 1,
            "canonical_graph_bytes": graph_summary["canonical_encoding"]["encoded_bytes"],
            "planner_wall_ns": time.perf_counter_ns() - started,
            "schedules": schedules,
        })
    return {
        "format": FORMAT,
        "warning": "NON-CONSENSUS OPTIMISTIC OFFLINE GRAPH SCHEDULE; no executable attack, throughput, or PoW gate assessment",
        "profile": profile_name,
        "source_revision": source_revision,
        "params": params.to_dict(),
        "seed_count": seed_count,
        "budget": {
            "bytes": budget_bytes,
            "fraction_of_scratchpad": "1/2",
            "schedule_bytes_charged_to_value_capacity": 0,
            "layouts": {
                name: {"value_entry_bytes": entry_bytes, "capacity_values": budget_bytes // entry_bytes}
                for name, entry_bytes in LAYOUTS.items()
            },
        },
        "planner": {
            "replacement": "offline farthest-next-canonical-use",
            "miss_action": "recursive producer traversal in dependency postorder",
            "producer_output_policy": "retain requested output and sibling only when favored by next use",
            "schedule_encoding": "domain header followed by u8 frame tag, u32 requested version, u32 action count, and u32 producer ordinals",
        },
        "relaxations": [
            "the planner holds the complete full-memory graph and every future use",
            "historical VM registers, accumulator, address state, and dataset position are free",
            "a graph producer can execute whenever its two scratch inputs are available",
            "the entire half-scratch budget is available for retained value entries",
            "encoded schedule bytes are reported separately and not subtracted from value capacity",
            "Python planner memory and runtime are not attack measurements",
        ],
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_model": cpu_model(),
            "logical_cpus": os.cpu_count(),
            "runner_image": os.environ.get("ImageOS", "unrecorded"),
            "memory_note": "Python object RSS is planner memory, not an attack-memory measurement",
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "standard"), default="standard")
    parser.add_argument("--seeds", type=int)
    parser.add_argument("--source-revision", default=os.environ.get("GITHUB_SHA", "unrecorded"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        document = build_matrix(args.profile, args.seeds, args.source_revision)
    except ValueError as error:
        parser.error(str(error))
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
