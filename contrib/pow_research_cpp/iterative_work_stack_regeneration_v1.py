# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Collect the predeclared iterative work-stack holdout for PoW v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from .benchmark_matrix_v1 import HEADER, seed_for
    from .versioned_graph_v1 import profile
except ImportError:
    from benchmark_matrix_v1 import HEADER, seed_for
    from versioned_graph_v1 import profile

from contrib.pow_research_v1.checkpoint_recursive_regeneration import (
    reconstruct_repeatedly_with_iterative_work_stack,
)
from contrib.pow_research_v1.powvm import prepare_epoch


FORMAT = "soveroot-pow-v1-iterative-work-stack-regeneration-holdout-v0"


def build_holdout(
    profile_name: str = "standard",
    seeds: int = 8,
    operation_limit: int = 5_000_000,
) -> dict[str, object]:
    if not 1 <= seeds <= 8:
        raise ValueError("seeds must be in [1, 8]")
    if operation_limit <= 0:
        raise ValueError("operation limit must be positive")
    params, _ = profile(profile_name)
    cases: list[dict[str, object]] = []
    for seed_index in range(seeds):
        started = time.perf_counter_ns()
        result = reconstruct_repeatedly_with_iterative_work_stack(
            prepare_epoch(seed_for(seed_index), params),
            HEADER,
            0,
            operation_limit=operation_limit,
        ).to_dict()
        cases.append({
            "seed_index": seed_index,
            "wall_ns": time.perf_counter_ns() - started,
            **result,
        })
    prefixes = sorted(int(case["completed_iterations"]) for case in cases)
    middle = len(prefixes) // 2
    median = (
        prefixes[middle]
        if len(prefixes) % 2
        else (prefixes[middle - 1] + prefixes[middle]) / 2
    )
    return {
        "format": FORMAT,
        "warning": "NON-CONSENSUS ITERATIVE WORK-STACK HOLDOUT; no gate assessment",
        "profile": profile_name,
        "nonce": 0,
        "seed_count": seeds,
        "operation_limit": operation_limit,
        "minimum_completed_iterations": prefixes[0],
        "median_completed_iterations": median,
        "maximum_completed_iterations": prefixes[-1],
        "completed_proofs": sum(case["execution_result"] is not None for case in cases),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "standard"), default="standard")
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--operation-limit", type=int, default=5_000_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        document = build_holdout(args.profile, args.seeds, args.operation_limit)
    except ValueError as error:
        parser.error(str(error))
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
