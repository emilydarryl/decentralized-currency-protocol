# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Verify that v1 trace instrumentation preserves canonical outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VECTORS = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--vectors", default=DEFAULT_VECTORS, type=Path)
    args = parser.parse_args()
    vectors = json.loads(args.vectors.read_text(encoding="utf-8"))
    params = vectors["params"]
    for vector in vectors["vectors"]:
        completed = subprocess.run(
            [
                str(args.binary.resolve()),
                "trace",
                vector["seed"],
                vector["header"],
                str(vector["nonce"]),
                str(params["dataset_bytes"]),
                str(params["scratchpad_bytes"]),
                str(params["passes"]),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        expected = vector["result"]
        if result["digest"] != expected["digest"]:
            raise AssertionError(f"{vector['name']}: digest changed under tracing")
        if result["memory_commitment"] != expected["memory_commitment"]:
            raise AssertionError(f"{vector['name']}: memory commitment changed under tracing")
        if not result["trace"]["trace_commitment"]:
            raise AssertionError(f"{vector['name']}: trace commitment is missing")
        simulations = result["trace"]["cache_simulations"]
        for name in ("compact_half_budget", "conservative_half_budget"):
            scenario = simulations[name]
            if scenario["budget_bytes"] != params["scratchpad_bytes"] // 2:
                raise AssertionError(f"{vector['name']}: {name} exceeds the half-memory budget")
            if scenario["offline_optimal"]["materialized_read_misses"] > scenario["lru"]["materialized_read_misses"]:
                raise AssertionError(f"{vector['name']}: offline optimum is worse than LRU")
        print(f"PASS trace {vector['name']}")
    print(f"All {len(vectors['vectors'])} C++ v1 trace vectors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
