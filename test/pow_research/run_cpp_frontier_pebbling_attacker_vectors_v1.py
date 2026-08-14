# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Compare C++ and Python bounded frontier-pebbling boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contrib.pow_research_cpp.benchmark_matrix_v1 import HEADER, seed_for
from contrib.pow_research_cpp.versioned_graph_v1 import profile
from contrib.pow_research_v1.checkpoint_recursive_regeneration import (
    reconstruct_repeatedly_with_frontier_pebbling,
)
from contrib.pow_research_v1.powvm import prepare_epoch


FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "frontier_pebbling_attacker_v0.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    args = parser.parse_args()
    fixed = json.loads(FIXED.read_text(encoding="utf-8"))
    params, _ = profile(fixed["profile"])
    failures: list[int] = []
    for expected in fixed["cases"]:
        seed_index = expected["seed_index"]
        completed = subprocess.run(
            [
                str(args.binary.resolve()),
                "recursive-regenerate-frontier-pebbling",
                seed_for(seed_index).hex(),
                HEADER.hex(),
                str(fixed["nonce"]),
                str(params.dataset_bytes),
                str(params.scratchpad_bytes),
                str(params.passes),
                str(fixed["operation_limit"]),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cpp = json.loads(completed.stdout)
        for key in ("format", "warning", "params", "nonce"):
            cpp.pop(key)
        python = reconstruct_repeatedly_with_frontier_pebbling(
            prepare_epoch(seed_for(seed_index), params),
            HEADER,
            fixed["nonce"],
            operation_limit=fixed["operation_limit"],
        ).to_dict()
        if cpp != python:
            failures.append(seed_index)
            print(f"C++ mismatch for seed {seed_index}:\n{json.dumps(cpp, indent=2)}")
        else:
            print(f"PASS frontier-pebbling seed {seed_index}")
    if failures:
        raise AssertionError(
            "C++/Python frontier-pebbling mismatch: "
            + ", ".join(str(item) for item in failures)
        )
    print(f"All {len(fixed['cases'])} frontier-pebbling vectors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
