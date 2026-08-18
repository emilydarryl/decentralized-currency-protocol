#!/usr/bin/env python3
"""Generate and validate Soveroot's semantic SV2/JD labnet vectors.

The vectors deliberately stop at the authenticated protocol/state boundary.
They are not Noise ciphertext test vectors and they do not implement a pool.
Their purpose is to freeze behavior before the reference network path exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence


PROFILE_ID = "soveroot-sv2-jd-labnet-v0"
UPSTREAM_REVISION = "066971c7c750eded11b57aecd4ecdbd6e722c631"
VECTOR_FORMAT = "soveroot-sv2-jd-semantic-v0"
VECTOR_PATH = Path(__file__).resolve().parent / "vectors" / "sv2_job_declaration_profile_v0.json"

AUTHORITY_PUBLIC_KEY = "11" * 32
CERTIFICATE_SHA256 = "22" * 32
TOKEN = "a0" * 32
JOB_ID = "labnet-job-0001"

SCENARIO_FAILURE_EVENTS = {
    "rejected_custom_job": "declare_mining_job_error",
    "token_timeout": "token_timeout",
    "disconnect_after_declaration": "disconnect",
    "protocol_downgrade": "setup_connection_error",
    "malformed_reply": "malformed_reply",
    "coordinator_equivocation": "equivocation_detected",
    "replayed_acceptance": "replay_detected",
    "mitm_authentication_failure": "noise_authentication_failed",
}

REQUIRED_SCENARIOS = {"accepted_custom_job", *SCENARIO_FAILURE_EVENTS}
COORDINATOR_DIRECTIONS = {"miner_to_coordinator", "coordinator_to_miner"}


class VectorError(RuntimeError):
    """Raised when a profile vector violates a frozen invariant."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def template() -> dict[str, Any]:
    candidate = {
        "chain": "labnet",
        "height": 101,
        "previous_block_hash": "01" * 32,
        "version": 4,
        "bits": "207fffff",
        "curtime": 1_750_000_000,
        "coinbase_value": 5_000_000_000,
        "payout_script_hex": "51",
        "coinbase_prefix_hex": "0200000001",
        "coinbase_suffix_hex": "ffffffff",
        "ordered_txids": [],
        "transaction_data_hex": [],
        "witness_commitment_hex": "6a24aa21a9ed" + "00" * 32,
    }
    candidate["template_commitment_sha256"] = sha256_hex(candidate)
    return candidate


def event(direction: str, event_type: str, **fields: Any) -> dict[str, Any]:
    return {"direction": direction, "type": event_type, **fields}


def authenticated_prefix() -> list[dict[str, Any]]:
    return [
        event(
            "coordinator_to_miner",
            "noise_server_authenticated",
            pattern="Noise_NX_Secp256k1+EllSwift_ChaChaPoly_SHA256",
            authority_public_key=AUTHORITY_PUBLIC_KEY,
            certificate_sha256=CERTIFICATE_SHA256,
        ),
        event(
            "miner_to_coordinator",
            "setup_connection",
            upstream_message_type="0x00",
            protocol=1,
            min_version=2,
            max_version=2,
            flags=1,
            vendor="Soveroot",
            firmware=PROFILE_ID,
        ),
        event(
            "coordinator_to_miner",
            "setup_connection_success",
            upstream_message_type="0x01",
            used_version=2,
            flags=0,
        ),
    ]


def token_exchange() -> list[dict[str, Any]]:
    return [
        event(
            "miner_to_coordinator",
            "allocate_mining_job_token",
            upstream_message_type="0x50",
            request_id=7,
            user_identifier="labnet-miner-a",
        ),
        event(
            "coordinator_to_miner",
            "allocate_mining_job_token_success",
            upstream_message_type="0x51",
            request_id=7,
            mining_job_token=TOKEN,
            coinbase_output_max_additional_size=0,
        ),
    ]


def declaration() -> dict[str, Any]:
    return event(
        "miner_to_coordinator",
        "declare_mining_job",
        upstream_message_type="0x57",
        request_id=8,
        mining_job_token=TOKEN,
        job_id=JOB_ID,
        template_commitment_sha256=template()["template_commitment_sha256"],
        version=4,
        coinbase_prefix_hex="0200000001",
        coinbase_suffix_hex="ffffffff",
        tx_short_hash_list=[],
        excess_data_hex="",
    )


