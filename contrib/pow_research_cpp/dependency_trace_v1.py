# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Collect exact PoW v1 scratch-access summaries across deterministic seeds."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess

try:
    from .benchmark_matrix_v1 import HEADER, cpu_model, integer_summary, seed_for
except ImportError:  # Direct script execution places this directory on sys.path.
    from benchmark_matrix_v1 import HEADER, cpu_model, integer_summary, seed_for


FORMAT = "soveroot-pow-v1-dependency-trace-matrix-v0"
TRACE_FORMAT = "soveroot-pow-v1-access-trace-v0"


def profile(name: str) -> tuple[dict[str, int | str], int]:
    if name == "smoke":
        return {"name": "minimum", "dataset_bytes": 64 * 1024, "scratchpad_bytes": 8 * 1024, "passes": 1}, 2
    if name == "standard":
        return {"name": "baseline", "dataset_bytes": 2 * 1024 * 1024, "scratchpad_bytes": 256 * 1024, "passes": 3}, 8
    raise ValueError(f"unsupported profile: {name}")


def run_case(binary: Path, config: dict[str, int | str], seed_index: int) -> dict[str, object]:
    completed = subprocess.run(
        [
            str(binary.resolve()),
            "trace",
            seed_for(seed_index).hex(),
            HEADER.hex(),
            str(seed_index << 32),
            str(config["dataset_bytes"]),
            str(config["scratchpad_bytes"]),
            str(config["passes"]),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    if result.get("format") != TRACE_FORMAT:
        raise ValueError("unsupported C++ access-trace format")
    expected_iterations = int(config["scratchpad_bytes"]) // 8 * int(config["passes"])
    trace = result["trace"]
    if int(trace["reads"]) != expected_iterations * 2 + 16:
        raise ValueError("trace returned an unexpected read count")
    if int(trace["writes"]) != expected_iterations * 2:
        raise ValueError("trace returned an unexpected write count")
    result["seed_index"] = seed_index
    return result


def build_matrix(
    binary: Path,
    profile_name: str,
    seeds: int | None = None,
    source_revision: str = "unrecorded",
) -> dict[str, object]:
    config, default_seeds = profile(profile_name)
    seed_count = default_seeds if seeds is None else seeds
    if not 1 <= seed_count <= 128:
        raise ValueError("seeds must be in [1, 128]")
    cases = [run_case(binary, config, seed_index) for seed_index in range(seed_count)]

    def values(key: str) -> list[int]:
        return [int(case["trace"][key]) for case in cases]

    cache_summary: dict[str, object] = {}
    for cache_name in ("half_capacity_lru", "quarter_capacity_lru"):
        cache_summary[cache_name] = {
            metric: integer_summary([
                int(case["trace"]["cache_simulations"][cache_name][metric])
                for case in cases
            ])
            for metric in ("materialized_read_hits", "materialized_read_misses", "evictions")
        }

    return {
        "format": FORMAT,
        "warning": "NON-CONSENSUS FULL-MEMORY TRACE; cache simulations do not produce reduced-memory proofs",
        "profile": profile_name,
        "source_revision": source_revision,
        "config": config,
        "seed_count": seed_count,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_model": cpu_model(),
            "logical_cpus": os.cpu_count(),
            "runner_image": os.environ.get("ImageOS", "unrecorded"),
        },
        "summaries": {
            "initial_zero_reads": integer_summary(values("initial_zero_reads")),
            "materialized_reads": integer_summary(values("materialized_reads")),
            "distinct_read_words": integer_summary(values("distinct_read_words")),
            "distinct_written_words": integer_summary(values("distinct_written_words")),
            "maximum_live_values": integer_summary(values("maximum_live_values")),
            "cache_simulations": cache_summary,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--profile", choices=("smoke", "standard"), default="standard")
    parser.add_argument("--seeds", type=int)
    parser.add_argument("--source-revision", default=os.environ.get("GITHUB_SHA", "unrecorded"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        document = build_matrix(args.binary, args.profile, args.seeds, args.source_revision)
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
