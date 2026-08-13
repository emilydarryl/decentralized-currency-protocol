# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Collect one-miss bounded reconstruction evidence for PoW v1."""

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

from contrib.pow_research_v1.bounded_reconstruction import reconstruct_first_miss
from contrib.pow_research_v1.powvm import prepare_epoch


FORMAT = "soveroot-pow-v1-bounded-first-reconstruction-matrix-v0"


def build_matrix(
    profile_name: str,
    seeds: int | None = None,
    source_revision: str = "unrecorded",
) -> dict[str, object]:
    params, default_seeds = profile(profile_name)
    seed_count = default_seeds if seeds is None else seeds
    if not 1 <= seed_count <= 128:
        raise ValueError("seeds must be in [1, 128]")
    cases: list[dict[str, object]] = []
    for seed_index in range(seed_count):
        started = time.perf_counter_ns()
        result = reconstruct_first_miss(
            prepare_epoch(seed_for(seed_index), params),
            HEADER,
            seed_index << 32,
        ).to_dict()
        cases.append({
            "seed_index": seed_index,
            "nonce": seed_index << 32,
            "wall_ns": time.perf_counter_ns() - started,
            **result,
        })
    return {
        "format": FORMAT,
        "warning": "NON-CONSENSUS ONE-MISS RECONSTRUCTION; no completed proof, throughput, or PoW gate assessment",
        "profile": profile_name,
        "source_revision": source_revision,
        "params": params.to_dict(),
        "seed_count": seed_count,
        "all_runs_reconstructed_once": all(
            case["reconstructed_misses"] == 1
            and case["replay_state_matched"]
            for case in cases
        ),
        "all_runs_refused_without_digest": all(
            case["status"] == "refused_after_one_reconstruction"
            and case["execution_result"] is None
            for case in cases
        ),
        "memory_scope": {
            "admission": "one logical half-scratch arena partitioned before execution",
            "external_storage_bytes": 0,
            "offline_graph_or_schedule": "none",
            "actual_rss": "unmeasured",
            "stack_and_allocator": "logical fixed reserve only; not measured",
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