def direct_tail(*, fallback_reason: str | None = None) -> list[dict[str, Any]]:
    commitment = template()["template_commitment_sha256"]
    result: list[dict[str, Any]] = []
    if fallback_reason is not None:
        result.append(
            event(
                "local",
                "direct_fallback",
                reason=fallback_reason,
                job_id=JOB_ID,
                template_commitment_sha256=commitment,
            )
        )
    result.extend(
        [
            event(
                "local",
                "solve_miner_created_template",
                job_id=JOB_ID,
                template_commitment_sha256=commitment,
            ),
            event(
                "miner_to_node",
                "direct_publish",
                rpc="submitblock",
                chain="labnet",
                job_id=JOB_ID,
                template_commitment_sha256=commitment,
            ),
        ]
    )
    return result


def number_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"seq": index, **item} for index, item in enumerate(events, start=1)]


def scenario(name: str, events: list[dict[str, Any]], expected_result: str) -> dict[str, Any]:
    value = {
        "name": name,
        "profile_id": PROFILE_ID,
        "chain": "labnet",
        "upstream_revision": UPSTREAM_REVISION,
        "expected_result": expected_result,
        "miner_created_template": template(),
        "events": number_events(
            [
                event(
                    "local",
                    "miner_created_template",
                    job_id=JOB_ID,
                    template_commitment_sha256=template()["template_commitment_sha256"],
                ),
                *events,
            ]
        ),
    }
    value["transcript_sha256"] = sha256_hex(value)
    return value


def build_scenarios() -> list[dict[str, Any]]:
    accepted = scenario(
        "accepted_custom_job",
        [
            *authenticated_prefix(),
            *token_exchange(),
            declaration(),
            event(
                "coordinator_to_miner",
                "declare_mining_job_success",
                upstream_message_type="0x58",
                request_id=8,
                new_mining_job_token=TOKEN,
            ),
            event(
                "miner_to_coordinator",
                "open_extended_mining_channel",
                upstream_message_type="0x13",
                request_id=9,
                user_identity="labnet-miner-a",
            ),
            event(
                "coordinator_to_miner",
                "open_extended_mining_channel_success",
                upstream_message_type="0x14",
                request_id=9,
                channel_id=1,
            ),
            event(
                "miner_to_coordinator",
                "set_custom_mining_job",
                upstream_message_type="0x22",
                channel_id=1,
                request_id=10,
                mining_job_token=TOKEN,
                job_id=JOB_ID,
                template_commitment_sha256=template()["template_commitment_sha256"],
            ),
            event(
                "coordinator_to_miner",
                "set_custom_mining_job_success",
                upstream_message_type="0x23",
                channel_id=1,
                request_id=10,
                job_id=JOB_ID,
            ),
            *direct_tail(),
        ],
        "coordinator_accepted_direct_publication",
    )

    rejected = scenario(
        "rejected_custom_job",
        [
            *authenticated_prefix(),
            *token_exchange(),
            declaration(),
            event(
                "coordinator_to_miner",
                "declare_mining_job_error",
                upstream_message_type="0x59",
                request_id=8,
                error_code="invalid-job-declaration",
                error_details="fixture-rejection",
            ),
            *direct_tail(fallback_reason="coordinator_rejected_custom_job"),
        ],
        "direct_fallback_publication",
    )

    timeout = scenario(
        "token_timeout",
        [
            *authenticated_prefix(),
            token_exchange()[0],
            event("local", "token_timeout", request_id=7, timeout_ms=2_000),
            *direct_tail(fallback_reason="coordinator_token_timeout"),
        ],
        "direct_fallback_publication",
    )

    disconnected = scenario(
        "disconnect_after_declaration",
        [
            *authenticated_prefix(),
            *token_exchange(),
            declaration(),
            event("network_to_miner", "disconnect", phase="awaiting_declaration_reply"),
            *direct_tail(fallback_reason="coordinator_disconnected"),
        ],
        "direct_fallback_publication",
    )

    downgrade = scenario(
        "protocol_downgrade",
        [
            authenticated_prefix()[0],
            authenticated_prefix()[1],
            event(
                "coordinator_to_miner",
                "setup_connection_error",
                upstream_message_type="0x02",
                flags=0,
                error_code="unsupported-protocol",
                offered_version=1,
            ),
            *direct_tail(fallback_reason="protocol_downgrade_refused"),
        ],
        "direct_fallback_publication",
    )

    malformed = scenario(
        "malformed_reply",
        [
            *authenticated_prefix(),
            token_exchange()[0],
            event(
                "coordinator_to_miner",
                "malformed_reply",
                claimed_message_type="0x51",
                reason="token_length_is_31_not_32",
            ),
            *direct_tail(fallback_reason="malformed_coordinator_reply"),
        ],
        "direct_fallback_publication",
    )

    equivocation = scenario(
        "coordinator_equivocation",
        [
            *authenticated_prefix(),
            *token_exchange(),
            declaration(),
            event(
                "coordinator_to_miner",
                "declare_mining_job_success",
                upstream_message_type="0x58",
                request_id=8,
                new_mining_job_token=TOKEN,
            ),
            event(
                "local",
                "equivocation_detected",
                request_id=8,
                first_job_id=JOB_ID,
                conflicting_job_id="labnet-job-conflict",
            ),
            *direct_tail(fallback_reason="coordinator_equivocation"),
        ],
        "direct_fallback_publication",
    )

    replay = scenario(
        "replayed_acceptance",
        [
            *authenticated_prefix(),
            *token_exchange(),
            declaration(),
            event(
                "coordinator_to_miner",
                "replay_detected",
                replayed_message_type="0x58",
                request_id=6,
                active_request_id=8,
            ),
            *direct_tail(fallback_reason="replayed_coordinator_message"),
        ],
        "direct_fallback_publication",
    )

    mitm = scenario(
        "mitm_authentication_failure",
        [
            event(
                "network_to_miner",
                "noise_authentication_failed",
                expected_authority_public_key=AUTHORITY_PUBLIC_KEY,
                observed_certificate_sha256="33" * 32,
            ),
            *direct_tail(fallback_reason="coordinator_authentication_failed"),
        ],
        "direct_fallback_publication",
    )

    return [accepted, rejected, timeout, disconnected, downgrade, malformed, equivocation, replay, mitm]


