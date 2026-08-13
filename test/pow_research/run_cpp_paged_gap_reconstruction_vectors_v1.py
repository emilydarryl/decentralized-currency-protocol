# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Compare C++ and Python paged-gap reconstruction boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contrib.pow_research_v1.paged_gap_reconstruction import reconstruct_with_paged_gaps
from contrib.pow_research_v1.powvm import Params, prepare_epoch


SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "paged_gap_reconstruction_v0.json"


def normalize_python(vector: dict[str, object], params: Params) -> dict[str, object]:
    result = reconstruct_with_paged_gaps(
        prepare_epoch(bytes.fromhex(str(vector["seed"])), params),
        bytes.fromhex(str(vector["header"])), int(vector["nonce"]),
    ).to_dict()
    result.pop("execution_result")
    result["digest"] = None
    result["memory_commitment"] = None
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    args = parser.parse_args()
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    fixed = json.loads(FIXED.read_text(encoding="utf-8"))
    params = Params(**source["params"])
    failures: list[str] = []
    for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
        completed = subprocess.run(
            [str(args.binary.resolve()), "bounded-reconstruct-paged", vector["seed"],
             vector["header"], str(vector["nonce"]), str(params.dataset_bytes),
             str(params.scratchpad_bytes), str(params.passes)],
            check=True, capture_output=True, text=True,
        )
        cpp = json.loads(completed.stdout)
        for key in ("format", "warning", "params", "nonce"):
            cpp.pop(key)
        python = normalize_python(vector, params)
        expected_document = {
            "status": "refused_paged_gap_exhausted",
            "layout": fixed["layout"],
            **dict(zip(fixed["counter_fields"], expected["counters"], strict=True)),
            "max_reconstruction_depth": 1,
            "all_replay_states_matched": True,
            "transcript_commitment": expected["transcript_commitment"],
            "first_reconstruction": dict(zip(fixed["reconstruction_fields"], expected["first"], strict=True)),
            "last_reconstruction": dict(zip(fixed["reconstruction_fields"], expected["last"], strict=True)),
            "exhaustion": dict(zip(fixed["exhaustion_fields"], expected["exhaustion"], strict=True)),
            "digest": None,
            "memory_commitment": None,
        }
        if cpp != python or python != expected_document:
            failures.append(str(vector["name"]))
            if cpp != python:
                print(f"C++ mismatch for {vector['name']}:\n{json.dumps(cpp, indent=2)}")
        else:
            print(f"PASS paged-gap-reconstruction {vector['name']}")
    if failures:
        raise AssertionError("C++/Python paged-gap reconstruction mismatch: " + ", ".join(failures))
    print(f"All {len(source['vectors'])} paged-gap reconstruction vectors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
