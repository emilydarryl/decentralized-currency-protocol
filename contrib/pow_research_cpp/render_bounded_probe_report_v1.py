# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Render the fail-closed online bounded-probe report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics


def render(matrix_path: Path, method_path: Path, label: str) -> str:
    raw = matrix_path.read_bytes()
    matrix = json.loads(raw)
    method = json.loads(method_path.read_text(encoding="utf-8"))
    if matrix["format"] != "soveroot-pow-v1-online-bounded-probe-matrix-v0":
        raise ValueError("unsupported bounded-probe matrix format")
    if method["format"] != "soveroot-pow-v1-online-bounded-probe-method-v0":
        raise ValueError("unsupported bounded-probe method format")

    completed = [case["completed_iterations"] for case in matrix["cases"]]
    lines = [
        f"# Soveroot PoW v1 Online Bounded Probe: {label}",
        "",
        "**NON-CONSENSUS FAIL-CLOSED PREFIX PROBE - NO POW GATE ASSESSED**",
        "",
        f"Source revision: `{matrix['source_revision']}`  ",
        f"Profile: `{matrix['profile']}`; seeds: {matrix['seed_count']}  ",
        f"Raw matrix SHA3-384: `{hashlib.sha3_384(raw).hexdigest()}`",
        "",
        "## Result",
        "",
        f"Every run refused without a digest: `{str(matrix['all_runs_refused_without_digest']).lower()}`. ",
        f"Exact iterations before refusal: minimum {min(completed):,}, median {statistics.median(completed):,.1f}, maximum {max(completed):,}.",
        "",
        "| Seed | Exact iterations | First missing read | Cache capacity | Evictions | State commitment |",
        "| ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for case in matrix["cases"]:
        miss = case["miss"] if "miss" in case else {
            "consumer_kind": case["miss_consumer_kind"],
            "consumer": case["miss_consumer"],
            "slot": case["miss_slot"],
            "word": case["miss_word"],
        }
        lines.append(
            f"| {case['seed_index']} | {case['completed_iterations']:,} "
            f"| kind {miss['consumer_kind']}, consumer {miss['consumer']}, slot {miss['slot']}, word {miss['word']} "
            f"| {case['layout']['cache_capacity']:,} | {case['evictions']:,} "
            f"| `{case['state_commitment']}` |"
        )
    lines.extend([
        "",
        "The probe returns zero only for a word proven unwritten by its bitmap. A missing materialized word stops the evaluator before state mutation, and the report emits no digest or memory commitment.",
        "",
        "## Why the gate remains open",
        "",
    ])
    lines.extend(f"- {item}" for item in method["limitations"])
    lines.extend([
        "",
        "This milestone establishes online admission, exact-prefix agreement, and a reproducible reconstruction boundary. It does not reconstruct the missing value, finish a proof, measure attack throughput, or measure actual process memory. The mandatory time-memory gate remains open.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--method", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = render(args.matrix, args.method, args.label)
    if args.output:
        args.output.write_text(report, encoding="utf-8", newline="\n")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
