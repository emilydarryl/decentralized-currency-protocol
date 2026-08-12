# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Run a reproducible multi-seed C++ PoW v1 research benchmark matrix."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess


WARNING = (
    "NON-CONSENSUS V1 CANDIDATE; these measurements do not establish memory hardness, "
    "specialization resistance, decentralization, energy efficiency, or production readiness"
)
HEADER = b"Soveroot reproducible C++ benchmark matrix v1"
PHASES = ("input_setup", "scratchpad_init", "mix_execute", "finalize")


@dataclass(frozen=True)
class Config:
    name: str
    dataset_bytes: int
    scratchpad_bytes: int
    passes: int


def profile(name: str) -> tuple[list[Config], int, int]:
    baseline = Config("baseline", 2 * 1024 * 1024, 256 * 1024, 3)
    if name == "smoke":
        return [Config("minimum", 64 * 1024, 8 * 1024, 1), baseline], 2, 2
    if name == "standard":
        configs = [baseline]
        configs += [
            Config(f"dataset-{kib}k", kib * 1024, baseline.scratchpad_bytes, baseline.passes)
            for kib in (64, 1024, 4096)
        ]
        configs += [
            Config(f"scratch-{kib}k", baseline.dataset_bytes, kib * 1024, baseline.passes)
            for kib in (8, 128, 512)
        ]
        configs += [
            Config(f"passes-{count}", baseline.dataset_bytes, baseline.scratchpad_bytes, count)
            for count in (1, 16)
        ]
        return configs, 8, 20
    raise ValueError(f"unsupported profile: {name}")


def seed_for(index: int) -> bytes:
    if not 0 <= index <= 0xFFFFFFFF:
        raise ValueError("seed index must fit uint32")
    return hashlib.sha3_384(
        b"Soveroot/PowResearch/BenchmarkSeed/v1\x00" + index.to_bytes(4, "little")
    ).digest()


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.partition(":")[2].strip()
    except OSError:
        pass
    return platform.processor() or "unavailable"


def run_case(binary: Path, config: Config, seed_index: int, attempts: int) -> dict[str, object]:
    completed = subprocess.run(
        [
            str(binary.resolve()),
            "benchmark",
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
    if result.get("format") != "soveroot-pow-research-cpp-benchmark-v1":
        raise ValueError("unsupported C++ v1 benchmark format")
    if set(result.get("phase_ns", {})) != set(PHASES):
        raise ValueError("C++ v1 benchmark did not provide the required phase timings")
    for phase in PHASES:
        if len(result["phase_ns"][phase]["samples"]) != attempts:
            raise ValueError(f"C++ v1 benchmark returned the wrong sample count for {phase}")
    if len(result.get("attempt_ns", {}).get("samples", [])) != attempts:
        raise ValueError("C++ v1 benchmark returned the wrong total-attempt sample count")
    for index, total in enumerate(result["attempt_ns"]["samples"]):
        phase_total = sum(result["phase_ns"][phase]["samples"][index] for phase in PHASES)
        if phase_total > total:
            raise ValueError("C++ v1 phase timings exceed the enclosing attempt timing")
    result["seed_index"] = seed_index
    result["seed_commitment"] = hashlib.sha3_384(seed_for(seed_index)).hexdigest()
    return result


def integer_summary(values: list[int]) -> dict[str, int]:
    if not values:
        raise ValueError("cannot summarize an empty sample")
    return {
        "min": min(values),
        "median": int(statistics.median(values)),
        "mean": int(statistics.fmean(values)),
        "max": max(values),
        "spread_ppm": 0 if min(values) == 0 else (max(values) - min(values)) * 1_000_000 // min(values),
    }


def build_matrix(
    binary: Path,
    profile_name: str,
    seeds: int | None = None,
    attempts: int | None = None,
    source_revision: str = "unrecorded",
) -> dict[str, object]:
    configs, default_seeds, default_attempts = profile(profile_name)
    seed_count = default_seeds if seeds is None else seeds
    attempt_count = default_attempts if attempts is None else attempts
    if not 1 <= seed_count <= 128:
        raise ValueError("seeds must be in [1, 128]")
    if not 1 <= attempt_count <= 10_000:
        raise ValueError("attempts must be in [1, 10000]")

    results = []
    for config in configs:
        cases = [run_case(binary, config, seed_index, attempt_count) for seed_index in range(seed_count)]
        results.append({
            "config": asdict(config),
            "seed_count": seed_count,
            "attempts_per_seed": attempt_count,
            "prepare_ns_across_seeds": integer_summary([int(case["prepare_ns"]) for case in cases]),
            "median_attempt_ns_across_seeds": integer_summary(
                [int(case["attempt_ns"]["median"]) for case in cases]
            ),
            "median_phase_ns_across_seeds": {
                phase: integer_summary([int(case["phase_ns"][phase]["median"]) for case in cases])
                for phase in PHASES
            },
            "cases": cases,
        })

    return {
        "format": "soveroot-pow-research-matrix-v1",
        "warning": WARNING,
        "profile": profile_name,
        "source_revision": source_revision,
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
            "clock": "C++ std::chrono::steady_clock",
            "seed_derivation": "SHA3-384(Soveroot/PowResearch/BenchmarkSeed/v1\\0 || uint32_le(index))",
            "changes_per_config": "one parameter family relative to baseline",
            "thermal_control": "not measured; record externally for published studies",
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--profile", choices=("smoke", "standard"), default="standard")
    parser.add_argument("--seeds", type=int)
    parser.add_argument("--attempts", type=int)
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
