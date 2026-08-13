# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Compare independent C++ and Python repeated recursive-regeneration results."""

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
from contrib.pow_research_v1.repeated_recursive_regeneration import (
    reconstruct_repeatedly_recursively,
)


SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    args = parser.parse_args()
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    params = Params(**source["params"])
    failures: list[str] = []
    for vector in source["vectors"]:
        completed = subprocess.run(
            [str(args.binary.resolve()), "recursive-regenerate-repeated", vector["seed"],
             vector["header"], str(vector["nonce"]), str(params.dataset_bytes),
             str(params.scratchpad_bytes), str(params.passes)],
            check=True, capture_output=True, text=True,
        )
        cpp = json.loads(completed.stdout)
        for key in ("format", "warning", "params", "nonce"):
            cpp.pop(key)
        python = reconstruct_repeatedly_recursively(
            prepare_epoch(bytes.fromhex(vector["seed"]), params),
            bytes.fromhex(vector["header"]), vector["nonce"],
        ).to_dict()
        if cpp != python:
            failures.append(vector["name"])
            print(f"C++ mismatch for {vector['name']}:\n{json.dumps(cpp, indent=2)}")
        else:
            print(f"PASS repeated-recursive-regeneration {vector['name']}")
    if failures:
        raise AssertionError(
            "C++/Python repeated recursive regeneration mismatch: " + ", ".join(failures)
        )
    print(f"All {len(source['vectors'])} repeated recursive regeneration vectors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