def build_corpus() -> dict[str, Any]:
    return {
        "format": VECTOR_FORMAT,
        "profile_id": PROFILE_ID,
        "upstream": {
            "repository": "https://github.com/stratum-mining/sv2-spec",
            "revision": UPSTREAM_REVISION,
        },
        "warning": "PRIVATE LABNET ONLY; NOT NOISE WIRE VECTORS; NOT SAFE FOR MONETARY USE",
        "scenarios": build_scenarios(),
    }


def require_subsequence(types: list[str], expected: list[str], name: str) -> None:
    position = 0
    for value in types:
        if position < len(expected) and value == expected[position]:
            position += 1
    if position != len(expected):
        raise VectorError(f"{name}: missing ordered event subsequence: {expected}")


def validate_template(candidate: Any, name: str) -> None:
    if not isinstance(candidate, dict):
        raise VectorError(f"{name}: template must be an object")
    commitment = candidate.get("template_commitment_sha256")
    unsigned = {key: value for key, value in candidate.items() if key != "template_commitment_sha256"}
    if commitment != sha256_hex(unsigned):
        raise VectorError(f"{name}: template commitment does not match canonical fields")
    if candidate.get("chain") != "labnet":
        raise VectorError(f"{name}: template must be chain=labnet")
    if len(str(candidate.get("previous_block_hash", ""))) != 64:
        raise VectorError(f"{name}: previous block hash must be 32 bytes")
    if candidate.get("bits") != "207fffff":
        raise VectorError(f"{name}: vectors must use the inherited easy labnet target")
    for field in ("payout_script_hex", "coinbase_prefix_hex", "coinbase_suffix_hex"):
        try:
            bytes.fromhex(candidate[field])
        except (KeyError, TypeError, ValueError) as error:
            raise VectorError(f"{name}: {field} must be canonical hex") from error


