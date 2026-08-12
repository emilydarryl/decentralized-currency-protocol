# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Emit reproducible JSON timing data for the non-consensus PoW prototype."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time

from .powvm import Params, evaluate, prepare_epoch


def benchmark(params: Params, attempts: int) -> dict[str, object]:
    params.validate()
    if not 1 <= attempts <= 10_000:
        raise ValueError("attempts must be in [1, 10000]")
    seed = bytes.fromhex("42" * 48)
    header = b"Soveroot non-consensus benchmark header"

    start_prepare = time.perf_counter_ns()
    context = prepare_epoch(seed, params)
    prepare_ns = time.perf_counter_ns() - start_prepare

    samples = []
    digest_xor = 0
    for nonce in range(attempts):
        started = time.perf_counter_ns()
        result = evaluate(context, header, nonce)
        samples.append(time.perf_counter_ns() - started)
        digest_xor ^= int.from_bytes(result.digest[:8], "little")

    return {
        "format": "soveroot-pow-research-benchmark-v0",
        "warning": "NON-CONSENSUS PROTOTYPE; Python timings do not predict optimized mining economics",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "params": params.to_dict(),
        "attempts": attempts,
        "prepare_ns": prepare_ns,
        "attempt_ns": {
            "min": min(samples),
            "median": int(statistics.median(samples)),
            "mean": int(statistics.fmean(samples)),
            "max": max(samples),
        },
        "digest_xor_64": f"{digest_xor:016x}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--dataset-kib", type=int, default=256)
    parser.add_argument("--scratchpad-kib", type=int, default=64)
    parser.add_argument("--instructions", type=int, default=64)
    parser.add_argument("--passes", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.attempts <= 10_000:
        parser.error("--attempts must be in [1, 10000]")
    params = Params(
        dataset_bytes=args.dataset_kib * 1024,
        scratchpad_bytes=args.scratchpad_kib * 1024,
        program_instructions=args.instructions,
        passes=args.passes,
    )
    try:
        params.validate()
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(benchmark(params, args.attempts), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
