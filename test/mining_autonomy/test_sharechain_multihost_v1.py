#!/usr/bin/env python3

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[2] / "contrib" / "mining_autonomy"
sys.path.insert(0, str(MODULE_DIR))

import sharechain_multihost_v1 as safety  # noqa: E402
import sharechain_sync_v0 as sync  # noqa: E402
import sharechain_v0 as reference  # noqa: E402


SEED_A = "01" * 32
SEED_B = "02" * 32


class MultiHostCryptoTests(unittest.TestCase):
    def test_rfc_vectors_all_match(self) -> None:
        self.assertTrue(all(safety.check_rfc_vectors().values()))

    def test_signature_rejects_message_and_signature_changes(self) -> None:
        public = safety.identity_public_key(SEED_A)
        signature = safety.identity_sign(SEED_A, b"message")
        self.assertTrue(safety.identity_verify(public, b"message", signature))
        self.assertFalse(safety.identity_verify(public, b"changed", signature))
        self.assertFalse(safety.identity_verify(public, b"message", "00" * 64))

    def test_both_session_endpoints_derive_identical_key(self) -> None:
        private_a, private_b = safety.ephemeral_private(b"a"), safety.ephemeral_private(b"b")
        hello_a = safety.make_hello(
            peer_id="alpha",
            identity_seed_hex=SEED_A,
            operator_group="operator-a",
            transport="tcp-lab",
            endpoint="127.20.1.1",
            role="initiator",
            ephemeral_private_key=private_a,
            nonce_hex="11" * 32,
            issued_tick=4,
        )
        hello_b = safety.make_hello(
            peer_id="bravo",
            identity_seed_hex=SEED_B,
            operator_group="operator-b",
            transport="tcp-lab",
            endpoint="127.21.1.1",
            role="responder",
            ephemeral_private_key=private_b,
            nonce_hex="22" * 32,
            issued_tick=4,
        )
        safety.verify_hello(
            hello_a,
            expected_peer_id="alpha",
            expected_public_key_hex=safety.identity_public_key(SEED_A),
            expected_role="initiator",
            expected_operator_group="operator-a",
            expected_transport="tcp-lab",
            expected_endpoint="127.20.1.1",
            current_tick=5,
        )
        safety.verify_hello(
            hello_b,
            expected_peer_id="bravo",
            expected_public_key_hex=safety.identity_public_key(SEED_B),
            expected_role="responder",
            expected_operator_group="operator-b",
            expected_transport="tcp-lab",
            expected_endpoint="127.21.1.1",
            current_tick=5,
        )
        a_key, a_transcript = safety.derive_session_key(
            local_ephemeral_private=private_a,
            initiator_hello=hello_a,
            responder_hello=hello_b,
        )
        b_key, b_transcript = safety.derive_session_key(
            local_ephemeral_private=private_b,
            initiator_hello=hello_a,
            responder_hello=hello_b,
        )
        self.assertEqual((a_key, a_transcript), (b_key, b_transcript))

        frame = safety.session_envelope(
            session_key_hex=a_key,
            transcript_sha256=a_transcript,
            sender_id="alpha",
            recipient_id="bravo",
            sequence=1,
            issued_tick=5,
            payload={"op": "inventory", "cursor": 0},
        )
        self.assertEqual(
            safety.verify_session_envelope(
                frame,
                session_key_hex=b_key,
                transcript_sha256=b_transcript,
                expected_sender="alpha",
                expected_recipient="bravo",
                prior_sequence=0,
                session_start_tick=4,
                current_tick=5,
            ),
            frame,
        )
        with self.assertRaisesRegex(safety.SafetyError, "sequence") as caught:
            safety.verify_session_envelope(
                frame,
                session_key_hex=b_key,
                transcript_sha256=b_transcript,
                expected_sender="alpha",
                expected_recipient="bravo",
                prior_sequence=1,
                session_start_tick=4,
                current_tick=5,
            )
        self.assertEqual(caught.exception.reason, "frame_replay")

    def test_hello_failures_are_specific_and_fail_closed(self) -> None:
        private = safety.ephemeral_private(b"hello")
        hello = safety.make_hello(
            peer_id="alpha",
            identity_seed_hex=SEED_A,
            operator_group="operator-a",
            transport="tcp-lab",
            endpoint="127.20.1.1",
            role="initiator",
            ephemeral_private_key=private,
            nonce_hex="33" * 32,
            issued_tick=0,
        )
        cases = []
        wrong_network = copy.deepcopy(hello)
        wrong_network["network_id"] = "bitcoin-main"
        cases.append((wrong_network, "wrong_network"))
        downgraded = copy.deepcopy(hello)
        downgraded["ephemeral_algorithm"] = "plaintext"
        cases.append((downgraded, "algorithm_downgrade"))
        tampered = copy.deepcopy(hello)
        tampered["endpoint"] = "127.99.1.1"
        cases.append((tampered, "identity_signature"))
        for value, reason in cases:
            with self.subTest(reason=reason):
                with self.assertRaises(safety.SafetyError) as caught:
                    safety.verify_hello(
                        value,
                        expected_peer_id="alpha",
                        expected_public_key_hex=safety.identity_public_key(SEED_A),
                        expected_role="initiator",
                        expected_operator_group="operator-a",
                        expected_transport="tcp-lab",
                        expected_endpoint="127.20.1.1",
                        current_tick=1,
                    )
                self.assertEqual(caught.exception.reason, reason)

        relabeled = safety.make_hello(
            peer_id="alpha",
            identity_seed_hex=SEED_A,
            operator_group="forged-operator",
            transport="tcp-lab",
            endpoint="127.20.1.1",
            role="initiator",
            ephemeral_private_key=private,
            nonce_hex="44" * 32,
            issued_tick=0,
        )
        with self.assertRaises(safety.SafetyError) as caught:
            safety.verify_hello(
                relabeled,
                expected_peer_id="alpha",
                expected_public_key_hex=safety.identity_public_key(SEED_A),
                expected_role="initiator",
                expected_operator_group="operator-a",
                expected_transport="tcp-lab",
                expected_endpoint="127.20.1.1",
                current_tick=1,
            )
        self.assertEqual(caught.exception.reason, "peer_metadata")

    def test_signed_equivocation_is_portable_and_tamper_evident(self) -> None:
        public = safety.identity_public_key(SEED_A)
        first = safety.signed_announcement(
            identity_seed_hex=SEED_A,
            peer_id="alpha",
            slot=8,
            selected_tip_share_id="11" * 32,
            state_commitment_sha256="22" * 32,
        )
        second = safety.signed_announcement(
            identity_seed_hex=SEED_A,
            peer_id="alpha",
            slot=8,
            selected_tip_share_id="33" * 32,
            state_commitment_sha256="44" * 32,
        )
        evidence = safety.equivocation_evidence(first, second, public, "alpha")
        self.assertEqual(len(evidence["evidence_commitment_sha256"]), 64)
        changed = copy.deepcopy(first)
        changed["state_commitment_sha256"] = "55" * 32
        with self.assertRaises(safety.SafetyError) as caught:
            safety.verify_announcement(changed, public, "alpha")
        self.assertEqual(caught.exception.reason, "identity_signature")


