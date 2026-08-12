# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Collect metadata-aware LRU and offline-optimal PoW v1 cache screens."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess

try:
    from .benchmark_matrix_v1 import HEADER, cpu_model, integer_summary, seed_for
except ImportError:
    from benchmark_matrix_v1 import HEADER, cpu_model, integer_summary, seed_for


FORMAT = "soveroot-pow-v1-budgeted-cache-matrix-v0"
TRACE_FORMAT = "soveroot-pow-v1-access-trace-v0"
SCENARIOS = ("compact_half_budget", "conservative_half_budget")
POLICIES = ("lru", "offline_optimal")


def profile(name: str) -> tuple[dict[str, int | str], int]:
    if name == "smoke":
        return {"name": "minimum", "dataset_bytes": 64 * 1024, "scratchpad_bytes": 8 * 1024, "passes": 1}, 2
    if name == "standard":
        return {"name": "baseline", "dataset_bytes": 2 * 1024 * 1024, "scratchpad_bytes": 256 * 1024, "passes": 3}, 8
    raise ValueError(f"unsupported profile: {name}")


def run_case(binary: Path, config: dict[str, int | str], seed_index: int) -> dict[str, object]:
    completed = subprocess.run(
        [
            str(binary.resolve()), "trace", seed_for(seed_index).hex(), HEADER.hex(),
            str(seed_index << 32), str(config["dataset_bytes"]),
            str(config["scratchpad_bytes"]), str(config["passes"]),
        ],
        check=True, capture_output=True, text=True,
    )
    trace_document = json.loads(completed.stdout)
    if trace_document.get("format") != TRACE_FORMAT:
        raise ValueError("unsupported C++ access-trace format")
    simulations = trace_document["trace"]["cache_simulations"]
    scenarios: dict[str, object] = {}
    for scenario_name in SCENARIOS:
        raw = simulations[scenario_name]
        policies: dict[str, object] = {}
        for policy_name in POLICIES:
            policy = dict(raw[policy_name])
            total = int(policy["materialized_read_hits"]) + int(policy["materialized_read_misses"])
            policy["miss_share_ppm"] = int(policy["materialized_read_misses"]) * 1_000_000 // total
            policies[policy_name] = policy
        scenarios[scenario_name] = {
            "budget_bytes": raw["budget_bytes"],
            "entry_bytes": raw["entry_bytes"],
            **policies,
        }
    return {
        "seed_index": seed_index,
        "digest": trace_document["digest"],
        "trace_commitment": trace_document["trace"]["trace_commitment"],
        "materialized_reads": trace_document["trace"]["materialized_reads"],
        "scenarios": scenarios,
    }


def build_matrix(binary: Path, profile_name: str, seeds: int | None = None, source_revision: str = "unrecorded") -> dict[str, object]:
    config, default_seeds = profile(profile_name)
    seed_count = default_seeds if seeds is None else seeds
    if not 1 <= seed_count <= 128:
        raise ValueError("seeds must be in [1, 128]")
    cases = [run_case(binary, config, index) for index in range(seed_count)]
    summaries: dict[str, object] = {}
    for scenario_name in SCENARIOS:
        first = cases[0]["scenarios"][scenario_name]
        scenario_summary: dict[str, object] = {
            "budget_bytes": first["budget_bytes"],
            "entry_bytes": first["entry_bytes"],
        }
        for policy_name in POLICIES:
            scenario_summary[policy_name] = {
                metric: integer_summary([
                    int(case["scenarios"][scenario_name][policy_name][metric])
                    for case in cases
                ])
                for metric in (
                    "capacity_words", "materialized_read_hits",
                    "materialized_read_misses", "evictions", "miss_share_ppm",
                )
            }
        summaries[scenario_name] = scenario_summary
    return {
        "format": FORMAT,
        "warning": "NON-CONSENSUS CACHE LOWER BOUND; misses do not produce valid reduced-memory proofs",
        "profile": profile_name,
        "source_revision": source_revision,
        "config": config,
        "seed_count": seed_count,
        "host": {
            "platform": platform.platform(), "machine": platform.machine(),
            "cpu_model": cpu_model(), "logical_cpus": os.cpu_count(),
            "runner_image": os.environ.get("ImageOS", "unrecorded"),
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
