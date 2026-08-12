# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Measure the exact-output PoW v1 no-spill recomputation baseline."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess

try:
    from .benchmark_matrix_v1 import HEADER, cpu_model, seed_for
except ImportError:
    from benchmark_matrix_v1 import HEADER, cpu_model, seed_for


NORMAL_FORMAT = "soveroot-pow-research-cpp-benchmark-v1"
ATTACK_FORMAT = "soveroot-pow-research-cpp-half-recompute-benchmark-v1"
WARNING = (
    "NON-CONSENSUS RECOMPUTATION BASELINE; peak scratch allocation is 150% of "
    "the declared scratchpad, so this result cannot assess the half-memory gate"
)


@dataclass(frozen=True)
class Config:
    name: str
    dataset_bytes: int
    scratchpad_bytes: int
    passes: int


def profile(name: str) -> tuple[Config, int, int]:
    if name == "smoke":
        return Config("minimum", 64 * 1024, 8 * 1024, 1), 2, 1
    if name == "pilot":
        return Config("pilot", 256 * 1024, 32 * 1024, 1), 4, 1
    raise ValueError(f"unsupported profile: {name}")


def integer_summary(values: list[int]) -> dict[str, int]:
    if not values:
        raise ValueError("cannot summarize an empty sample")
    return {
        "min": min(values),
        "median": int(statistics.median(values)),
        "mean": int(statistics.fmean(values)),
        "max": max(values),
    }


def run_backend(
    binary: Path,
    command: str,
    config: Config,
    seed_index: int,
    attempts: int,
) -> dict[str, object]:
    completed = subprocess.run(
        [
            str(binary.resolve()),
            command,
            seed_for(seed_index).hex(),
            HEADER.hex(),
            str(seed_index << 32),
            str(attempts),
            str(config.dataset_bytes),
            str(config.scratchpad_bytes),
            str(config.passes),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    expected = NORMAL_FORMAT if command == "benchmark" else ATTACK_FORMAT
    if result.get("format") != expected:
        raise ValueError(f"unexpected {command} output format")
    if len(result.get("attempt_ns", {}).get("samples", [])) != attempts:
        raise ValueError(f"{command} returned the wrong attempt sample count")
    return result


def run_case(binary: Path, config: Config, seed_index: int, attempts: int) -> dict[str, object]:
    commands = ("benchmark", "benchmark-half-recompute")
    if seed_index & 1:
        commands = tuple(reversed(commands))
    measured = {
        command: run_backend(binary, command, config, seed_index, attempts)
        for command in commands
    }
    normal = measured["benchmark"]
    attack = measured["benchmark-half-recompute"]
    exact_match = (
        normal["digest_sequence_commitment"] == attack["digest_sequence_commitment"]
        and normal["digest_xor_64"] == attack["digest_xor_64"]
    )
    normal_median = int(normal["attempt_ns"]["median"])
    attack_median = int(attack["attempt_ns"]["median"])
    return {
        "seed_index": seed_index,
        "normal": normal,
        "half_retained_full_replay": attack,
        "exact_output_match": exact_match,
        "throughput_fraction_ppm": normal_median * 1_000_000 // attack_median,
        "slowdown_ppm": attack_median * 1_000_000 // normal_median,
    }


def build_matrix(
    binary: Path,
    profile_name: str,
    seeds: int | None = None,
    attempts: int | None = None,
    source_revision: str = "unrecorded",
) -> dict[str, object]:
    config, default_seeds, default_attempts = profile(profile_name)
    seed_count = default_seeds if seeds is None else seeds
    attempt_count = default_attempts if attempts is None else attempts
    if not 1 <= seed_count <= 16:
        raise ValueError("seeds must be in [1, 16] for the replay baseline")
    if not 1 <= attempt_count <= 4:
        raise ValueError("attempts must be in [1, 4] for the replay baseline")

    cases = [run_case(binary, config, index, attempt_count) for index in range(seed_count)]
    if not all(bool(case["exact_output_match"]) for case in cases):
        raise RuntimeError("recomputation backend produced a different output sequence")

    normal_medians = [int(case["normal"]["attempt_ns"]["median"]) for case in cases]
    attack_medians = [
        int(case["half_retained_full_replay"]["attempt_ns"]["median"])
        for case in cases
    ]
    throughput = [int(case["throughput_fraction_ppm"]) for case in cases]
    replayed = [
        int(case["half_retained_full_replay"]["recomputation_stats"]["replayed_iterations"])
        for case in cases
    ]
    return {
        "format": "soveroot-pow-v1-recomputation-baseline-matrix-v0",
        "warning": WARNING,
        "profile": profile_name,
        "source_revision": source_revision,
        "config": asdict(config),
        "seed_count": seed_count,
        "attempts_per_seed": attempt_count,
        "all_exact_outputs_match": True,
        "normal_median_attempt_ns_across_seeds": integer_summary(normal_medians),
        "recomputation_median_attempt_ns_across_seeds": integer_summary(attack_medians),
        "throughput_fraction_ppm_across_seeds": integer_summary(throughput),
        "replayed_iterations_across_seeds": integer_summary(replayed),
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_model": cpu_model(),
            "logical_cpus": os.cpu_count(),
            "python": platform.python_version(),
            "runner_image": os.environ.get("ImageOS", "unrecorded"),
        },
        "method": {
            "logical_retained_fraction": "1/2",
            "peak_scratch_fraction": "3/2",
            "external_storage": "none",
            "backend_order": "alternated by seed index",
            "gate_eligibility": "informational only",
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--profile", choices=("smoke", "pilot"), default="pilot")
    parser.add_argument("--seeds", type=int)
    parser.add_argument("--attempts", type=int)
    parser.add_argument("--source-revision", default=os.environ.get("GITHUB_SHA", "unrecorded"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        document = build_matrix(
            args.binary, args.profile, args.seeds, args.attempts, args.source_revision
        )
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
