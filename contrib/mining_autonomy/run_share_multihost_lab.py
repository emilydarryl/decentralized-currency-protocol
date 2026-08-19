#!/usr/bin/env python3
"""Run deterministic multi-address safety and share-sync adversarial evidence."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence

import run_share_sync_lab as legacy
import sharechain_multihost_v1 as safety


FORMAT = "soveroot-share-sync-multihost-evidence-v1"
IDENTITY_SEEDS = {
    "alpha": "01" * 32,
    "bravo": "02" * 32,
    "charlie": "03" * 32,
}
HOSTS = {
    "alpha": "127.20.1.1",
    "bravo": "127.21.1.1",
    "charlie": "127.22.1.1",
}
OPERATORS = {"alpha": "operator-a", "bravo": "operator-b", "charlie": "operator-c"}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rejects(reason: str, action: Callable[[], Any]) -> bool:
    try:
        action()
    except safety.SafetyError as error:
        return error.reason == reason
    return False


def session_material() -> tuple[dict[frozenset[str], str], dict[str, Any]]:
    pair_keys: dict[frozenset[str], str] = {}
    reports: dict[str, Any] = {}
    for left, right in (("alpha", "bravo"), ("alpha", "charlie"), ("bravo", "charlie")):
        left_ephemeral = safety.ephemeral_private(f"{left}->{right}".encode("ascii"))
        right_ephemeral = safety.ephemeral_private(f"{right}->{left}".encode("ascii"))
        left_hello = safety.make_hello(
            peer_id=left,
            identity_seed_hex=IDENTITY_SEEDS[left],
            operator_group=OPERATORS[left],
            transport="tcp-lab",
            endpoint=HOSTS[left],
            role="initiator",
            ephemeral_private_key=left_ephemeral,
            nonce_hex=safety.canonical_hash({"nonce": left, "peer": right}),
            issued_tick=0,
        )
        right_hello = safety.make_hello(
            peer_id=right,
            identity_seed_hex=IDENTITY_SEEDS[right],
            operator_group=OPERATORS[right],
            transport="tcp-lab",
            endpoint=HOSTS[right],
            role="responder",
            ephemeral_private_key=right_ephemeral,
            nonce_hex=safety.canonical_hash({"nonce": right, "peer": left}),
            issued_tick=0,
        )
        safety.verify_hello(
            left_hello,
            expected_peer_id=left,
            expected_public_key_hex=safety.identity_public_key(IDENTITY_SEEDS[left]),
            expected_role="initiator",
            expected_operator_group=OPERATORS[left],
            expected_transport="tcp-lab",
            expected_endpoint=HOSTS[left],
            current_tick=1,
        )
        safety.verify_hello(
            right_hello,
            expected_peer_id=right,
            expected_public_key_hex=safety.identity_public_key(IDENTITY_SEEDS[right]),
            expected_role="responder",
            expected_operator_group=OPERATORS[right],
            expected_transport="tcp-lab",
            expected_endpoint=HOSTS[right],
            current_tick=1,
        )
        left_key, left_transcript = safety.derive_session_key(
            local_ephemeral_private=left_ephemeral,
            initiator_hello=left_hello,
            responder_hello=right_hello,
        )
        right_key, right_transcript = safety.derive_session_key(
            local_ephemeral_private=right_ephemeral,
            initiator_hello=left_hello,
            responder_hello=right_hello,
        )
        if left_key != right_key or left_transcript != right_transcript:
            raise RuntimeError("session endpoints derived different keys or transcript commitments")
        pair_keys[frozenset((left, right))] = left_key
        reports[f"{left}-{right}"] = {
            "initiator_hello": left_hello,
            "responder_hello": right_hello,
            "transcript_sha256": left_transcript,
            "session_key_commitment_sha256": safety.canonical_hash({"session_key_hex": left_key}),
        }
    return pair_keys, reports


def admission_checks(checks: dict[str, bool], observations: dict[str, Any]) -> None:
    identity_limit = safety.AdmissionController()
    identity_limit.admit_handshake(peer_id="peer-a", source_ip="10.1.0.1", nonce_hex="01" * 32, tick=0)
    identity_limit.admit_handshake(peer_id="peer-a", source_ip="10.1.0.2", nonce_hex="02" * 32, tick=0)
    checks["identity_session_limit_exact_plus_one"] = rejects(
        "identity_session_limit",
        lambda: identity_limit.admit_handshake(
            peer_id="peer-a", source_ip="10.1.0.3", nonce_hex="03" * 32, tick=0
        ),
    )

    prefix_limit = safety.AdmissionController()
    for index in range(safety.MAX_SESSIONS_PER_SOURCE_PREFIX):
        prefix_limit.admit_handshake(
            peer_id=f"prefix-{index}",
            source_ip=f"10.2.0.{index + 1}",
            nonce_hex=f"{index + 10:064x}",
            tick=0,
        )
    checks["source_prefix_session_limit_exact_plus_one"] = rejects(
        "prefix_session_limit",
        lambda: prefix_limit.admit_handshake(
            peer_id="prefix-over", source_ip="10.2.0.99", nonce_hex="ff" * 32, tick=0
        ),
    )

    handshake_rate = safety.AdmissionController()
    for index in range(safety.HANDSHAKE_BUCKET_CAPACITY):
        peer_id = f"rate-{index}"
        address = f"10.3.0.{index + 1}"
        handshake_rate.admit_handshake(
            peer_id=peer_id, source_ip=address, nonce_hex=f"{index + 100:064x}", tick=0
        )
        handshake_rate.close_session(peer_id=peer_id, source_ip=address)
    checks["source_prefix_handshake_bucket_exact_plus_one"] = rejects(
        "prefix_handshake_rate",
        lambda: handshake_rate.admit_handshake(
            peer_id="rate-over", source_ip="10.3.0.200", nonce_hex="ee" * 32, tick=0
        ),
    )

    global_limit = safety.AdmissionController()
    for index in range(safety.MAX_ACTIVE_SESSIONS):
        global_limit.admit_handshake(
            peer_id=f"global-{index}",
            source_ip=f"10.{10 + index // 4}.{index % 4}.1",
            nonce_hex=f"{index + 200:064x}",
            tick=0,
        )
    checks["global_session_limit_exact_plus_one"] = rejects(
        "active_session_limit",
        lambda: global_limit.admit_handshake(
            peer_id="global-over", source_ip="10.99.0.1", nonce_hex="dd" * 32, tick=0
        ),
    )

    message_rate = safety.AdmissionController()
    for _ in range(safety.MESSAGE_BUCKET_CAPACITY):
        message_rate.admit_message(peer_id="message-peer", frame_bytes=1, tick=0)
    checks["message_bucket_exact_plus_one"] = rejects(
        "message_rate",
        lambda: message_rate.admit_message(peer_id="message-peer", frame_bytes=1, tick=0),
    )
    frame_bounds = safety.AdmissionController()
    checks["maximum_frame_is_admitted"] = (
        frame_bounds.admit_message(peer_id="frame-peer", frame_bytes=safety.MAX_FRAME_BYTES, tick=0) == 32
    )
    checks["oversize_frame_is_rejected"] = rejects(
        "frame_size",
        lambda: frame_bounds.admit_message(
            peer_id="frame-peer", frame_bytes=safety.MAX_FRAME_BYTES + 1, tick=0
        ),
    )

    bucket_limit = safety.AdmissionController()
    for index in range(safety.MAX_ADMISSION_BUCKETS):
        bucket_limit.admit_message(peer_id=f"bucket-{index}", frame_bytes=1, tick=0)
    checks["admission_bucket_state_exact_plus_one"] = rejects(
        "admission_bucket_limit",
        lambda: bucket_limit.admit_message(peer_id="bucket-over", frame_bytes=1, tick=0),
    )

    persisted = safety.AdmissionController()
    persisted.admit_handshake(peer_id="persisted", source_ip="10.40.0.1", nonce_hex="aa" * 32, tick=5)
    restored = safety.AdmissionController(copy.deepcopy(persisted.snapshot()))
    checks["restart_preserves_replay_state"] = rejects(
        "replayed_handshake",
        lambda: restored.admit_handshake(
            peer_id="persisted", source_ip="10.40.0.1", nonce_hex="aa" * 32, tick=6
        ),
    )
    restored.quarantine("hostile", 6)
    restarted_again = safety.AdmissionController(copy.deepcopy(restored.snapshot()))
    checks["restart_preserves_quarantine_state"] = rejects(
        "quarantined_identity",
        lambda: restarted_again.admit_handshake(
            peer_id="hostile", source_ip="10.41.0.1", nonce_hex="bb" * 32, tick=7
        ),
    )
    observations["admission_rejections"] = {
        "identity": identity_limit.rejections,
        "prefix": prefix_limit.rejections,
        "handshake_rate": handshake_rate.rejections,
        "global": global_limit.rejections,
        "message": message_rate.rejections,
        "persisted": restored.rejections,
        "quarantine": restarted_again.rejections,
    }


def diversity_checks(checks: dict[str, bool], observations: dict[str, Any]) -> None:
    honest = [
        {"peer_id": "honest-a", "address": "10.50.1.1", "operator_group": "group-a", "transport": "tcp-v4", "priority": 0},
        {"peer_id": "honest-b", "address": "10.51.1.1", "operator_group": "group-b", "transport": "tcp-v6-tunnel", "priority": 1},
        {"peer_id": "honest-c", "address": "10.52.1.1", "operator_group": "group-c", "transport": "tor", "priority": 2},
    ]
    selected = safety.select_diverse_peers(honest)
    checks["diverse_peer_floor_is_satisfied"] = {item["peer_id"] for item in selected} == {
        "honest-a", "honest-b", "honest-c"
    }
    concentrated_prefix = [
        {"peer_id": f"prefix-attack-{index}", "address": f"10.60.0.{index + 1}", "operator_group": f"forged-{index}", "transport": "tcp-v4", "priority": index}
        for index in range(6)
    ]
    checks["address_concentrated_eclipse_is_rejected"] = rejects(
        "insufficient_peer_diversity", lambda: safety.select_diverse_peers(concentrated_prefix)
    )
    concentrated_operator = [
        {"peer_id": f"operator-attack-{index}", "address": f"10.{70 + index}.0.1", "operator_group": "one-operator", "transport": "tcp-v4" if index % 2 == 0 else "tor", "priority": index}
        for index in range(6)
    ]
    checks["operator_concentrated_eclipse_is_rejected"] = rejects(
        "insufficient_peer_diversity", lambda: safety.select_diverse_peers(concentrated_operator)
    )
    oversized_candidates = [
        {
            "peer_id": f"candidate-{index}",
            "address": f"10.{90 + index // 200}.{index % 200}.1",
            "operator_group": f"candidate-group-{index}",
            "transport": "tcp-v4" if index % 2 == 0 else "tor",
            "priority": index,
        }
        for index in range(safety.MAX_PEER_CANDIDATES + 1)
    ]
    checks["peer_candidate_limit_exact_plus_one"] = rejects(
        "peer_candidate_limit", lambda: safety.select_diverse_peers(oversized_candidates)
    )
    attackers = [
        {"peer_id": f"attacker-{index}", "address": f"10.80.0.{index + 1}", "operator_group": f"attacker-label-{index}", "transport": "tcp-v4", "priority": index}
        for index in range(8)
    ]
    mixed = safety.select_diverse_peers(attackers + honest)
    checks["honest_diverse_paths_survive_concentrated_churn"] = {
        "honest-b", "honest-c"
    }.issubset({item["peer_id"] for item in mixed})
    observations["selected_diverse_peers"] = [item["peer_id"] for item in selected]
    observations["mixed_selection"] = [item["peer_id"] for item in mixed]


def protocol_negative_checks(
    checks: dict[str, bool], observations: dict[str, Any], reports: dict[str, Any]
) -> None:
    report = reports["alpha-bravo"]
    initiator = report["initiator_hello"]
    responder = report["responder_hello"]
    alpha_public = safety.identity_public_key(IDENTITY_SEEDS["alpha"])
    bravo_public = safety.identity_public_key(IDENTITY_SEEDS["bravo"])
    checks["wrong_identity_is_rejected"] = rejects(
        "wrong_identity",
        lambda: safety.verify_hello(
            initiator,
            expected_peer_id="alpha",
            expected_public_key_hex=bravo_public,
            expected_role="initiator",
            expected_operator_group="operator-a",
            expected_transport="tcp-lab",
            expected_endpoint=HOSTS["alpha"],
            current_tick=1,
        ),
    )
    wrong_network = copy.deepcopy(initiator)
    wrong_network["network_id"] = "inherited-bitcoin-mainnet"
    checks["wrong_network_is_rejected"] = rejects(
        "wrong_network",
        lambda: safety.verify_hello(
            wrong_network,
            expected_peer_id="alpha",
            expected_public_key_hex=alpha_public,
            expected_role="initiator",
            expected_operator_group="operator-a",
            expected_transport="tcp-lab",
            expected_endpoint=HOSTS["alpha"],
            current_tick=1,
        ),
    )
    downgrade = copy.deepcopy(initiator)
    downgrade["identity_algorithm"] = "none"
    checks["algorithm_downgrade_is_rejected"] = rejects(
        "algorithm_downgrade",
        lambda: safety.verify_hello(
            downgrade,
            expected_peer_id="alpha",
            expected_public_key_hex=alpha_public,
            expected_role="initiator",
            expected_operator_group="operator-a",
            expected_transport="tcp-lab",
            expected_endpoint=HOSTS["alpha"],
            current_tick=1,
        ),
    )
    checks["expired_hello_is_rejected"] = rejects(
        "expired_hello",
        lambda: safety.verify_hello(
            initiator,
            expected_peer_id="alpha",
            expected_public_key_hex=alpha_public,
            expected_role="initiator",
            expected_operator_group="operator-a",
            expected_transport="tcp-lab",
            expected_endpoint=HOSTS["alpha"],
            current_tick=safety.HELLO_LIFETIME_TICKS + 1,
        ),
    )
    bad_signature = copy.deepcopy(initiator)
    bad_signature["signature_hex"] = "00" * 64
    checks["altered_hello_is_rejected"] = rejects(
        "identity_signature",
        lambda: safety.verify_hello(
            bad_signature,
            expected_peer_id="alpha",
            expected_public_key_hex=alpha_public,
            expected_role="initiator",
            expected_operator_group="operator-a",
            expected_transport="tcp-lab",
            expected_endpoint=HOSTS["alpha"],
            current_tick=1,
        ),
    )
    relabeled = safety.make_hello(
        peer_id="alpha",
        identity_seed_hex=IDENTITY_SEEDS["alpha"],
        operator_group="forged-new-operator",
        transport="tcp-lab",
        endpoint=HOSTS["alpha"],
        role="initiator",
        ephemeral_private_key=safety.ephemeral_private(b"alpha-relabeled"),
        nonce_hex="66" * 32,
        issued_tick=0,
    )
    checks["signed_operator_relabel_cannot_override_pin"] = rejects(
        "peer_metadata",
        lambda: safety.verify_hello(
            relabeled,
            expected_peer_id="alpha",
            expected_public_key_hex=alpha_public,
            expected_role="initiator",
            expected_operator_group="operator-a",
            expected_transport="tcp-lab",
            expected_endpoint=HOSTS["alpha"],
            current_tick=1,
        ),
    )

    alpha_ephemeral = safety.ephemeral_private(b"alpha->bravo")
    session_key, transcript = safety.derive_session_key(
        local_ephemeral_private=alpha_ephemeral,
        initiator_hello=initiator,
        responder_hello=responder,
    )
    frame = safety.session_envelope(
        session_key_hex=session_key,
        transcript_sha256=transcript,
        sender_id="alpha",
        recipient_id="bravo",
        sequence=1,
        issued_tick=2,
        payload={"op": "inventory", "cursor": 0},
    )
    safety.verify_session_envelope(
        frame,
        session_key_hex=session_key,
        transcript_sha256=transcript,
        expected_sender="alpha",
        expected_recipient="bravo",
        prior_sequence=0,
        session_start_tick=0,
        current_tick=2,
    )
    checks["replayed_session_frame_is_rejected"] = rejects(
        "frame_replay",
        lambda: safety.verify_session_envelope(
            frame,
            session_key_hex=session_key,
            transcript_sha256=transcript,
            expected_sender="alpha",
            expected_recipient="bravo",
            prior_sequence=1,
            session_start_tick=0,
            current_tick=2,
        ),
    )
    checks["altered_transcript_is_rejected"] = rejects(
        "altered_transcript",
        lambda: safety.verify_session_envelope(
            frame,
            session_key_hex=session_key,
            transcript_sha256="ff" * 32,
            expected_sender="alpha",
            expected_recipient="bravo",
            prior_sequence=0,
            session_start_tick=0,
            current_tick=2,
        ),
    )
    checks["expired_session_is_rejected"] = rejects(
        "expired_session",
        lambda: safety.verify_session_envelope(
            frame,
            session_key_hex=session_key,
            transcript_sha256=transcript,
            expected_sender="alpha",
            expected_recipient="bravo",
            prior_sequence=0,
            session_start_tick=0,
            current_tick=safety.SESSION_LIFETIME_TICKS + 1,
        ),
    )

    first = safety.signed_announcement(
        identity_seed_hex=IDENTITY_SEEDS["bravo"],
        peer_id="bravo",
        slot=777,
        selected_tip_share_id="11" * 32,
        state_commitment_sha256="22" * 32,
    )
    second = safety.signed_announcement(
        identity_seed_hex=IDENTITY_SEEDS["bravo"],
        peer_id="bravo",
        slot=777,
        selected_tip_share_id="33" * 32,
        state_commitment_sha256="44" * 32,
    )
    evidence = safety.equivocation_evidence(first, second, bravo_public, "bravo")
    checks["portable_signed_equivocation_is_preserved"] = bool(
        evidence["evidence_commitment_sha256"]
    )
    tampered = copy.deepcopy(first)
    tampered["state_commitment_sha256"] = "55" * 32
    checks["tampered_equivocation_claim_is_rejected"] = rejects(
        "identity_signature", lambda: safety.verify_announcement(tampered, bravo_public, "bravo")
    )
    observations["portable_equivocation_evidence"] = evidence


def run_lab(runtime: Path) -> dict[str, Any]:
    checks = safety.check_rfc_vectors()
    observations: dict[str, Any] = {}
    pair_keys, session_reports = session_material()
    checks["three_pairwise_authenticated_sessions_agree"] = len(pair_keys) == 3
    protocol_negative_checks(checks, observations, session_reports)
    admission_checks(checks, observations)
    diversity_checks(checks, observations)

    exact_catchup = safety.catchup_plan(5, 5 + safety.MAX_CATCHUP_SHARES)
    checks["long_partition_catchup_exact_limit"] = (
        exact_catchup["gap"] == safety.MAX_CATCHUP_SHARES
        and exact_catchup["pages"] == safety.MAX_CATCHUP_PAGES
    )
    checks["long_partition_catchup_plus_one_is_rejected"] = rejects(
        "catchup_share_limit",
        lambda: safety.catchup_plan(5, 6 + safety.MAX_CATCHUP_SHARES),
    )
    observations["exact_limit_catchup_plan"] = exact_catchup

    configs = legacy.build_configs(runtime, hosts=HOSTS, pair_keys=pair_keys)
    legacy_evidence = legacy.run_lab(runtime, configs=configs)
    checks["three_process_multi_address_share_sync_converges"] = legacy_evidence["all_checks_pass"]
    observations["share_sync_evidence_commitment_sha256"] = legacy_evidence[
        "evidence_commitment_sha256"
    ]
    observations["listener_address_prefixes"] = {
        node_id: safety.source_prefix(host) for node_id, host in HOSTS.items()
    }
    observations["session_transcripts"] = session_reports
    observations["legacy_share_sync_observations"] = legacy_evidence["observations"]

    evidence = {
        "format": FORMAT,
        "profile": safety.PROTOCOL,
        "network_id": safety.NETWORK_ID,
        "process_count": 3,
        "distinct_listener_addresses": HOSTS,
        "limits": safety.LIMITS,
        "checks": checks,
        "observations": observations,
        "all_checks_pass": all(checks.values()),
        "limitations": [
            "three_processes_but_one_physical_machine",
            "distinct_loopback_prefixes_not_independent_networks",
            "test_fixture_identity_seeds_not_deployment_keys",
            "classical_ed25519_and_x25519_not_post_quantum",
            "readable_reference_crypto_not_constant_time_or_production_reviewed",
            "operator_labels_are_self_asserted_and_sybil_vulnerable",
            "diversity_rules_reduce_simple_eclipse_risk_but_do_not_prove_sybil_resistance",
            "no_public_peer_discovery",
            "no_anonymity_claim",
            "no_production_settlement",
            "not_base_consensus",
            "not_final_soveroot_pow",
        ],
    }
    evidence["evidence_commitment_sha256"] = safety.canonical_hash(evidence)
    if not evidence["all_checks_pass"]:
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"multi-host share-sync lab failed checks: {failed}")
    return evidence


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.runtime is not None:
        args.runtime.mkdir(parents=True, exist_ok=True)
        evidence = run_lab(args.runtime)
    else:
        with tempfile.TemporaryDirectory(prefix="soveroot-share-multihost-") as directory:
            evidence = run_lab(Path(directory))
    write_json(args.output, evidence)
    print(f"Multi-address share-sync safety lab passed {len(evidence['checks'])} checks")
    print(f"Evidence: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, RuntimeError, safety.SafetyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
