# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render an informational Markdown report from a raw PoW CPU matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _milliseconds(nanoseconds: int) -> str:
    return f"{nanoseconds / 1_000_000:.3f}"


def render(matrix_path: Path, gates_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    if matrix.get("format") != "soveroot-pow-research-matrix-v0":
        raise ValueError("unsupported matrix format")
    if gates.get("format") != "soveroot-pow-evaluation-gates-v0":
        raise ValueError("unsupported gate format")

    lines = [
        f"# Soveroot CPU Research Baseline: {label}",
        "",
        "Status: **INFORMATIONAL ONLY — NO POW GATE PASSED**",
        "",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`",
        f"Source revision: `{matrix.get('source_revision', 'unrecorded')}`",
        f"Profile: `{matrix['profile']}`",
        "",
        "## Host and method",
        "",
        f"- Platform: `{matrix['host']['platform']}`",
        f"- Machine: `{matrix['host']['machine']}`",
        f"- CPU model: `{matrix['host'].get('cpu_model', 'unavailable')}`",
        f"- Logical CPUs visible: `{matrix['host']['logical_cpus']}`",
        f"- Runner image: `{matrix['host'].get('runner_image', 'unrecorded')}`",
        "- Clock: C++ `std::chrono::steady_clock`",
        "- Thermal state and package energy were not measured.",
        "",
        "## Results",
        "",
        "| Configuration | Dataset KiB | Scratch KiB | Instructions | Passes | Working set KiB | Prepare median ms | Attempt median ms | Seed spread |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in matrix["results"]:
        config = result["config"]
        first_case = result["cases"][0]
        spread = result["median_attempt_ns_across_seeds"]["spread_ppm"] / 10_000
        lines.append(
            f"| {config['name']} | {config['dataset_bytes'] // 1024} | {config['scratchpad_bytes'] // 1024} | "
            f"{config['program_instructions']} | {config['passes']} | {first_case['working_set_bytes_estimate'] / 1024:.1f} | "
            f"{_milliseconds(result['prepare_ns_across_seeds']['median'])} | "
            f"{_milliseconds(result['median_attempt_ns_across_seeds']['median'])} | {spread:.2f}% |"
        )

    seed_gate = next(gate for gate in gates["gates"] if gate["id"] == "seed_variance")
    observed_seeds = min(result["seed_count"] for result in matrix["results"])
    lines += [
        "",
        "## Gate interpretation",
        "",
        f"The seed-variance gate requires at least {seed_gate['minimum_evidence']['unbiased_seeds_per_device']:,} seeds per controlled device; this run used {observed_seeds}. "
        "The measurements are therefore a pipeline screening signal, not a pass or failure.",
        "",
        "This run cannot evaluate energy efficiency, retail-price performance, memory recomputation, large-batch amortization, GPU advantage, FPGA or ASIC advantage, quantum advantage, or mining-template autonomy.",
        "",
        "## Reproduction requirements",
        "",
        "Preserve the raw JSON with this report. Repeat the same source revision and profile on declared low-cost, midrange, and high-end physical systems while recording compiler flags, operating system, power mode, package energy, temperature, and background load.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--gates", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = render(args.matrix, args.gates, args.label)
    except ValueError as error:
        parser.error(str(error))
    args.output.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
