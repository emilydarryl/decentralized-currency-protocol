# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Collect deterministic v1 versioned scratch-graph summaries."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from .benchmark_matrix_v1 import HEADER, cpu_model, seed_for
except ImportError:  # Direct script execution places this directory on sys.path.
    from benchmark_matrix_v1 import HEADER, cpu_model, seed_for

from contrib.pow_research_v1.powvm import Params, prepare_epoch
from contrib.pow_research_v1.versioned_graph import FORMAT, evaluate_versioned_graph


MATRIX_FORMAT = "soveroot-pow-v1-versioned-graph-matrix-v0"


def profile(name: str) -> tuple[Params, int]:
    if name == "smoke":
        return Params(dataset_bytes=64 * 1024, scratchpad_bytes=8 * 1024, passes=1), 2
    if name == "standard":
        return Params(dataset_bytes=2 * 1024 * 1024, scratchpad_bytes=256 * 1024, passes=3), 8
    raise ValueError(f"unsupported profile: {name}")


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
        context = prepare_epoch(seed_for(seed_index), params)
        result, graph = evaluate_versioned_graph(context, HEADER, seed_index << 32)
        cases.append({
            "seed_index": seed_index,
            "nonce": seed_index << 32,
            "digest": result.digest.hex(),
            "memory_commitment": result.memory_commitment.hex(),
            "graph": graph,
        })
    return {
        "format": MATRIX_FORMAT,
        "graph_format": FORMAT,
        "warning": "NON-CONSENSUS FULL-MEMORY OFFLINE GRAPH; no PoW gate is assessed",
        "profile": profile_name,
        "source_revision": source_revision,
        "params": params.to_dict(),
        "seed_count": seed_count,
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