class AdmissionAndDiversityTests(unittest.TestCase):
    def test_identity_and_prefix_session_limits_are_exact(self) -> None:
        controller = safety.AdmissionController()
        for index in range(safety.MAX_SESSIONS_PER_IDENTITY):
            controller.admit_handshake(
                peer_id="same",
                source_ip=f"10.1.0.{index + 1}",
                nonce_hex=f"{index + 1:064x}",
                tick=0,
            )
        with self.assertRaises(safety.SafetyError) as caught:
            controller.admit_handshake(
                peer_id="same", source_ip="10.1.0.9", nonce_hex="09" * 32, tick=0
            )
        self.assertEqual(caught.exception.reason, "identity_session_limit")

        controller = safety.AdmissionController()
        for index in range(safety.MAX_SESSIONS_PER_SOURCE_PREFIX):
            controller.admit_handshake(
                peer_id=f"peer-{index}",
                source_ip=f"10.2.0.{index + 1}",
                nonce_hex=f"{index + 20:064x}",
                tick=0,
            )
        with self.assertRaises(safety.SafetyError) as caught:
            controller.admit_handshake(
                peer_id="over", source_ip="10.2.0.99", nonce_hex="99" * 32, tick=0
            )
        self.assertEqual(caught.exception.reason, "prefix_session_limit")

    def test_message_bucket_refills_deterministically(self) -> None:
        controller = safety.AdmissionController()
        for _ in range(safety.MESSAGE_BUCKET_CAPACITY):
            controller.admit_message(peer_id="peer", frame_bytes=1, tick=0)
        with self.assertRaises(safety.SafetyError) as caught:
            controller.admit_message(peer_id="peer", frame_bytes=1, tick=0)
        self.assertEqual(caught.exception.reason, "message_rate")
        for _ in range(safety.MESSAGE_REFILL_PER_TICK):
            controller.admit_message(peer_id="peer", frame_bytes=1, tick=1)
        with self.assertRaises(safety.SafetyError) as caught:
            controller.admit_message(peer_id="peer", frame_bytes=1, tick=1)
        self.assertEqual(caught.exception.reason, "message_rate")

    def test_admission_bucket_state_is_bounded_and_prunable(self) -> None:
        controller = safety.AdmissionController()
        for index in range(safety.MAX_ADMISSION_BUCKETS):
            controller.admit_message(peer_id=f"peer-{index}", frame_bytes=1, tick=0)
        with self.assertRaises(safety.SafetyError) as caught:
            controller.admit_message(peer_id="peer-over", frame_bytes=1, tick=0)
        self.assertEqual(caught.exception.reason, "admission_bucket_limit")
        controller.admit_message(peer_id="peer-after-refill", frame_bytes=1, tick=1)
        self.assertLessEqual(len(controller.message_buckets), safety.MAX_ADMISSION_BUCKETS)

    def test_snapshot_preserves_replay_and_quarantine(self) -> None:
        controller = safety.AdmissionController()
        controller.admit_handshake(
            peer_id="peer", source_ip="10.4.0.1", nonce_hex="aa" * 32, tick=2
        )
        controller.quarantine("hostile", 2)
        restored = safety.AdmissionController(copy.deepcopy(controller.snapshot()))
        with self.assertRaises(safety.SafetyError) as caught:
            restored.admit_handshake(
                peer_id="peer", source_ip="10.4.0.1", nonce_hex="aa" * 32, tick=3
            )
        self.assertEqual(caught.exception.reason, "replayed_handshake")
        with self.assertRaises(safety.SafetyError) as caught:
            restored.admit_handshake(
                peer_id="hostile", source_ip="10.5.0.1", nonce_hex="bb" * 32, tick=3
            )
        self.assertEqual(caught.exception.reason, "quarantined_identity")

    def test_peer_diversity_and_concentration(self) -> None:
        diverse = [
            {"peer_id": "a", "address": "10.10.0.1", "operator_group": "a", "transport": "tcp", "priority": 0},
            {"peer_id": "b", "address": "10.11.0.1", "operator_group": "b", "transport": "tor", "priority": 1},
            {"peer_id": "c", "address": "10.12.0.1", "operator_group": "c", "transport": "tcp", "priority": 2},
        ]
        self.assertEqual(len(safety.select_diverse_peers(diverse)), 3)
        concentrated = copy.deepcopy(diverse)
        for index, candidate in enumerate(concentrated):
            candidate["address"] = f"10.10.0.{index + 1}"
        with self.assertRaises(safety.SafetyError) as caught:
            safety.select_diverse_peers(concentrated)
        self.assertEqual(caught.exception.reason, "insufficient_peer_diversity")

        oversized = [
            {
                "peer_id": f"candidate-{index}",
                "address": f"10.{20 + index // 200}.{index % 200}.1",
                "operator_group": f"group-{index}",
                "transport": "tcp" if index % 2 == 0 else "tor",
                "priority": index,
            }
            for index in range(safety.MAX_PEER_CANDIDATES + 1)
        ]
        with self.assertRaises(safety.SafetyError) as caught:
            safety.select_diverse_peers(oversized)
        self.assertEqual(caught.exception.reason, "peer_candidate_limit")

    def test_address_prefix_normalizes_mapped_ipv4_and_rejects_scopes(self) -> None:
        self.assertEqual(safety.source_prefix("::ffff:10.8.9.10"), "10.8.9.0/24")
        with self.assertRaises(safety.SafetyError) as caught:
            safety.source_prefix("fe80::1%eth0")
        self.assertEqual(caught.exception.reason, "source_address")

    def test_catchup_bound_exact_and_plus_one(self) -> None:
        plan = safety.catchup_plan(10, 10 + safety.MAX_CATCHUP_SHARES)
        self.assertEqual(plan["pages"], safety.MAX_CATCHUP_PAGES)
        with self.assertRaises(safety.SafetyError) as caught:
            safety.catchup_plan(10, 11 + safety.MAX_CATCHUP_SHARES)
        self.assertEqual(caught.exception.reason, "catchup_share_limit")


class LoopbackAddressTests(unittest.TestCase):
    def test_v0_accepts_distinct_loopback_prefixes_but_not_private_lan(self) -> None:
        config = {
            "format": sync.PROTOCOL,
            "node_id": "alpha",
            "listen_host": "127.20.1.1",
            "listen_port": 19333,
            "state_path": "unused.json",
            "control_key_hex": "aa" * 32,
            "trusted_rounds": reference.trusted_rounds(),
            "limits": sync.LIMITS,
            "peers": [
                {"node_id": "bravo", "host": "127.21.1.1", "port": 19334, "shared_key_hex": "bb" * 32}
            ],
        }
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(sync.load_config(path)["listen_host"], "127.20.1.1")
            config["listen_host"] = "10.0.0.1"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(sync.SyncError) as caught:
                sync.load_config(path)
            self.assertEqual(caught.exception.reason, "non_loopback")


if __name__ == "__main__":
    unittest.main()
