# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render an informational Markdown report from a raw PoW v1 CPU matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _milliseconds(nanoseconds: int) -> str:
    return f"{nanoseconds / 1_000_000:.3f}"


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator


def _percent(part: int, whole: int) -> float:
    return part * 100 / whole


def _fmt_ratio(value: float) -> str:
    return f"{value:.2f}x"


def _fmt_percent(value: float) -> str:
    return f"{value:.1f}%"


def _attempt_median(results: dict[str, dict[str, object]], name: str) -> int:
    return int(results[name]["median_attempt_ns_across_seeds"]["median"])


def _classify_min(value: float, advance_min: float, redesign_below: float) -> str:
    if value >= advance_min:
        return "ADVANCE"
    if value < redesign_below:
        return "REDESIGN"
    return "INCONCLUSIVE"


def _classify_max(value: float, advance_max: float, redesign_above: float) -> str:
    if value <= advance_max:
        return "ADVANCE"
    if value > redesign_above:
        return "REDESIGN"
    return "INCONCLUSIVE"


def _classify_range(
    value: float,
    advance_min: float,
    advance_max: float,
    redesign_below: float,
    redesign_above: float,
) -> str:
    if advance_min <= value <= advance_max:
        return "ADVANCE"
    if value < redesign_below or value > redesign_above:
        return "REDESIGN"
    return "INCONCLUSIVE"


