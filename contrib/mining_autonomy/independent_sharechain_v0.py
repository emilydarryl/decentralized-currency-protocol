#!/usr/bin/env python3
"""Independently verify the frozen Soveroot private-lab sharechain v0 corpus.

This implementation deliberately imports no code from sharechain_v0.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any, Sequence


PROFILE = "soveroot-sharechain-labnet-v0"
CORPUS_KIND = "soveroot-sharechain-adversarial-v0"
SHARE_KIND = "soveroot-labnet-share-v0"
ZERO = "0" * 64
BITS = "207fffff"
SHARE_LIMIT_TEXT = "b" + "f" * 63
SHARE_LIMIT = int(SHARE_LIMIT_TEXT, 16)
NETWORK_LIMIT = int("7fffff" + "0" * 58, 16)
WORK_PER_SHARE = 2
FINALITY = 2
WINDOW = 4
MAX_SHARES = 4096
MAX_ROUNDS = 64
DEFAULT_CORPUS = Path(__file__).resolve().parent / "vectors" / "sharechain_v0.json"

SHARE_KEYS = {
    "format",
    "profile",
    "chain",
    "sequence",
    "previous_share_id",
    "round_height",
    "round_previous_block_hash",
    "header_hex",
    "header_hash",
    "network_bits",
    "share_target_hex",
    "template_commitment_sha256",
    "payout_script_hex",
    "work_id_sha256",
    "block_candidate",
    "share_id_sha256",
}

REQUIRED_NAMES = {
    "valid_linear_chain",
    "longer_competing_fork",
    "equal_work_tie_break",
    "delayed_order_reconstruction",
    "restart_reconstruction",
    "unknown_parent",
    "miner_supplied_share_target",
    "fabricated_network_bits",
    "untrusted_round_context",
    "proof_above_share_target",
    "duplicate_share",
    "proof_reassigned_to_other_payout",
    "invalid_parent_sequence",
    "malformed_header",
    "stale_extension_after_block",
}


class Reject(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def encode(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")


def digest_object(value: Any) -> str:
    return hashlib.sha256(encode(value)).hexdigest()


def double_sha(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def hex_field(value: Any, size: int, code: str) -> str:
    if not isinstance(value, str) or len(value) != size * 2 or value != value.lower():
        raise Reject(code)
    try:
        bytes.fromhex(value)
    except ValueError as error:
        raise Reject(code) from error
    return value


def check_round_table(raw: Any) -> dict[tuple[int, str], str]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ROUNDS:
        raise Reject("invalid_round_table")
    table = {}
    fields = {"height", "previous_block_hash", "network_bits", "template_commitment_sha256"}
    for row in raw:
        if not isinstance(row, dict) or set(row) != fields:
            raise Reject("invalid_round_table")
        height = row["height"]
        if not isinstance(height, int) or isinstance(height, bool) or height < 0:
            raise Reject("invalid_round_table")
        previous = hex_field(row["previous_block_hash"], 32, "invalid_round_table")
        commitment = hex_field(row["template_commitment_sha256"], 32, "invalid_round_table")
        if row["network_bits"] != BITS or (height, previous) in table:
            raise Reject("invalid_round_table")
        table[(height, previous)] = commitment
    return table


def check_share(raw: Any, rounds: dict[tuple[int, str], str]) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != SHARE_KEYS:
        raise Reject("share_fields")
    if raw["format"] != SHARE_KIND or raw["profile"] != PROFILE or raw["chain"] != "labnet":
        raise Reject("share_profile")
    sequence = raw["sequence"]
    if not isinstance(sequence, int) or isinstance(sequence, bool) or not 0 <= sequence <= 0xFFFFFFFF:
        raise Reject("share_sequence")
    if not isinstance(raw["round_height"], int) or isinstance(raw["round_height"], bool):
        raise Reject("untrusted_round_context")
    hex_field(raw["previous_share_id"], 32, "share_identifier")
    previous_block = hex_field(raw["round_previous_block_hash"], 32, "untrusted_round_context")
    hex_field(raw["header_hash"], 32, "header_hash")
    template = hex_field(raw["template_commitment_sha256"], 32, "untrusted_round_context")
    hex_field(raw["work_id_sha256"], 32, "work_identity")
    hex_field(raw["share_id_sha256"], 32, "share_identifier")
    if raw["share_target_hex"] != SHARE_LIMIT_TEXT:
        raise Reject("share_target_mismatch")
    if raw["network_bits"] != BITS:
        raise Reject("network_bits_mismatch")
    if rounds.get((raw["round_height"], previous_block)) != template:
        raise Reject("untrusted_round_context")
    script = raw["payout_script_hex"]
    if not isinstance(script, str) or not 2 <= len(script) <= 20_000 or len(script) % 2 or script != script.lower():
        raise Reject("payout_script")
    try:
        bytes.fromhex(script)
    except ValueError as error:
        raise Reject("payout_script") from error
    if not isinstance(raw["block_candidate"], bool):
        raise Reject("block_candidate")
    header_text = raw["header_hex"]
    try:
        header = bytes.fromhex(header_text)
    except (TypeError, ValueError) as error:
        raise Reject("malformed_header") from error
    if len(header) != 80 or header_text != header_text.lower():
        raise Reject("malformed_header")
    if header[4:36][::-1].hex() != previous_block:
        raise Reject("untrusted_round_context")
    if f"{struct.unpack('<I', header[72:76])[0]:08x}" != BITS:
        raise Reject("network_bits_mismatch")
    header_digest = double_sha(header)
    if header_digest[::-1].hex() != raw["header_hash"]:
        raise Reject("header_hash")
    numeric_proof = int.from_bytes(header_digest, "little")
    if numeric_proof > SHARE_LIMIT:
        raise Reject("proof_above_share_target")
    if raw["block_candidate"] != (numeric_proof <= NETWORK_LIMIT):
        raise Reject("block_candidate")
    work_document = {
        "profile": PROFILE,
        "chain": "labnet",
        "round_height": raw["round_height"],
        "header_hex": header_text,
    }
    if digest_object(work_document) != raw["work_id_sha256"]:
        raise Reject("work_identity")
    share_body = {key: raw[key] for key in SHARE_KEYS if key != "share_id_sha256"}
    if digest_object(share_body) != raw["share_id_sha256"]:
        raise Reject("share_identifier")
    return raw


def select_state(raw_shares: Any, round_rows: Any) -> dict[str, Any]:
    rounds = check_round_table(round_rows)
    if not isinstance(raw_shares, list) or not 1 <= len(raw_shares) <= MAX_SHARES:
        raise Reject("empty_graph")
    shares_by_id = {}
    shares_by_work = {}
    for item in raw_shares:
        share = check_share(item, rounds)
        share_id = share["share_id_sha256"]
        work_id = share["work_id_sha256"]
        if share_id in shares_by_id:
            raise Reject("duplicate_share_id")
        if work_id in shares_by_work:
            if shares_by_work[work_id]["payout_script_hex"] != share["payout_script_hex"]:
                raise Reject("work_reassigned")
            raise Reject("duplicate_work_identity")
        shares_by_id[share_id] = share
        shares_by_work[work_id] = share
    roots = [item for item in raw_shares if item["previous_share_id"] == ZERO]
    if len(roots) != 1 or roots[0]["sequence"] != 0:
        raise Reject("invalid_root")
    accumulated = {}
    for share in sorted(raw_shares, key=lambda item: item["sequence"]):
        share_id = share["share_id_sha256"]
        parent_id = share["previous_share_id"]
        if parent_id == ZERO:
            accumulated[share_id] = WORK_PER_SHARE
            continue
        parent = shares_by_id.get(parent_id)
        if parent is None:
            raise Reject("unknown_parent")
        if share["sequence"] != parent["sequence"] + 1 or parent_id not in accumulated:
            raise Reject("parent_sequence")
        parent_round = (parent["round_height"], parent["round_previous_block_hash"])
        child_round = (share["round_height"], share["round_previous_block_hash"])
        if child_round == parent_round:
            if parent["block_candidate"]:
                raise Reject("round_transition")
        elif (
            not parent["block_candidate"]
            or share["round_height"] != parent["round_height"] + 1
            or share["round_previous_block_hash"] != parent["header_hash"]
        ):
            raise Reject("round_transition")
        accumulated[share_id] = accumulated[parent_id] + WORK_PER_SHARE
    referenced = {item["previous_share_id"] for item in raw_shares if item["previous_share_id"] != ZERO}
    tips = [share_id for share_id in shares_by_id if share_id not in referenced]
    winning_work = max(accumulated[item] for item in tips)
    winner = sorted(item for item in tips if accumulated[item] == winning_work)[0]
    chosen = []
    current = winner
    while current != ZERO:
        chosen.append(current)
        current = shares_by_id[current]["previous_share_id"]
    chosen.reverse()
    finalized = chosen[:-FINALITY] if len(chosen) > FINALITY else []
    payout_window = finalized[-WINDOW:]
    buckets = {}
    for share_id in payout_window:
        payout = shares_by_id[share_id]["payout_script_hex"]
        bucket = buckets.setdefault(payout, {"share_ids": [], "share_count": 0, "work_units": 0})
        bucket["share_ids"].append(share_id)
        bucket["share_count"] += 1
        bucket["work_units"] += WORK_PER_SHARE
    claims = [{"payout_script_hex": payout, **buckets[payout]} for payout in sorted(buckets)]
    return {
        "selected_tip_share_id": winner,
        "selected_cumulative_work": winning_work,
        "selected_path_share_ids": chosen,
        "finalized_share_ids": finalized,
        "payout_window_share_ids": payout_window,
        "payout_claims": claims,
    }


def outcome(scenario: dict[str, Any]) -> dict[str, Any]:
    try:
        return {"accepted": True, "state": select_state(scenario["shares"], scenario["trusted_rounds"])}
    except Reject as error:
        return {"accepted": False, "reason": error.code}


def verify_corpus(corpus: Any) -> list[dict[str, Any]]:
    top_keys = {"format", "profile", "chain", "constants", "scenarios", "limits", "corpus_commitment_sha256"}
    if not isinstance(corpus, dict) or set(corpus) != top_keys:
        raise Reject("corpus_fields")
    if corpus["format"] != CORPUS_KIND or corpus["profile"] != PROFILE or corpus["chain"] != "labnet":
        raise Reject("corpus_profile")
    constants = {
        "network_bits": BITS,
        "network_target_hex": f"{NETWORK_LIMIT:064x}",
        "share_target_hex": SHARE_LIMIT_TEXT,
        "share_work_units": WORK_PER_SHARE,
        "finality_depth": FINALITY,
        "payout_window": WINDOW,
        "max_shares": MAX_SHARES,
        "max_trusted_rounds": MAX_ROUNDS,
        "tie_break": "lowest_share_id_sha256",
    }
    if corpus["constants"] != constants:
        raise Reject("corpus_constants")
    expected_limits = [
        "offline_private_lab_profile_only",
        "no_peer_protocol_or_discovery",
        "no_sybil_or_eclipse_resistance",
        "no_production_settlement",
        "not_final_soveroot_pow",
    ]
    if corpus["limits"] != expected_limits:
        raise Reject("corpus_limits")
    unsigned_corpus = {key: corpus[key] for key in top_keys if key != "corpus_commitment_sha256"}
    if digest_object(unsigned_corpus) != corpus["corpus_commitment_sha256"]:
        raise Reject("corpus_commitment")
    scenarios = corpus["scenarios"]
    if (
        not isinstance(scenarios, list)
        or len(scenarios) != len(REQUIRED_NAMES)
        or {item.get("name") for item in scenarios if isinstance(item, dict)} != REQUIRED_NAMES
    ):
        raise Reject("scenario_set")
    report = []
    scenario_keys = {"name", "trusted_rounds", "shares", "expected", "scenario_commitment_sha256"}
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != scenario_keys:
            raise Reject("scenario_fields")
        unsigned = {key: scenario[key] for key in scenario_keys if key != "scenario_commitment_sha256"}
        if digest_object(unsigned) != scenario["scenario_commitment_sha256"]:
            raise Reject("scenario_commitment")
        actual = outcome(scenario)
        if actual != scenario["expected"]:
            raise Reject("scenario_expectation")
        report.append({"name": scenario["name"], **actual})
    return report


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", type=Path, default=DEFAULT_CORPUS, const=DEFAULT_CORPUS, nargs="?")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    corpus = json.loads(args.check.read_text(encoding="utf-8"))
    results = verify_corpus(corpus)
    report = {
        "format": "soveroot-sharechain-independent-report-v0",
        "profile": PROFILE,
        "corpus_commitment_sha256": corpus["corpus_commitment_sha256"],
        "all_scenarios_match": True,
        "scenario_results": results,
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Independent validator matched {len(results)} scenarios")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, Reject) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
