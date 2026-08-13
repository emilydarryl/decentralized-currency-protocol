# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Compare C++ and Python fail-closed online bounded-probe boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contrib.pow_research_v1.bounded_probe import probe_bounded_evaluator
from contrib.pow_research_v1.powvm import Params, prepare_epoch


SOURCE_VECTORS = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED_VECTORS = ROOT / "contrib" / "pow_research_v1" / "vectors" / "bounded_probe_v0.json"


def normalized_python(vector: dict[str, object], params: Params) -> dict[str, object]:
    probe = probe_bounded_evaluator(
        prepare_epoch(bytes.fromhex(str(vector["seed"])), params),
        bytes.fromhex(str(vector["header"])),
        int(vector["nonce"]),
    ).to_dict()
    return {
        "status": probe["status"],
        "layout": probe["layout"],
        "completed_iterations": probe["completed_iterations"],
        "reads": probe["reads"],
        "cache_hits": probe["cache_hits"],
        "initial_zero_reads": probe["initial_zero_reads"],
        "materialized_misses": probe["materialized_misses"],
        "writes": probe["writes"],
        "evictions": probe["evictions"],
        "miss": {
            "consumer_kind": probe["miss_consumer_kind"],
            "consumer": probe["miss_consumer"],
            "slot": probe["miss_slot"],
            "word": probe["miss_word"],
        },
        "state_commitment": probe["state_commitment"],
        "digest": None,
        "memory_commitment": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    args = parser.parse_args()
    source = json.loads(SOURCE_VECTORS.read_text(encoding="utf-8"))
    fixed = json.loads(FIXED_VECTORS.read_text(encoding="utf-8"))
    params = Params(**source["params"])
    failures: list[str] = []
    for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
        completed = subprocess.run(
            [
                str(args.binary.resolve()),
                "bounded-probe",
                vector["seed"],
                vector["header"],
                str(vector["nonce"]),
                str(params.dataset_bytes),
                str(params.scratchpad_bytes),
                str(params.passes),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cpp = json.loads(completed.stdout)
        cpp.pop("format")
        cpp.pop("warning")
        cpp.pop("params")
        cpp.pop("nonce")
        python = normalized_python(vector, params)
        expected_boundary = {
            "layout": fixed["layout"],
            **{key: expected[key] for key in (
                "completed_iterations", "reads", "cache_hits", "initial_zero_reads",
                "writes", "evictions", "miss", "state_commitment",
            )},
            "status": "refused_materialized_miss",
            "materialized_misses": 1,
            "digest": None,
            "memory_commitment": None,
        }
        if cpp != python or python != expected_boundary:
            failures.append(str(vector["name"]))
        else:
            print(f"PASS bounded-probe {vector['name']}")
    if failures:
        raise AssertionError("C++/Python bounded-probe mismatch: " + ", ".join(failures))
    print(f"All {len(source['vectors'])} bounded-probe vectors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
