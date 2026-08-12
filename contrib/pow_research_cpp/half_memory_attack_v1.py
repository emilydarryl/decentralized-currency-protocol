# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Measure an exact-output PoW v1 static half-memory spill adversary."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile

try:
    from .benchmark_matrix_v1 import HEADER, cpu_model, seed_for
except ImportError:  # Direct script execution places this directory on sys.path.
    from benchmark_matrix_v1 import HEADER, cpu_model, seed_for


WARNING = (
    "NON-CONSENSUS ATTACK EXPERIMENT; external storage and unmeasured OS caching make "
    "this result ineligible to pass or reject the time-memory-tradeoff gate"
)
NORMAL_FORMAT = "soveroot-pow-research-cpp-benchmark-v1"
ATTACK_FORMAT = "soveroot-pow-research-cpp-half-spill-benchmark-v1"


@dataclass(frozen=True)
class Config:
    name: str
    dataset_bytes: int
    scratchpad_bytes: int
    passes: int


def profile(name: str) -> tuple[Config, int, int]:
    if name == "smoke":
        return Config("minimum", 64 * 1024, 8 * 1024, 1), 2, 1
    if name == "standard":
        return Config("baseline", 2 * 1024 * 1024, 256 * 1024, 3), 8, 3
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
    spill_directory: Path,
) -> dict[str, object]:
    arguments = [
        str(binary.resolve()),
        command,
        seed_for(seed_index).hex(),
        HEADER.hex(),
        str(seed_index << 32),
        str(attempts),
        str(config.dataset_bytes),
        str(config.scratchpad_bytes),
        str(config.passes),
    ]
    expected_format = NORMAL_FORMAT
    if command == "benchmark-half-spill":
        arguments.append(str(spill_directory.resolve()))
        expected_format = ATTACK_FORMAT
    elif command != "benchmark":
        raise ValueError(f"unsupported backend command: {command}")

    completed = subprocess.run(arguments, check=True, capture_output=True, text=True)
    result = json.loads(completed.stdout)
    if result.get("format") != expected_format:
        raise ValueError(f"unexpected {command} output format")
    if len(result.get("attempt_ns", {}).get("samples", [])) != attempts:
        raise ValueError(f"{command} returned the wrong attempt sample count")
    if not result.get("digest_sequence_commitment"):
        raise ValueError(f"{command} omitted its digest sequence commitment")
    return result


def run_case(
    binary: Path,
    config: Config,
    seed_index: int,
    attempts: int,
    spill_directory: Path,
) -> dict[str, object]:
    commands = ("benchmark", "benchmark-half-spill")
    if seed_index & 1:
        commands = tuple(reversed(commands))
    measured = {
        command: run_backend(
            binary,
            command,
            config,
            seed_index,
            attempts,
            spill_directory,
        )
        for command in commands
    }
    normal = measured["benchmark"]
    attack = measured["benchmark-half-spill"]
    exact_match = (
        normal["digest_sequence_commitment"] == attack["digest_sequence_commitment"]
        and normal["digest_xor_64"] == attack["digest_xor_64"]
    )
    normal_median = int(normal["attempt_ns"]["median"])
    attack_median = int(attack["attempt_ns"]["median"])
    return {
        "seed_index": seed_index,
        "normal": normal,
        "half_spill": attack,
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
    spill_directory: Path | None = None,
) -> dict[str, object]:
    config, default_seeds, default_attempts = profile(profile_name)
    seed_count = default_seeds if seeds is None else seeds
    attempt_count = default_attempts if attempts is None else attempts
    if not 1 <= seed_count <= 128:
        raise ValueError("seeds must be in [1, 128]")
    if not 1 <= attempt_count <= 100:
        raise ValueError("attempts must be in [1, 100] for the spill adversary")

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if spill_directory is None:
        temporary = tempfile.TemporaryDirectory(prefix="soveroot-pow-v1-half-spill-")
        active_spill_directory = Path(temporary.name)
    else:
        active_spill_directory = spill_directory
        if not active_spill_directory.is_dir():
            raise ValueError("spill directory does not exist")

    try:
        cases = [
            run_case(binary, config, seed_index, attempt_count, active_spill_directory)
            for seed_index in range(seed_count)
        ]
    finally:
        if temporary is not None:
            temporary.cleanup()

    if not all(bool(case["exact_output_match"]) for case in cases):
        raise RuntimeError("half-spill backend produced a different output sequence")

    normal_medians = [int(case["normal"]["attempt_ns"]["median"]) for case in cases]
    attack_medians = [int(case["half_spill"]["attempt_ns"]["median"]) for case in cases]
    throughput_fractions = [int(case["throughput_fraction_ppm"]) for case in cases]
    return {
        "format": "soveroot-pow-v1-half-memory-attack-matrix-v0",
        "warning": WARNING,
        "profile": profile_name,
        "source_revision": source_revision,
        "config": asdict(config),
        "seed_count": seed_count,
        "attempts_per_seed": attempt_count,
        "all_exact_outputs_match": True,
        "normal_median_attempt_ns_across_seeds": integer_summary(normal_medians),
        "half_spill_median_attempt_ns_across_seeds": integer_summary(attack_medians),
        "throughput_fraction_ppm_across_seeds": integer_summary(throughput_fractions),
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
            "retained_words": "even logical scratchpad word indexes",
            "spilled_words": "odd logical scratchpad word indexes",
            "logical_retained_fraction": "1/2",
            "external_storage": "temporary random-access file recreated for every attempt",
            "backend_order": "alternated by seed index",
            "output_check": "SHA3-384 digest-sequence commitment plus 64-bit digest xor",
            "os_page_cache": "unmeasured and uncontrolled",
            "physical_peak_memory": "unmeasured",
            "attacker_optimization": "correctness baseline; not optimized",
            "gate_eligibility": "informational only",
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--profile", choices=("smoke", "standard"), default="standard")
    parser.add_argument("--seeds", type=int)
    parser.add_argument("--attempts", type=int)
    parser.add_argument("--spill-directory", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-revision", default=os.environ.get("GITHUB_SHA", "unrecorded"))
    args = parser.parse_args()
    try:
        document = build_matrix(
            args.binary,
            args.profile,
            args.seeds,
            args.attempts,
            args.source_revision,
            args.spill_directory,
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
