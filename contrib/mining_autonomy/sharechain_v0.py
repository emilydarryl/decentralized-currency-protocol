#!/usr/bin/env python3
"""Generate and validate the frozen Soveroot private-lab sharechain v0 corpus."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any, Sequence


PROFILE_ID = "soveroot-sharechain-labnet-v0"
CORPUS_FORMAT = "soveroot-sharechain-adversarial-v0"
SHARE_FORMAT = "soveroot-labnet-share-v0"
VECTOR_PATH = Path(__file__).resolve().parent / "vectors" / "sharechain_v0.json"
ZERO_ID = "00" * 32
NETWORK_BITS = "207fffff"
SHARE_TARGET_HEX = "bfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
SHARE_TARGET = int(SHARE_TARGET_HEX, 16)
FINALITY_DEPTH = 2
PAYOUT_WINDOW = 4
MAX_SHARES = 4096
MAX_TRUSTED_ROUNDS = 64

REQUIRED_SCENARIOS = {
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

PROFILE_LIMITS = [
    "offline_private_lab_profile_only",
    "no_peer_protocol_or_discovery",
    "no_sybil_or_eclipse_resistance",
    "no_production_settlement",
    "not_final_soveroot_pow",
]

SHARE_BODY_FIELDS = {
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
}


class ProfileError(RuntimeError):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=True).encode("ascii")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def hash256(value: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(value).digest()).digest()


def compact_target(bits: int) -> int:
    exponent = bits >> 24
    mantissa = bits & 0x007FFFFF
    if bits & 0x00800000 or mantissa == 0:
        raise ProfileError("invalid_network_bits", "network bits encode an invalid target")
    target = mantissa >> (8 * (3 - exponent)) if exponent <= 3 else mantissa << (8 * (exponent - 3))
    if not 0 < target < 1 << 256:
        raise ProfileError("invalid_network_bits", "network target is outside the uint256 range")
    return target


NETWORK_TARGET = compact_target(int(NETWORK_BITS, 16))
SHARE_WORK_UNITS = ((1 << 256) - 1) // (SHARE_TARGET + 1) + 1


def require_hex(value: Any, length: int, reason: str, label: str) -> str:
    if not isinstance(value, str) or len(value) != length * 2 or value != value.lower():
        raise ProfileError(reason, f"{label} must be canonical lowercase {length}-byte hex")
    try:
        bytes.fromhex(value)
    except ValueError as error:
        raise ProfileError(reason, f"{label} must be hexadecimal") from error
    return value


def trusted_rounds() -> list[dict[str, Any]]:
    first = {
        "height": 101,
        "previous_block_hash": "01" * 32,
        "network_bits": NETWORK_BITS,
        "template_commitment_sha256": "a1" * 32,
    }
    _, transition_digest = find_header(first, 3, "block")
    second = {
        "height": 102,
        "previous_block_hash": transition_digest[::-1].hex(),
        "network_bits": NETWORK_BITS,
        "template_commitment_sha256": "a2" * 32,
    }
    return [first, second]


def header_for(
    previous_block_hash: str,
    marker: int,
    timestamp: int,
    nonce: int,
    bits_hex: str = NETWORK_BITS,
) -> bytes:
    return (
        struct.pack("<I", 4)
        + bytes.fromhex(previous_block_hash)[::-1]
        + bytes([marker]) * 32
        + struct.pack("<I", timestamp)
        + struct.pack("<I", int(bits_hex, 16))
        + struct.pack("<I", nonce)
    )


def find_header(round_context: dict[str, Any], marker: int, mode: str) -> tuple[bytes, bytes]:
    for nonce in range(1_000_000):
        header = header_for(
            round_context["previous_block_hash"],
            marker,
            1_750_000_000 + marker,
            nonce,
        )
        digest = hash256(header)
        value = int.from_bytes(digest, "little")
        if mode == "block" and value <= NETWORK_TARGET:
            return header, digest
        if mode == "share" and NETWORK_TARGET < value <= SHARE_TARGET:
            return header, digest
        if mode == "invalid" and value > SHARE_TARGET:
            return header, digest
    raise RuntimeError(f"could not find deterministic {mode} header")


def work_identity(share: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": PROFILE_ID,
        "chain": "labnet",
        "round_height": share["round_height"],
        "header_hex": share["header_hex"],
    }


def share_body(share: dict[str, Any]) -> dict[str, Any]:
    return {key: share[key] for key in sorted(SHARE_BODY_FIELDS)}


def refresh_share_id(share: dict[str, Any], *, refresh_work: bool = False) -> dict[str, Any]:
    if refresh_work:
        share["work_id_sha256"] = canonical_hash(work_identity(share))
    share["share_id_sha256"] = canonical_hash(share_body(share))
    return share


def make_share(
    parent: dict[str, Any] | None,
    sequence: int,
    payout_script_hex: str,
    marker: int,
    *,
    round_index: int = 0,
    mode: str = "share",
) -> dict[str, Any]:
    context = trusted_rounds()[round_index]
    header, digest = find_header(context, marker, mode)
    share = {
        "format": SHARE_FORMAT,
        "profile": PROFILE_ID,
        "chain": "labnet",
        "sequence": sequence,
        "previous_share_id": ZERO_ID if parent is None else parent["share_id_sha256"],
        "round_height": context["height"],
        "round_previous_block_hash": context["previous_block_hash"],
        "header_hex": header.hex(),
        "header_hash": digest[::-1].hex(),
        "network_bits": NETWORK_BITS,
        "share_target_hex": SHARE_TARGET_HEX,
        "template_commitment_sha256": context["template_commitment_sha256"],
        "payout_script_hex": payout_script_hex,
        "work_id_sha256": "",
        "block_candidate": int.from_bytes(digest, "little") <= NETWORK_TARGET,
    }
    return refresh_share_id(share, refresh_work=True)


def validate_rounds(rounds: Any) -> dict[tuple[int, str], dict[str, Any]]:
    if not isinstance(rounds, list) or not 1 <= len(rounds) <= MAX_TRUSTED_ROUNDS:
        raise ProfileError("invalid_round_table", "trusted rounds must be a nonempty list")
    expected_fields = {"height", "previous_block_hash", "network_bits", "template_commitment_sha256"}
    result = {}
    for item in rounds:
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise ProfileError("invalid_round_table", "trusted round fields are not canonical")
        if not isinstance(item["height"], int) or isinstance(item["height"], bool) or item["height"] < 0:
            raise ProfileError("invalid_round_table", "trusted round height is invalid")
        require_hex(item["previous_block_hash"], 32, "invalid_round_table", "round previous block hash")
        require_hex(item["template_commitment_sha256"], 32, "invalid_round_table", "round template commitment")
        if item["network_bits"] != NETWORK_BITS:
            raise ProfileError("invalid_round_table", "trusted round changes the frozen network bits")
        key = (item["height"], item["previous_block_hash"])
        if key in result:
            raise ProfileError("invalid_round_table", "trusted round table contains a duplicate context")
        result[key] = item
    return result


def validate_share(share: Any, rounds: dict[tuple[int, str], dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(share, dict) or set(share) != SHARE_BODY_FIELDS | {"share_id_sha256"}:
        raise ProfileError("share_fields", "share contains missing or unknown fields")
    if share["format"] != SHARE_FORMAT or share["profile"] != PROFILE_ID or share["chain"] != "labnet":
        raise ProfileError("share_profile", "share uses the wrong format, profile, or chain")
    if (
        not isinstance(share["sequence"], int)
        or isinstance(share["sequence"], bool)
        or not 0 <= share["sequence"] <= 0xFFFFFFFF
    ):
        raise ProfileError("share_sequence", "share sequence must be a nonnegative integer")
    if not isinstance(share["round_height"], int) or isinstance(share["round_height"], bool):
        raise ProfileError("untrusted_round_context", "share round height is invalid")
    require_hex(share["previous_share_id"], 32, "share_identifier", "previous share id")
    require_hex(share["round_previous_block_hash"], 32, "untrusted_round_context", "round previous block hash")
    require_hex(share["header_hash"], 32, "header_hash", "header hash")
    require_hex(share["template_commitment_sha256"], 32, "untrusted_round_context", "template commitment")
    require_hex(share["work_id_sha256"], 32, "work_identity", "work id")
    require_hex(share["share_id_sha256"], 32, "share_identifier", "share id")
    if share["share_target_hex"] != SHARE_TARGET_HEX:
        raise ProfileError("share_target_mismatch", "share attempts to change the frozen profile target")
    if share["network_bits"] != NETWORK_BITS:
        raise ProfileError("network_bits_mismatch", "share attempts to change the trusted network bits")
    context = rounds.get((share["round_height"], share["round_previous_block_hash"]))
    if context is None or context["template_commitment_sha256"] != share["template_commitment_sha256"]:
        raise ProfileError("untrusted_round_context", "share is not bound to a trusted labnet round")
    script = share["payout_script_hex"]
    if not isinstance(script, str) or not 2 <= len(script) <= 20_000 or len(script) % 2:
        raise ProfileError("payout_script", "payout script must encode 1-10000 bytes")
    try:
        bytes.fromhex(script)
    except ValueError as error:
        raise ProfileError("payout_script", "payout script must be hexadecimal") from error
    if script != script.lower():
        raise ProfileError("payout_script", "payout script must use lowercase hexadecimal")
    if not isinstance(share["block_candidate"], bool):
        raise ProfileError("block_candidate", "block-candidate marker must be boolean")
    try:
        header = bytes.fromhex(share["header_hex"])
    except (TypeError, ValueError) as error:
        raise ProfileError("malformed_header", "header must be hexadecimal") from error
    if len(header) != 80 or share["header_hex"] != share["header_hex"].lower():
        raise ProfileError("malformed_header", "header must be canonical 80-byte lowercase hex")
    if header[4:36][::-1].hex() != share["round_previous_block_hash"]:
        raise ProfileError("untrusted_round_context", "header previous block does not match the trusted round")
    if f"{struct.unpack('<I', header[72:76])[0]:08x}" != NETWORK_BITS:
        raise ProfileError("network_bits_mismatch", "header does not use the trusted network bits")
    digest = hash256(header)
    if digest[::-1].hex() != share["header_hash"]:
        raise ProfileError("header_hash", "header hash does not match the submitted header")
    proof_value = int.from_bytes(digest, "little")
    if proof_value > SHARE_TARGET:
        raise ProfileError("proof_above_share_target", "header proof does not meet the frozen share target")
    if share["block_candidate"] != (proof_value <= NETWORK_TARGET):
        raise ProfileError("block_candidate", "block-candidate marker does not match the network target")
    if canonical_hash(work_identity(share)) != share["work_id_sha256"]:
        raise ProfileError("work_identity", "work identifier does not match the header proof")
    if canonical_hash(share_body(share)) != share["share_id_sha256"]:
        raise ProfileError("share_identifier", "share identifier does not match its canonical body")
    return share


def evaluate_graph(shares: Any, rounds_document: Any) -> dict[str, Any]:
    rounds = validate_rounds(rounds_document)
    if not isinstance(shares, list) or not 1 <= len(shares) <= MAX_SHARES:
        raise ProfileError("empty_graph", "share graph must be nonempty")
    by_id: dict[str, dict[str, Any]] = {}
    by_work: dict[str, dict[str, Any]] = {}
    for raw_share in shares:
        share = validate_share(raw_share, rounds)
        share_id = share["share_id_sha256"]
        work_id = share["work_id_sha256"]
        if share_id in by_id:
            raise ProfileError("duplicate_share_id", "share graph repeats one share identifier")
        if work_id in by_work:
            if by_work[work_id]["payout_script_hex"] != share["payout_script_hex"]:
                raise ProfileError("work_reassigned", "one proof is assigned to multiple payout scripts")
            raise ProfileError("duplicate_work_identity", "share graph counts one proof more than once")
        by_id[share_id] = share
        by_work[work_id] = share
    roots = [share for share in shares if share["previous_share_id"] == ZERO_ID]
    if len(roots) != 1 or roots[0]["sequence"] != 0:
        raise ProfileError("invalid_root", "share graph must contain exactly one sequence-zero root")
    cumulative: dict[str, int] = {}
    for share in sorted(shares, key=lambda item: item["sequence"]):
        share_id = share["share_id_sha256"]
        parent_id = share["previous_share_id"]
        if parent_id == ZERO_ID:
            cumulative[share_id] = SHARE_WORK_UNITS
            continue
        parent = by_id.get(parent_id)
        if parent is None:
            raise ProfileError("unknown_parent", "share references an unavailable parent")
        if share["sequence"] != parent["sequence"] + 1:
            raise ProfileError("parent_sequence", "share sequence does not immediately follow its parent")
        if parent_id not in cumulative:
            raise ProfileError("parent_sequence", "parent must precede its child by sequence")
        parent_round = (parent["round_height"], parent["round_previous_block_hash"])
        child_round = (share["round_height"], share["round_previous_block_hash"])
        if child_round == parent_round:
            if parent["block_candidate"]:
                raise ProfileError("round_transition", "a block-candidate share cannot be extended on its stale round")
        elif (
            not parent["block_candidate"]
            or share["round_height"] != parent["round_height"] + 1
            or share["round_previous_block_hash"] != parent["header_hash"]
        ):
            raise ProfileError("round_transition", "share changes round without extending its parent block")
        cumulative[share_id] = cumulative[parent_id] + SHARE_WORK_UNITS
    parent_ids = {share["previous_share_id"] for share in shares if share["previous_share_id"] != ZERO_ID}
    tips = [share_id for share_id in by_id if share_id not in parent_ids]
    best_work = max(cumulative[share_id] for share_id in tips)
    selected_tip = min(share_id for share_id in tips if cumulative[share_id] == best_work)
    path = []
    cursor = selected_tip
    while cursor != ZERO_ID:
        path.append(cursor)
        cursor = by_id[cursor]["previous_share_id"]
    path.reverse()
    finalized = path[:-FINALITY_DEPTH] if len(path) > FINALITY_DEPTH else []
    payout_ids = finalized[-PAYOUT_WINDOW:]
    grouped: dict[str, dict[str, Any]] = {}
    for share_id in payout_ids:
        script = by_id[share_id]["payout_script_hex"]
        group = grouped.setdefault(script, {"share_ids": [], "share_count": 0, "work_units": 0})
        group["share_ids"].append(share_id)
        group["share_count"] += 1
        group["work_units"] += SHARE_WORK_UNITS
    claims = [
        {"payout_script_hex": script, **grouped[script]}
        for script in sorted(grouped)
    ]
    return {
        "selected_tip_share_id": selected_tip,
        "selected_cumulative_work": best_work,
        "selected_path_share_ids": path,
        "finalized_share_ids": finalized,
        "payout_window_share_ids": payout_ids,
        "payout_claims": claims,
    }


def assess(shares: Any, rounds: Any) -> dict[str, Any]:
    try:
        return {"accepted": True, "state": evaluate_graph(shares, rounds)}
    except ProfileError as error:
        return {"accepted": False, "reason": error.reason}


def make_scenario(
    name: str,
    shares: list[dict[str, Any]],
    *,
    expected_reason: str | None = None,
) -> dict[str, Any]:
    rounds = trusted_rounds()
    result = assess(shares, rounds)
    if expected_reason is None:
        if result.get("accepted") is not True:
            raise RuntimeError(f"accepted scenario {name} failed: {result}")
    elif result != {"accepted": False, "reason": expected_reason}:
        raise RuntimeError(f"rejected scenario {name} produced {result}")
    body = {"name": name, "trusted_rounds": rounds, "shares": shares, "expected": result}
    return {**body, "scenario_commitment_sha256": canonical_hash(body)}


def linear_shares() -> list[dict[str, Any]]:
    root = make_share(None, 0, "51", 1)
    one = make_share(root, 1, "52", 2)
    two = make_share(one, 2, "51", 3, mode="block")
    three = make_share(two, 3, "52", 4, round_index=1)
    four = make_share(three, 4, "51", 5, round_index=1)
    return [root, one, two, three, four]


def build_scenarios() -> list[dict[str, Any]]:
    scenarios = []
    linear = linear_shares()
    scenarios.append(make_scenario("valid_linear_chain", copy.deepcopy(linear)))

    root = make_share(None, 0, "51", 10)
    a1 = make_share(root, 1, "51", 11)
    a2 = make_share(a1, 2, "51", 12)
    b1 = make_share(root, 1, "52", 13)
    b2 = make_share(b1, 2, "52", 14)
    b3 = make_share(b2, 3, "52", 15)
    scenarios.append(make_scenario("longer_competing_fork", [root, a1, a2, b1, b2, b3]))

    tie_root = make_share(None, 0, "51", 20)
    tie_a = make_share(tie_root, 1, "51", 21)
    tie_b = make_share(tie_root, 1, "52", 22)
    scenarios.append(make_scenario("equal_work_tie_break", [tie_root, tie_a, tie_b]))
    scenarios.append(make_scenario("delayed_order_reconstruction", list(reversed(copy.deepcopy(linear)))))
    scenarios.append(make_scenario("restart_reconstruction", [linear[2], linear[4], linear[0], linear[3], linear[1]]))

    unknown = copy.deepcopy(linear[:2])
    unknown[1]["previous_share_id"] = "ee" * 32
    refresh_share_id(unknown[1])
    scenarios.append(make_scenario("unknown_parent", unknown, expected_reason="unknown_parent"))

    target_change = copy.deepcopy(linear[:2])
    target_change[1]["share_target_hex"] = "ff" * 32
    refresh_share_id(target_change[1])
    scenarios.append(make_scenario("miner_supplied_share_target", target_change, expected_reason="share_target_mismatch"))

    bits_change = copy.deepcopy(linear[:2])
    bits_change[1]["network_bits"] = "1d00ffff"
    refresh_share_id(bits_change[1])
    scenarios.append(make_scenario("fabricated_network_bits", bits_change, expected_reason="network_bits_mismatch"))

    untrusted = copy.deepcopy(linear[:2])
    untrusted[1]["template_commitment_sha256"] = "ff" * 32
    refresh_share_id(untrusted[1])
    scenarios.append(make_scenario("untrusted_round_context", untrusted, expected_reason="untrusted_round_context"))

    invalid_root = make_share(None, 0, "51", 30, mode="invalid")
    scenarios.append(make_scenario("proof_above_share_target", [invalid_root], expected_reason="proof_above_share_target"))

    scenarios.append(make_scenario("duplicate_share", [linear[0], linear[1], copy.deepcopy(linear[1])], expected_reason="duplicate_share_id"))

    reassigned = copy.deepcopy(linear[1])
    reassigned["payout_script_hex"] = "53"
    refresh_share_id(reassigned)
    scenarios.append(make_scenario("proof_reassigned_to_other_payout", [linear[0], linear[1], reassigned], expected_reason="work_reassigned"))

    bad_sequence = copy.deepcopy(linear[:2])
    bad_sequence[1]["sequence"] = 3
    refresh_share_id(bad_sequence[1])
    scenarios.append(make_scenario("invalid_parent_sequence", bad_sequence, expected_reason="parent_sequence"))

    malformed = copy.deepcopy(linear[:1])
    malformed[0]["header_hex"] = "00"
    refresh_share_id(malformed[0], refresh_work=True)
    scenarios.append(make_scenario("malformed_header", malformed, expected_reason="malformed_header"))

    stale = copy.deepcopy(linear[:3])
    stale_child = make_share(stale[2], 3, "52", 40, round_index=0)
    stale.append(stale_child)
    scenarios.append(make_scenario("stale_extension_after_block", stale, expected_reason="round_transition"))
    return scenarios


def profile_constants() -> dict[str, Any]:
    return {
        "network_bits": NETWORK_BITS,
        "network_target_hex": f"{NETWORK_TARGET:064x}",
        "share_target_hex": SHARE_TARGET_HEX,
        "share_work_units": SHARE_WORK_UNITS,
        "finality_depth": FINALITY_DEPTH,
        "payout_window": PAYOUT_WINDOW,
        "max_shares": MAX_SHARES,
        "max_trusted_rounds": MAX_TRUSTED_ROUNDS,
        "tie_break": "lowest_share_id_sha256",
    }


def build_corpus() -> dict[str, Any]:
    body = {
        "format": CORPUS_FORMAT,
        "profile": PROFILE_ID,
        "chain": "labnet",
        "constants": profile_constants(),
        "scenarios": build_scenarios(),
        "limits": PROFILE_LIMITS,
    }
    return {**body, "corpus_commitment_sha256": canonical_hash(body)}


def validate_scenario(scenario: Any) -> dict[str, Any]:
    required = {"name", "trusted_rounds", "shares", "expected", "scenario_commitment_sha256"}
    if not isinstance(scenario, dict) or set(scenario) != required:
        raise ProfileError("scenario_fields", "scenario contains missing or unknown fields")
    body = {key: scenario[key] for key in required if key != "scenario_commitment_sha256"}
    if scenario["scenario_commitment_sha256"] != canonical_hash(body):
        raise ProfileError("scenario_commitment", "scenario commitment is inconsistent")
    actual = assess(scenario["shares"], scenario["trusted_rounds"])
    if actual != scenario["expected"]:
        raise ProfileError("scenario_expectation", f"scenario {scenario['name']} produced {actual}")
    return actual


def validate_corpus(corpus: Any) -> list[dict[str, Any]]:
    required = {"format", "profile", "chain", "constants", "scenarios", "limits", "corpus_commitment_sha256"}
    if not isinstance(corpus, dict) or set(corpus) != required:
        raise ProfileError("corpus_fields", "corpus contains missing or unknown fields")
    if corpus["format"] != CORPUS_FORMAT or corpus["profile"] != PROFILE_ID or corpus["chain"] != "labnet":
        raise ProfileError("corpus_profile", "corpus has the wrong profile boundary")
    if corpus["constants"] != profile_constants():
        raise ProfileError("corpus_constants", "corpus changes frozen profile constants")
    if corpus["limits"] != PROFILE_LIMITS:
        raise ProfileError("corpus_limits", "corpus changes the frozen safety limits")
    body = {key: corpus[key] for key in required if key != "corpus_commitment_sha256"}
    if corpus["corpus_commitment_sha256"] != canonical_hash(body):
        raise ProfileError("corpus_commitment", "corpus commitment is inconsistent")
    scenarios = corpus["scenarios"]
    if (
        not isinstance(scenarios, list)
        or len(scenarios) != len(REQUIRED_SCENARIOS)
        or {item.get("name") for item in scenarios if isinstance(item, dict)} != REQUIRED_SCENARIOS
    ):
        raise ProfileError("scenario_set", "corpus does not contain the exact required scenario set")
    return [{"name": item["name"], **validate_scenario(item)} for item in scenarios]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the canonical vector corpus")
    mode.add_argument("--check", action="store_true", help="validate the checked-in vector corpus")
    parser.add_argument("--path", type=Path, default=VECTOR_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.write:
        corpus = build_corpus()
        validate_corpus(corpus)
        args.path.parent.mkdir(parents=True, exist_ok=True)
        args.path.write_text(json.dumps(corpus, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote {len(corpus['scenarios'])} sharechain scenarios to {args.path}")
        return 0
    corpus = json.loads(args.path.read_text(encoding="utf-8"))
    results = validate_corpus(corpus)
    print(f"Validated {len(results)} sharechain scenarios from {args.path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ProfileError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
