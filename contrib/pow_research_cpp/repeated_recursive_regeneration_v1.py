# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Collect repeated recursive-regeneration allocation evidence for PoW v1."""

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
from contrib.pow_research_v1.repeated_recursive_regeneration import (
    reconstruct_repeatedly_recursively,
)


FORMAT = "soveroot-pow-v1-repeated-recursive-regeneration-matrix-v0"
ALLOCATIONS = (128, 64, 32, 16, 8)


def build_matrix(
    profile_name: str,
    seeds: int | None = None,
    source_revision: str = "unrecorded",
) -> dict[str, object]:
    params, _ = profile(profile_name)
    seed_count = (1 if profile_name == "standard" else 2) if seeds is None else seeds
    if not 1 <= seed_count <= 4:
        raise ValueError("seeds must be in [1, 4]")
    cases: list[dict[str, object]] = []
    for seed_index in range(seed_count):
        context = prepare_epoch(seed_for(seed_index), params)
        allocations: list[dict[str, object]] = []
        for denominator in ALLOCATIONS:
            started = time.perf_counter_ns()
            result = reconstruct_repeatedly_recursively(
                context,
                HEADER,
                seed_index << 32,
                primary_denominator=denominator,
            ).to_dict()
            allocations.append({
                "allocation": f"1/{denominator}",
                "wall_ns": time.perf_counter_ns() - started,
                **result,
            })
        cases.append({
            "seed_index": seed_index,
            "nonce": seed_index << 32,
            "best_exact_prefix_allocation": max(
                allocations, key=lambda item: item["completed_iterations"]
            )["allocation"],
            "allocations": allocations,
        })
    all_allocations = [allocation for case in cases for allocation in case["allocations"]]
    return {
        "format": FORMAT,
        "warning": "NON-CONSENSUS REPEATED RECURSIVE REGENERATION SCREEN; no proof output, throughput result, or gate assessment",
        "profile": profile_name,
        "source_revision": source_revision,
        "params": params.to_dict(),
        "seed_count": seed_count,
        "allocations": [f"1/{item}" for item in ALLOCATIONS],
        "all_runs_reconstructed_repeatedly": all(
            allocation["reconstructed_misses"] > 1 for allocation in all_allocations
        ),
        "all_runs_exhausted_without_digest": all(
            allocation["status"] == "refused_recursive_regeneration_exhausted"
            and allocation["execution_result"] is None
            for allocation in all_allocations
        ),
        "memory_scope": {
            "admission": "one logical half-scratch arena partitioned before execution",
            "external_storage_bytes": 0,
            "offline_graph_or_schedule": "none",
            "logical_frames": "104 bytes per frame, with at most 20 reserved frames",
            "actual_stack_allocator_and_rss": "unmeasured",
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
