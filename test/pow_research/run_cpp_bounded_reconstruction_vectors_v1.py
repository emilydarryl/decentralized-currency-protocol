# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Compare C++ and Python one-miss bounded reconstruction boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contrib.pow_research_v1.bounded_reconstruction import reconstruct_first_miss
from contrib.pow_research_v1.powvm import Params, prepare_epoch


SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "bounded_reconstruction_v0.json"


def normalize_python(vector: dict[str, object], params: Params) -> dict[str, object]:
    result = reconstruct_first_miss(
        prepare_epoch(bytes.fromhex(str(vector["seed"])), params),
        bytes.fromhex(str(vector["header"])),
        int(vector["nonce"]),
    ).to_dict()
    return {
        "status": result["status"],
        "layout": result["layout"],
        **{key: result[key] for key in (
            "completed_iterations", "canonical_reads", "cache_hits", "initial_zero_reads",
            "materialized_misses", "writes", "evictions", "reconstructed_misses",
            "replayed_iterations", "replay_peak_entries", "replay_hash_probes",
        )},
        "reconstruction": {
            "consumer": result["reconstruction_consumer"],
            "slot": result["reconstruction_slot"],
            "word": result["reconstruction_word"],
            "value": result["reconstruction_value"],
            "commitment": result["reconstruction_commitment"],
        },
        "replay_state_matched": result["replay_state_matched"],
        "refusal": {
            "consumer": result["refusal_consumer"],
            "slot": result["refusal_slot"],
            "word": result["refusal_word"],
            "state_commitment": result["refusal_state_commitment"],
        },
        "digest": None,
        "memory_commitment": None,
    }


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
            [
                str(args.binary.resolve()), "bounded-reconstruct-one", vector["seed"],
                vector["header"], str(vector["nonce"]), str(params.dataset_bytes),
                str(params.scratchpad_bytes), str(params.passes),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cpp = json.loads(completed.stdout)
        for key in ("format", "warning", "params", "nonce"):
            cpp.pop(key)
        python = normalize_python(vector, params)
        counter_fields = fixed["counter_fields"]
        expected_document = {
            "status": "refused_after_one_reconstruction",
            "layout": fixed["layout"],
            **dict(zip(counter_fields, expected["counters"], strict=True)),
            "reconstructed_misses": 1,
            "reconstruction": dict(zip(fixed["reconstruction_fields"], expected["reconstruction"], strict=True)),
            "replay_state_matched": True,
            "refusal": dict(zip(fixed["refusal_fields"], expected["refusal"], strict=True)),
            "digest": None,
            "memory_commitment": None,
        }
        if cpp != python or python != expected_document:
            failures.append(str(vector["name"]))
        else:
            print(f"PASS bounded-reconstruction {vector['name']}")
    if failures:
        raise AssertionError("C++/Python bounded reconstruction mismatch: " + ", ".join(failures))
    print(f"All {len(source['vectors'])} bounded reconstruction vectors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
