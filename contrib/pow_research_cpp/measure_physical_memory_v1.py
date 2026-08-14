# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Measure whole-process RSS for ordinary and physically accounted v1 runs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

try:
    from .benchmark_matrix_v1 import HEADER, seed_for
    from .versioned_graph_v1 import profile
except ImportError:  # Direct script execution.
    from benchmark_matrix_v1 import HEADER, seed_for
    from versioned_graph_v1 import profile


TIME_FIELDS = {
    "Maximum resident set size (kbytes)": "maximum_resident_set_bytes",
    "Minor (reclaiming a frame) page faults": "minor_page_faults",
    "Major (requiring I/O) page faults": "major_page_faults",
}


def parse_verbose_time(text: str) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for line in text.splitlines():
        stripped = line.strip()
        for label, output_name in TIME_FIELDS.items():
            prefix = f"{label}: "
            if stripped.startswith(prefix):
                value = int(stripped[len(prefix):])
                parsed[output_name] = value * 1024 if output_name.endswith("_bytes") else value
    missing = set(TIME_FIELDS.values()) - set(parsed)
    if missing:
        raise ValueError(f"missing /usr/bin/time fields: {sorted(missing)}")
    return parsed


def timed_json(command: list[str], directory: Path) -> tuple[dict[str, object], dict[str, int]]:
    timing_path = directory / "time.txt"
    completed = subprocess.run(
        ["/usr/bin/time", "-v", "-o", str(timing_path), *command],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout), parse_verbose_time(
        timing_path.read_text(encoding="utf-8")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--profile", choices=("smoke", "standard"), default="standard")
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--operation-limit", type=int, default=100)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.seeds <= 0 or args.operation_limit <= 0:
        raise ValueError("seeds and operation-limit must be positive")
    params, _ = profile(args.profile)
    binary = str(args.binary.resolve())
    cases: list[dict[str, object]] = []
    for seed_index in range(args.seeds):
        common = [
            seed_for(seed_index).hex(),
            HEADER.hex(),
            "0",
            str(params.dataset_bytes),
            str(params.scratchpad_bytes),
            str(params.passes),
        ]
        with tempfile.TemporaryDirectory(prefix="soveroot-pow-rss-") as temp:
            directory = Path(temp)
            ordinary, ordinary_usage = timed_json([binary, *common], directory)
            attacked, attacked_usage = timed_json(
                [
                    binary,
                    "recursive-regenerate-physically-accounted-bundle",
                    *common,
                    str(args.operation_limit),
                ],
                directory,
            )
        accounting = attacked["physical_memory_accounting"]
        half_budget = params.scratchpad_bytes // 2
        if accounting["accounted_bytes"] != half_budget:
            raise AssertionError("logical physical accounting does not equal half-scratch budget")
        cases.append(
            {
                "seed_index": seed_index,
                "ordinary": {
                    "status": ordinary.get("status", "exact_complete"),
                    **ordinary_usage,
                },
                "attacker": {
                    "status": attacked["status"],
                    "completed_iterations": attacked["completed_iterations"],
                    "operation_counts": attacked["operation_counts"],
                    "physical_memory_accounting": accounting,
                    **attacked_usage,
                },
                "attacker_whole_process_rss_exceeds_half_budget": (
                    attacked_usage["maximum_resident_set_bytes"] > half_budget
                ),
            }
        )
    document = {
        "format": "soveroot-pow-v1-physical-memory-diagnostic-v0",
        "warning": "SHARED-RUNNER WHOLE-PROCESS DIAGNOSTIC; not controlled-host gate evidence",
        "profile": args.profile,
        "params": {
            "dataset_bytes": params.dataset_bytes,
            "scratchpad_bytes": params.scratchpad_bytes,
            "passes": params.passes,
        },
        "operation_limit": args.operation_limit,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_runner_name": os.environ.get("RUNNER_NAME"),
        },
        "interpretation": {
            "whole_process_rss": "includes executable, runtime, epoch context, dataset, and attack state",
            "shared_components": "dataset and executable code are reported but are not attack-specific",
            "gate_assessment": "NOT_ASSESSED",
        },
        "cases": cases,
    }
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(document, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
