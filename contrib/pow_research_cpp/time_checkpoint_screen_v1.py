# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Collect offline time-checkpoint feasibility evidence for PoW v1."""

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
except ImportError:
    from benchmark_matrix_v1 import HEADER, cpu_model, seed_for
    from versioned_graph_v1 import profile

from contrib.pow_research_v1.powvm import prepare_epoch
from contrib.pow_research_v1.time_checkpoint_screen import screen_time_checkpoints


FORMAT = "soveroot-pow-v1-time-checkpoint-screen-matrix-v0"


def build_matrix(
    profile_name: str,
    seeds: int | None = None,
    source_revision: str = "unrecorded",
) -> dict[str, object]:
    params, _ = profile(profile_name)
    seed_count = (2 if profile_name == "smoke" else 1) if seeds is None else seeds
    if not 1 <= seed_count <= 8:
        raise ValueError("seeds must be in [1, 8]")
    cases: list[dict[str, object]] = []
    for seed_index in range(seed_count):
        started = time.perf_counter_ns()
        result = screen_time_checkpoints(
            prepare_epoch(seed_for(seed_index), params), HEADER, seed_index << 32
        ).to_dict()
        cases.append({
            "seed_index": seed_index,
            "nonce": seed_index << 32,
            "wall_ns": time.perf_counter_ns() - started,
            **result,
        })
    return {
        "format": FORMAT,
        "warning": "NON-CONSENSUS FULL-MEMORY OFFLINE CHECKPOINT SCREEN; no attack or gate result",
        "profile": profile_name,
        "source_revision": source_revision,
        "params": params.to_dict(),
        "seed_count": seed_count,
        "all_naive_snapshot_delta_cuts_fail": all(
            not case["any_naive_snapshot_delta_fits"] for case in cases
        ),
        "all_optimistic_staged_cuts_fail": all(
            not case["any_optimistic_staged_fits"] for case in cases
        ),
        "all_staged_peaks_equal_global_maximum": all(
            all(cut["staged_peak_live_values"] == case["global_maximum_live_values"]
                for cut in case["cuts"])
            for case in cases
        ),
        "memory_scope": {
            "trace": "full ordinary scratchpad plus unbounded offline event trace",
            "future_knowledge": "exact future materialized reads and writes",
            "optimistic_store": "one reusable bitmap-ranked value store plus fixed reserve",
            "omitted": "canonical cache, schedule, allocator overhead, and physical-memory effects",
            "actual_rss": "unmeasured",
        },
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_model": cpu_model(),
            "logical_cpus": os.cpu_count(),
            "runner_image": os.environ.get("ImageOS", "unrecorded"),
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
