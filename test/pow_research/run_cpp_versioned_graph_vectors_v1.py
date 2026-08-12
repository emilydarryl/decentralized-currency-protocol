# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Compare C++ and Python v1 versioned graph commitments and fixed vectors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contrib.pow_research_v1.powvm import Params, prepare_epoch
from contrib.pow_research_v1.versioned_graph import FORMAT, evaluate_versioned_graph


DEFAULT_VECTORS = ROOT / "contrib" / "pow_research_v1" / "vectors" / "versioned_graph_v0.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--vectors", default=DEFAULT_VECTORS, type=Path)
    args = parser.parse_args()
    vectors = json.loads(args.vectors.read_text(encoding="utf-8"))
    params = Params(**vectors["params"])
    for vector in vectors["vectors"]:
        context = prepare_epoch(bytes.fromhex(vector["seed"]), params)
        python_result, python_graph = evaluate_versioned_graph(
            context,
            bytes.fromhex(vector["header"]),
            vector["nonce"],
        )
        completed = subprocess.run(
            [
                str(args.binary.resolve()),
                "graph",
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
        if cpp["format"] != FORMAT:
            raise AssertionError(f"{vector['name']}: unsupported C++ graph format")
        if cpp["digest"] != python_result.digest.hex():
            raise AssertionError(f"{vector['name']}: canonical digest changed")
        if cpp["memory_commitment"] != python_result.memory_commitment.hex():
            raise AssertionError(f"{vector['name']}: canonical memory commitment changed")
        if cpp["graph"] != python_graph:
            raise AssertionError(f"{vector['name']}: C++ and Python graph summaries differ")
        if cpp["graph"]["graph_commitment"] != vector["graph_commitment"]:
            raise AssertionError(f"{vector['name']}: fixed graph commitment changed")
        print(f"PASS versioned graph {vector['name']}")
    print(f"All {len(vectors['vectors'])} C++/Python versioned graph vectors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
