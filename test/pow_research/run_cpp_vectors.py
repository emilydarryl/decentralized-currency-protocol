# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Compare the standalone C++ PoW research VM with canonical JSON vectors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VECTORS = REPOSITORY_ROOT / "contrib" / "pow_research" / "vectors" / "v0.json"


def parse_output(output: str) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError(f"malformed C++ output line: {line!r}")
        parsed[key] = value.split(",") if key == "registers" else value
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--vectors", default=DEFAULT_VECTORS, type=Path)
    args = parser.parse_args()

    document = json.loads(args.vectors.read_text(encoding="utf-8"))
    if document["format"] != "soveroot-pow-research-v0":
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
                str(params["program_instructions"]),
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
        raise AssertionError("C++ differential failures:\n" + "\n".join(failures))
    print(f"All {len(document['vectors'])} C++ differential vectors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
