# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Compare independent C++ and Python time-checkpoint screens."""

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
from contrib.pow_research_v1.time_checkpoint_screen import screen_time_checkpoints


SOURCE = ROOT / "contrib" / "pow_research_v1" / "vectors" / "v1.json"
FIXED = ROOT / "contrib" / "pow_research_v1" / "vectors" / "time_checkpoint_screen_v0.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    args = parser.parse_args()
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    fixed = json.loads(FIXED.read_text(encoding="utf-8"))
    params = Params(**source["params"])
    failures: list[str] = []
    for vector, expected in zip(source["vectors"], fixed["cases"], strict=True):
        if vector["name"] != expected["name"]:
            failures.append(vector["name"])
            continue
        completed = subprocess.run(
            [str(args.binary.resolve()), "checkpoint-screen", vector["seed"], vector["header"],
             str(vector["nonce"]), str(params.dataset_bytes), str(params.scratchpad_bytes),
             str(params.passes)], check=True, capture_output=True, text=True,
        )
        cpp = json.loads(completed.stdout)
        cpp.pop("params"); cpp.pop("nonce")
        python = screen_time_checkpoints(
            prepare_epoch(bytes.fromhex(vector["seed"]), params),
            bytes.fromhex(vector["header"]), vector["nonce"],
        ).to_dict()
        if cpp != python:
            failures.append(vector["name"])
            print(f"C++ mismatch for {vector['name']}:\n{json.dumps(cpp, indent=2)}")
            continue
        observed_cuts = [[cut[field] for field in fixed["cut_fields"]] for cut in python["cuts"]]
        if (python["layout"] != fixed["layout"]
                or python["global_maximum_live_values"] != expected["global_maximum_live_values"]
                or python["screen_commitment"] != expected["screen_commitment"]
                or observed_cuts != expected["cuts"]):
            failures.append(vector["name"])
        else:
            print(f"PASS time-checkpoint-screen {vector['name']}")
    if failures:
        raise AssertionError("C++/Python time checkpoint mismatch: " + ", ".join(failures))
    print(f"All {len(source['vectors'])} time-checkpoint screen vectors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
