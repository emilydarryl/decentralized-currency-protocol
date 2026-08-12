# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Compare the standalone C++ v1 candidate with canonical Python vectors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from run_cpp_vectors import parse_output


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VECTORS = REPOSITORY_ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--vectors", default=DEFAULT_VECTORS, type=Path)
    args = parser.parse_args()

    document = json.loads(args.vectors.read_text(encoding="utf-8"))
    if document["format"] != "soveroot-pow-research-v1":
        raise ValueError("unsupported vector format")
    params = document["params"]

    failures: list[str] = []
    for vector in document["vectors"]:
        completed = subprocess.run(
            [
                str(args.binary.resolve()),
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
        actual = parse_output(completed.stdout)
        expected = vector["result"]
        if actual != expected:
            differing = sorted(key for key in expected if actual.get(key) != expected[key])
            failures.append(f"{vector['name']}: {', '.join(differing)}")
        else:
            print(f"PASS {vector['name']}")

    if failures:
        raise AssertionError("C++ v1 differential failures:\n" + "\n".join(failures))
    print(f"All {len(document['vectors'])} C++ v1 differential vectors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