def render(matrix_path: Path, gates_path: Path, screening_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    screening = json.loads(screening_path.read_text(encoding="utf-8"))
    if matrix.get("format") != "soveroot-pow-research-matrix-v1":
        raise ValueError("unsupported v1 matrix format")
    if gates.get("format") != "soveroot-pow-evaluation-gates-v0":
        raise ValueError("unsupported gate format")
    if screening.get("format") != "soveroot-pow-v1-screening-objectives-v0":
        raise ValueError("unsupported v1 screening format")

    lines = [
        f"# Soveroot PoW v1 CPU Screening: {label}",
        "",
        "Status: **INFORMATIONAL V1 SCREEN -- NO POW GATE PASSED**",
        "",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`",
        f"Source revision: `{matrix.get('source_revision', 'unrecorded')}`",
        f"Profile: `{matrix['profile']}`",
        f"Screening policy: `{screening['format']}` version `{screening['version']}`",
        "",
        "## Host and method",
        "",
        f"- Platform: `{matrix['host']['platform']}`",
        f"- Machine: `{matrix['host']['machine']}`",
        f"- CPU model: `{matrix['host'].get('cpu_model', 'unavailable')}`",
        f"- Logical CPUs visible: `{matrix['host']['logical_cpus']}`",
        f"- Runner image: `{matrix['host'].get('runner_image', 'unrecorded')}`",
        "- Clock: C++ `std::chrono::steady_clock`",
        "- Thermal state, package energy, and memory traffic were not measured.",
        "",
        "## Results",
        "",
        "| Configuration | Dataset KiB | Scratch KiB | Passes | Working set KiB | Prepare median ms | Attempt median ms | Seed spread |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in matrix["results"]:
        config = result["config"]
        first_case = result["cases"][0]
        spread = result["median_attempt_ns_across_seeds"]["spread_ppm"] / 10_000
        lines.append(
            f"| {config['name']} | {config['dataset_bytes'] // 1024} | "
            f"{config['scratchpad_bytes'] // 1024} | {config['passes']} | "
            f"{first_case['working_set_bytes_estimate'] / 1024:.1f} | "
            f"{_milliseconds(result['prepare_ns_across_seeds']['median'])} | "
            f"{_milliseconds(result['median_attempt_ns_across_seeds']['median'])} | "
            f"{spread:.2f}% |"
        )

    lines += [
        "",
        "## Median phase shares",
        "",
        "Phase medians are summarized independently across seeds, so percentages may not total exactly 100%.",
        "",
        "| Configuration | Input setup | Zero allocation | Mixing | Finalization |",
        "|---|---:|---:|---:|---:|",
    ]
    for result in matrix["results"]:
        total = int(result["median_attempt_ns_across_seeds"]["median"])
        phases = result["median_phase_ns_across_seeds"]
        lines.append(
            f"| {result['config']['name']} | "
            f"{_fmt_percent(_percent(phases['input_setup']['median'], total))} | "
            f"{_fmt_percent(_percent(phases['scratchpad_init']['median'], total))} | "
            f"{_fmt_percent(_percent(phases['mix_execute']['median'], total))} | "
            f"{_fmt_percent(_percent(phases['finalize']['median'], total))} |"
        )

    indexed = {result["config"]["name"]: result for result in matrix["results"]}
    screens = screening["screens"]
    outcomes: list[str] = []
    lines += [
        "",
        "## Predeclared v1 software screens",
        "",
        "| Screen | Observation | Outcome |",
        "|---|---:|---|",
    ]

    if "baseline" in indexed:
        baseline = indexed["baseline"]
        total = int(baseline["median_attempt_ns_across_seeds"]["median"])
        phases = baseline["median_phase_ns_across_seeds"]
        mix_share = _percent(phases["mix_execute"]["median"], total)
        mix_rule = screens["baseline_mix_share_percent"]
        mix_outcome = _classify_min(mix_share, mix_rule["advance_min"], mix_rule["redesign_below"])
        outcomes.append(mix_outcome)
        lines.append(f"| Baseline mixing share | {_fmt_percent(mix_share)} | **{mix_outcome}** |")

        init_share = _percent(phases["scratchpad_init"]["median"], total)
        init_rule = screens["baseline_scratchpad_init_share_percent"]
        init_outcome = _classify_max(init_share, init_rule["advance_max"], init_rule["redesign_above"])
        outcomes.append(init_outcome)
        lines.append(f"| Baseline zero-allocation share | {_fmt_percent(init_share)} | **{init_outcome}** |")

        finalize_share = _percent(phases["finalize"]["median"], total)
        finalize_rule = screens["baseline_finalize_share_percent"]
        finalize_outcome = _classify_max(
            finalize_share,
            finalize_rule["advance_max"],
            finalize_rule["redesign_above"],
        )
        outcomes.append(finalize_outcome)
        lines.append(
            f"| Baseline fixed-finalization share | {_fmt_percent(finalize_share)} | "
            f"**{finalize_outcome}** |"
        )

    if {"passes-1", "passes-16"}.issubset(indexed):
        passes_ratio = _ratio(
            _attempt_median(indexed, "passes-16"),
            _attempt_median(indexed, "passes-1"),
        )
        pass_rule = screens["passes_16x_attempt_ratio"]
        pass_outcome = _classify_min(
            passes_ratio,
            pass_rule["advance_min"],
            pass_rule["redesign_below"],
        )
        outcomes.append(pass_outcome)
        lines.append(f"| 16x pass-count response | {_fmt_ratio(passes_ratio)} | **{pass_outcome}** |")

    if {"scratch-8k", "scratch-512k"}.issubset(indexed):
        scratch_ratio = _ratio(
            _attempt_median(indexed, "scratch-512k"),
            _attempt_median(indexed, "scratch-8k"),
        )
        scratch_rule = screens["scratchpad_64x_attempt_ratio"]
        scratch_outcome = _classify_range(
            scratch_ratio,
            scratch_rule["advance_min"],
            scratch_rule["advance_max"],
            scratch_rule["redesign_below"],
            scratch_rule["redesign_above"],
        )
        outcomes.append(scratch_outcome)
        lines.append(
            f"| 64x scratchpad response | {_fmt_ratio(scratch_ratio)} | "
            f"**{scratch_outcome}** |"
        )

    if {"dataset-64k", "dataset-4096k"}.issubset(indexed):
        dataset_ratio = _ratio(
            _attempt_median(indexed, "dataset-4096k"),
            _attempt_median(indexed, "dataset-64k"),
        )
        lines.append(
            f"| 64x dataset response | {_fmt_ratio(dataset_ratio)} | "
            "**UNASSESSED ON SHARED RUNNER** |"
        )

    if "REDESIGN" in outcomes:
        screen_result = "REDESIGN: at least one assessable v1 software screen crossed its predeclared redesign bound."
    elif outcomes and all(outcome == "ADVANCE" for outcome in outcomes):
        screen_result = (
            "ADVANCE SOFTWARE SCREEN ONLY: all assessable shared-runner screens met their "
            "advance bounds; the controlled dataset-cache screen and all mandatory gates remain open."
        )
    else:
        screen_result = "INCONCLUSIVE: at least one assessable screen fell between advance and redesign bounds."

    seed_gate = next(gate for gate in gates["gates"] if gate["id"] == "seed_variance")
    observed_seeds = min(result["seed_count"] for result in matrix["results"])
    lines += [
        "",
        f"Shared-runner outcome: **{screen_result}**",
        "",
        "## Gate interpretation",
        "",
        f"The seed-variance gate requires at least {seed_gate['minimum_evidence']['unbiased_seeds_per_device']:,} seeds per controlled device; this run used {observed_seeds}. "
        "The measurements are a workload-balance screen, not a pass or failure of that gate.",
        "",
        "This run cannot evaluate energy efficiency, memory recomputation, large-batch amortization, optimized GPU advantage, FPGA or ASIC advantage, quantum advantage, or mining-template autonomy.",
        "",
        "## Reproduction requirements",
        "",
        "Preserve the raw JSON with this report. Repeat the same source revision and profile on declared low-cost, midrange, and high-end physical systems while recording compiler flags, operating system, power mode, package energy, temperature, memory traffic, and background load.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--gates", required=True, type=Path)
    parser.add_argument("--screening", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = render(args.matrix, args.gates, args.screening, args.label)
    except ValueError as error:
        parser.error(str(error))
    args.output.write_text(report, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
