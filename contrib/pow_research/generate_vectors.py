# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Generate canonical JSON vectors for the non-consensus PoW prototype."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .powvm import Params, evaluate, prepare_epoch


VECTOR_PARAMS = Params(
    dataset_bytes=64 * 1024,
    scratchpad_bytes=8 * 1024,
    program_instructions=32,
    passes=2,
)

CASES = (
    {
        "name": "zero-seed-zero-nonce",
        "seed": bytes(48),
        "header": b"Soveroot research vector 0",
        "nonce": 0,
    },
    {
        "name": "incrementing-seed",
        "seed": bytes(range(48)),
        "header": bytes(range(80)),
        "nonce": 0x0123456789ABCDEF,
    },
    {
        "name": "high-bit-pattern",
        "seed": bytes.fromhex("a5" * 48),
        "header": bytes.fromhex("ff00" * 40),
        "nonce": (1 << 64) - 1,
    },
)


def build_vectors() -> dict[str, object]:
    vectors = []
    for case in CASES:
        context = prepare_epoch(case["seed"], VECTOR_PARAMS)
        result = evaluate(context, case["header"], case["nonce"])
        vectors.append({
            "name": case["name"],
            "seed": case["seed"].hex(),
            "header": case["header"].hex(),
            "nonce": case["nonce"],
            "result": result.to_dict(),
        })
    return {
        "format": "soveroot-pow-research-v0",
        "warning": "NON-CONSENSUS RESEARCH VECTORS; constants and outputs may change",
        "params": VECTOR_PARAMS.to_dict(),
        "vectors": vectors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write JSON to this path instead of stdout")
    args = parser.parse_args()
    rendered = json.dumps(build_vectors(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
