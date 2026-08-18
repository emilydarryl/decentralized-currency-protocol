#!/usr/bin/env python3
"""Compare the reference and independent miner implementations byte-for-byte."""

from __future__ import annotations

import argparse
import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


class InteroperabilityError(RuntimeError):
    """Raised when independent implementations disagree."""


def load_reference_miner(path: Path):
    spec = importlib.util.spec_from_file_location("soveroot_reference_miner", path)
    if spec is None or spec.loader is None:
        raise InteroperabilityError(f"cannot load reference miner from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_report(binary: Path, fixture: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [str(binary), "vector-report", "--fixture", str(fixture)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise InteroperabilityError(f"{binary.name} vector report failed: {detail.strip()}") from error
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise InteroperabilityError(f"{binary.name} returned malformed JSON") from error
    if not isinstance(value, dict):
        raise InteroperabilityError(f"{binary.name} report is not an object")
    return value


def reference_block(miner, candidate: dict[str, Any]) -> dict[str, Any]:
    coinbase = miner.build_coinbase(
        height=int(candidate["height"]),
        value=int(candidate["coinbase_value"]),
        payout_script=bytes.fromhex(candidate["payout_script_hex"]),
    )
    if coinbase.block_bytes.hex() != candidate["coinbase_tx_hex"]:
        raise InteroperabilityError("reference coinbase bytes disagree with the fixture")
    transaction_bytes = [coinbase.block_bytes]
    transaction_hashes = [coinbase.txid_hash]
    for transaction_hex, txid_hex in zip(
        candidate["transaction_data"], candidate["transaction_ids"], strict=True
    ):
        transaction = bytes.fromhex(transaction_hex)
        digest = miner.hash256(transaction)
        if digest[::-1].hex() != txid_hex:
            raise InteroperabilityError("reference transaction hash disagrees with fixture txid")
        transaction_bytes.append(transaction)
        transaction_hashes.append(digest)
    root = miner.merkle_root(transaction_hashes)
    if root.hex() != candidate["merkle_root_internal_hex"]:
        raise InteroperabilityError("reference merkle root disagrees with fixture")
    previous = bytes.fromhex(candidate["previous_block_hash"])[::-1]
    header_prefix = (
        struct.pack("<I", int(candidate["version"]))
        + previous
        + root
        + struct.pack("<I", int(candidate["curtime"]))
        + struct.pack("<I", int(candidate["bits"]))
    )
    header, nonce, digest = miner.solve_header(header_prefix, int(candidate["bits"]), 100)
    block = header + miner.encode_varint(len(transaction_bytes)) + b"".join(transaction_bytes)
    return {
        "nonce": nonce,
        "hash": digest[::-1].hex(),
        "header_hex": header.hex(),
        "block_hex": block.hex(),
    }


def compare(reference: dict[str, Any], independent: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    reference_negatives = reference.get("negative_results")
    independent_negatives = independent.get("negative_results")
    negatives_pass = (
        isinstance(reference_negatives, list)
        and bool(reference_negatives)
        and reference_negatives == independent_negatives
        and all(item.get("passed") is True for item in reference_negatives)
    )
    comparisons = {
        "authentication_transcript": reference.get("authentication")
        == independent.get("authentication"),
        "wire_payloads": reference.get("wire_transcript") == independent.get("wire_transcript"),
        "template_commitment": reference.get("template_commitment_sha256")
        == independent.get("template_commitment_sha256"),
        "negative_vectors": negatives_pass,
        "block_bytes": independent.get("solved_block") == block,
    }
    failed = [name for name, passed in comparisons.items() if not passed]
    if failed:
        raise InteroperabilityError("interoperability disagreement: " + ", ".join(failed))
    return comparisons


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-helper", type=Path, required=True)
    parser.add_argument("--independent-miner", type=Path, required=True)
    parser.add_argument("--reference-miner", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    candidate = fixture["candidate"]
    reference = run_report(args.reference_helper, args.fixture)
    independent = run_report(args.independent_miner, args.fixture)
    miner = load_reference_miner(args.reference_miner)
    block = reference_block(miner, candidate)
    if block != fixture["expected_block"]:
        raise InteroperabilityError("reference block bytes disagree with canonical fixture")
    commitment_input = dict(candidate)
    expected_commitment = commitment_input.pop("template_commitment_sha256")
    if miner.canonical_template_commitment(commitment_input) != expected_commitment:
        raise InteroperabilityError("reference template commitment disagrees with fixture")
    comparisons = compare(reference, independent, block)
    artifact = {
        "format": "soveroot-sv2-jd-interoperability-evidence-v0",
        "profile": fixture["profile"],
        "fixture": str(args.fixture).replace("\\", "/"),
        "all_exact_results_match": True,
        "comparisons": comparisons,
        "reference": reference,
        "independent": independent,
        "reference_block": block,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Interoperability evidence: {args.output}")
    print("Exact authentication, wire, negative-vector, commitment, and block results match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