def validate_scenario(value: Any) -> None:
    if not isinstance(value, dict):
        raise VectorError("scenario must be an object")
    name = value.get("name")
    if name not in REQUIRED_SCENARIOS:
        raise VectorError(f"unknown scenario: {name}")
    if value.get("profile_id") != PROFILE_ID or value.get("upstream_revision") != UPSTREAM_REVISION:
        raise VectorError(f"{name}: profile or upstream revision changed")
    if value.get("chain") != "labnet":
        raise VectorError(f"{name}: scenario must fail closed to chain=labnet")

    transcript_hash = value.get("transcript_sha256")
    unsigned = {key: item for key, item in value.items() if key != "transcript_sha256"}
    if transcript_hash != sha256_hex(unsigned):
        raise VectorError(f"{name}: transcript hash mismatch")

    validate_template(value.get("miner_created_template"), str(name))
    commitment = value["miner_created_template"]["template_commitment_sha256"]
    events = value.get("events")
    if not isinstance(events, list) or not events:
        raise VectorError(f"{name}: events must be a nonempty list")
    if [item.get("seq") for item in events] != list(range(1, len(events) + 1)):
        raise VectorError(f"{name}: sequence numbers must be contiguous")
    types = [str(item.get("type")) for item in events]
    if types[0] != "miner_created_template" or types[-1] != "direct_publish":
        raise VectorError(f"{name}: miner creation must be first and direct publication last")
    if any(item.get("type") == "coordinator_created_template" for item in events):
        raise VectorError(f"{name}: coordinator-created templates are forbidden")

    publication = events[-1]
    if publication.get("chain") != "labnet" or publication.get("rpc") != "submitblock":
        raise VectorError(f"{name}: final publication must be direct labnet submitblock")
    if publication.get("job_id") != JOB_ID or publication.get("template_commitment_sha256") != commitment:
        raise VectorError(f"{name}: publication changed the miner-created template")

    if name == "accepted_custom_job":
        if value.get("expected_result") != "coordinator_accepted_direct_publication":
            raise VectorError(f"{name}: accepted result changed")
        require_subsequence(
            types,
            [
                "noise_server_authenticated",
                "setup_connection",
                "setup_connection_success",
                "allocate_mining_job_token",
                "allocate_mining_job_token_success",
                "declare_mining_job",
                "declare_mining_job_success",
                "open_extended_mining_channel",
                "open_extended_mining_channel_success",
                "set_custom_mining_job",
                "set_custom_mining_job_success",
                "solve_miner_created_template",
                "direct_publish",
            ],
            name,
        )
        if "direct_fallback" in types:
            raise VectorError(f"{name}: accepted path must not report fallback")
    else:
        failure_type = SCENARIO_FAILURE_EVENTS[name]
        if value.get("expected_result") != "direct_fallback_publication":
            raise VectorError(f"{name}: failure result changed")
        require_subsequence(types, [failure_type, "direct_fallback", "solve_miner_created_template", "direct_publish"], name)

    if "noise_authentication_failed" in types:
        failure_index = types.index("noise_authentication_failed")
        if any(item.get("direction") in COORDINATOR_DIRECTIONS for item in events[failure_index + 1 :]):
            raise VectorError(f"{name}: coordinator traffic continued after failed authentication")
    elif "noise_server_authenticated" not in types:
        raise VectorError(f"{name}: coordinator traffic lacks authenticated Noise setup")


def validate_corpus(value: Any) -> None:
    if not isinstance(value, dict) or value.get("format") != VECTOR_FORMAT:
        raise VectorError("vector corpus format changed")
    if value.get("profile_id") != PROFILE_ID:
        raise VectorError("vector corpus profile changed")
    upstream = value.get("upstream")
    if not isinstance(upstream, dict) or upstream.get("revision") != UPSTREAM_REVISION:
        raise VectorError("upstream specification revision changed")
    scenarios = value.get("scenarios")
    if not isinstance(scenarios, list):
        raise VectorError("scenarios must be a list")
    names = [item.get("name") if isinstance(item, dict) else None for item in scenarios]
    if len(names) != len(set(names)) or set(names) != REQUIRED_SCENARIOS:
        raise VectorError("scenario corpus must contain every required scenario exactly once")
    for item in scenarios:
        validate_scenario(item)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate or check Soveroot SV2/JD labnet vectors.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the canonical vector corpus")
    mode.add_argument("--check", action="store_true", help="validate the checked-in vector corpus")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(list(argv) if argv is not None else __import__("sys").argv[1:])
    expected = build_corpus()
    validate_corpus(expected)
    if args.write:
        VECTOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        VECTOR_PATH.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote {VECTOR_PATH}")
        return 0
    if not VECTOR_PATH.is_file():
        raise VectorError(f"missing checked-in vector corpus: {VECTOR_PATH}")
    actual = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    validate_corpus(actual)
    if actual != expected:
        raise VectorError("checked-in corpus is valid but does not match the generator")
    print(f"Validated {len(actual['scenarios'])} scenarios from {VECTOR_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
