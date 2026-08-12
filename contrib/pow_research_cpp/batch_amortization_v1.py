# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Measure PoW v1 sequential batch and shared-preparation amortization."""

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


FORMAT = "soveroot-pow-v1-batch-amortization-matrix-v0"
BENCHMARK_FORMAT = "soveroot-pow-research-cpp-benchmark-v1"


def profile(name: str) -> tuple[dict[str, int | str], list[int], int]:
    if name == "smoke":
        return (
            {"name": "minimum", "dataset_bytes": 64 * 1024, "scratchpad_bytes": 8 * 1024, "passes": 1},
            [1, 4, 16],
            2,
        )
    if name == "standard":
        return (
            {"name": "baseline", "dataset_bytes": 2 * 1024 * 1024, "scratchpad_bytes": 256 * 1024, "passes": 3},
            [1, 4, 16, 64, 256, 1024, 4096],
            8,
        )
    raise ValueError(f"unsupported profile: {name}")


def run_batch(
    binary: Path,
    config: dict[str, int | str],
    seed_index: int,
    batch_size: int,
) -> dict[str, object]:
    completed = subprocess.run(
        [
            str(binary.resolve()),
            "benchmark",
            seed_for(seed_index).hex(),
            HEADER.hex(),
            str(seed_index << 32),
            str(batch_size),
            str(config["dataset_bytes"]),
            str(config["scratchpad_bytes"]),
            str(config["passes"]),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    if result.get("format") != BENCHMARK_FORMAT:
        raise ValueError("unsupported C++ benchmark format")
    samples = [int(value) for value in result["attempt_ns"]["samples"]]
    if len(samples) != batch_size:
        raise ValueError("benchmark returned the wrong attempt sample count")
    result["inclusive_per_attempt_ns"] = (int(result["prepare_ns"]) + sum(samples)) // batch_size
    result["evaluation_per_attempt_ns"] = sum(samples) // batch_size
    return result


def run_seed(
    binary: Path,
    config: dict[str, int | str],
    batch_sizes: list[int],
    seed_index: int,
) -> dict[str, object]:
    rotation = seed_index % len(batch_sizes)
    ordered = batch_sizes[rotation:] + batch_sizes[:rotation]
    measured = {
        batch_size: run_batch(binary, config, seed_index, batch_size)
        for batch_size in ordered
    }
    single = measured[1]
    single_inclusive = int(single["inclusive_per_attempt_ns"])
    single_evaluation = int(single["evaluation_per_attempt_ns"])
    batches = []
    for batch_size in batch_sizes:
        result = measured[batch_size]
        inclusive = int(result["inclusive_per_attempt_ns"])
        evaluation = int(result["evaluation_per_attempt_ns"])
        batches.append({
            "batch_size": batch_size,
            "inclusive_advantage_ppm": single_inclusive * 1_000_000 // inclusive,
            "evaluation_only_advantage_ppm": single_evaluation * 1_000_000 // evaluation,
            "benchmark": result,
        })
    return {"seed_index": seed_index, "execution_order": ordered, "batches": batches}


def build_matrix(
    binary: Path,
    profile_name: str,
    seeds: int | None = None,
    source_revision: str = "unrecorded",
) -> dict[str, object]:
    config, batch_sizes, default_seeds = profile(profile_name)
    seed_count = default_seeds if seeds is None else seeds
    if not 1 <= seed_count <= 128:
        raise ValueError("seeds must be in [1, 128]")
    cases = [run_seed(binary, config, batch_sizes, seed_index) for seed_index in range(seed_count)]

    summaries = []
    for batch_index, batch_size in enumerate(batch_sizes):
        entries = [case["batches"][batch_index] for case in cases]
        summaries.append({
            "batch_size": batch_size,
            "inclusive_per_attempt_ns": integer_summary([
                int(entry["benchmark"]["inclusive_per_attempt_ns"]) for entry in entries
            ]),
            "evaluation_per_attempt_ns": integer_summary([
                int(entry["benchmark"]["evaluation_per_attempt_ns"]) for entry in entries
            ]),
            "inclusive_advantage_ppm": integer_summary([
                int(entry["inclusive_advantage_ppm"]) for entry in entries
            ]),
            "evaluation_only_advantage_ppm": integer_summary([
                int(entry["evaluation_only_advantage_ppm"]) for entry in entries
            ]),
        })

    return {
        "format": FORMAT,
        "warning": "NON-CONSENSUS SEQUENTIAL CPU SCREEN; hardware occupancy and parallel mining are unmeasured",
        "profile": profile_name,
        "source_revision": source_revision,
        "config": config,
        "seed_count": seed_count,
        "batch_sizes": batch_sizes,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_model": cpu_model(),
            "logical_cpus": os.cpu_count(),
            "runner_image": os.environ.get("ImageOS", "unrecorded"),
        },
        "method": {
            "inclusive_cost": "(epoch preparation plus sum of measured attempts) divided by batch size",
            "evaluation_cost": "sum of measured attempts divided by batch size",
            "comparison": "same-seed batch-size-one cost divided by named batch cost",
            "execution_order": "deterministic rotation by seed index",
            "parallelism": "none; attempts execute sequentially",
            "hardware_occupancy": "unmeasured",
            "gate_eligibility": "informational only",
        },
        "summaries": summaries,
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
