#!/usr/bin/env python3

import copy
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MINING = ROOT / "contrib" / "mining_autonomy"
sys.path.insert(0, str(MINING))

import run_share_sync_lab as lab  # noqa: E402
import sharechain_sync_v0 as sync  # noqa: E402
import sharechain_v0 as reference  # noqa: E402


class ShareSyncUnitTests(unittest.TestCase):
    def test_authenticated_envelope_rejects_tampering_and_wrong_route(self):
        key = "ab" * 32
        envelope = sync.sign_envelope("alpha", "bravo", 1, {"op": "status"}, key)
        self.assertEqual(
            sync.verify_envelope(
                envelope,
                expected_sender="alpha",
                expected_recipient="bravo",
                key_hex=key,
            ),
            envelope,
        )
        tampered = copy.deepcopy(envelope)
        tampered["payload"]["op"] = "stop"
        with self.assertRaisesRegex(sync.SyncError, "MAC"):
            sync.verify_envelope(
                tampered,
                expected_sender="alpha",
                expected_recipient="bravo",
                key_hex=key,
            )
        with self.assertRaisesRegex(sync.SyncError, "route"):
            sync.verify_envelope(
                envelope,
                expected_sender="alpha",
                expected_recipient="charlie",
                key_hex=key,
            )

    def test_configuration_is_loopback_only_and_limits_are_frozen(self):
        with tempfile.TemporaryDirectory() as directory:
            configs = lab.build_configs(pathlib.Path(directory))
            alpha_path = pathlib.Path(configs["alpha"]["_path"])
            self.assertEqual(sync.load_config(alpha_path)["limits"], sync.LIMITS)

            changed = json.loads(alpha_path.read_text(encoding="utf-8"))
            changed["listen_host"] = "0.0.0.0"
            alpha_path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(sync.SyncError, "loopback"):
                sync.load_config(alpha_path)

    def test_reference_and_independent_validators_gate_every_accepted_state(self):
        with tempfile.TemporaryDirectory() as directory:
            config = lab.build_configs(pathlib.Path(directory))["alpha"]
            node = sync.ShareSyncNode(lab.public_config(config))
            scenario = next(
                item
                for item in reference.build_corpus()["scenarios"]
                if item["name"] == "valid_linear_chain"
            )
            summary = node.import_shares(list(reversed(scenario["shares"])))
            self.assertEqual(summary["rejected"], 0)
            self.assertEqual(node.status()["selected_state"], scenario["expected"]["state"])

    def test_pending_orphans_expire_by_deterministic_tick(self):
        with tempfile.TemporaryDirectory() as directory:
            config = lab.build_configs(pathlib.Path(directory))["alpha"]
            node = sync.ShareSyncNode(lab.public_config(config))
            orphan = lab.hostile_orphans(1)[0]
            self.assertEqual(node.import_shares([orphan])["orphaned"], 1)
            with node.lock:
                node.state["tick"] += sync.MAX_ORPHAN_AGE_TICKS + 1
                self.assertEqual(node._prune_orphans(), 1)
            self.assertEqual(node.status()["orphan_count"], 0)

    def test_inventory_pages_cover_the_full_limit_inside_one_frame(self):
        self.assertEqual(
            sync.MAX_INVENTORY_IDS_PER_MESSAGE * sync.MAX_INVENTORY_PAGES,
            sync.MAX_KNOWN_SHARES,
        )
        ids = [f"{index:064x}" for index in range(sync.MAX_INVENTORY_IDS_PER_MESSAGE)]
        response = sync.sign_envelope(
            "alpha",
            "bravo",
            1,
            {
                "op": "inventory_response",
                "share_ids": ids,
                "next_cursor": sync.MAX_INVENTORY_IDS_PER_MESSAGE,
                "announcement": {
                    "slot": 1,
                    "state_commitment_sha256": "11" * 32,
                    "selected_tip_share_id": "22" * 32,
                },
            },
            "ab" * 32,
        )
        self.assertLess(len(sync.canonical_bytes(response)) + 1, sync.MAX_MESSAGE_BYTES)

    def test_announcement_history_discards_the_oldest_slot_at_its_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            config = lab.build_configs(pathlib.Path(directory))["alpha"]
            node = sync.ShareSyncNode(lab.public_config(config))
            for slot in range(sync.MAX_ANNOUNCEMENT_SLOTS_PER_PEER + 1):
                envelope = sync.sign_envelope(
                    "bravo",
                    "alpha",
                    slot + 1,
                    {
                        "op": "inventory",
                        "cursor": 0,
                        "announcement": {
                            "slot": slot,
                            "state_commitment_sha256": f"{slot + 1:064x}",
                            "selected_tip_share_id": "00" * 32,
                        },
                    },
                    "ab" * 32,
                )
                node._observe_announcement(envelope)
            slots = node.state["announcements"]["bravo"]
            self.assertEqual(len(slots), sync.MAX_ANNOUNCEMENT_SLOTS_PER_PEER)
            self.assertNotIn("0", slots)
            self.assertIn(str(sync.MAX_ANNOUNCEMENT_SLOTS_PER_PEER), slots)
            stale = sync.sign_envelope(
                "bravo",
                "alpha",
                sync.MAX_ANNOUNCEMENT_SLOTS_PER_PEER + 2,
                {
                    "op": "inventory",
                    "cursor": 0,
                    "announcement": {
                        "slot": 0,
                        "state_commitment_sha256": "ff" * 32,
                        "selected_tip_share_id": "00" * 32,
                    },
                },
                "ab" * 32,
            )
            node._observe_announcement(stale)
            self.assertNotIn("0", slots)
            self.assertIn("1", slots)


class ThreeProcessShareSyncLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.evidence = lab.run_lab(pathlib.Path(cls.temporary.name))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_all_frozen_adversarial_checks_pass(self):
        self.assertTrue(self.evidence["all_checks_pass"])
        self.assertEqual(len(self.evidence["checks"]), 13)
        self.assertTrue(all(self.evidence["checks"].values()))

    def test_evidence_covers_network_and_resource_failures(self):
        required = {
            "partition_is_observable",
            "selective_relay_is_observable",
            "restart_preserves_pending_state",
            "authenticated_equivocation_is_preserved",
            "replayed_message_is_rejected",
            "unauthenticated_message_is_rejected",
            "orphan_flood_fails_closed_at_limit",
            "orphan_age_is_bounded",
            "oversize_message_is_rejected",
            "three_processes_converge",
        }
        self.assertTrue(required.issubset(self.evidence["checks"]))

    def test_evidence_commitment_is_canonical(self):
        body = {
            key: value
            for key, value in self.evidence.items()
            if key != "evidence_commitment_sha256"
        }
        self.assertEqual(
            self.evidence["evidence_commitment_sha256"],
            sync.canonical_hash(body),
        )

    def test_retained_equivocation_contains_two_verifiable_envelopes(self):
        records = self.evidence["observations"]["equivocation_evidence"]
        self.assertEqual(len(records), 1)
        record = records[0]
        commitment_body = {
            key: value for key, value in record.items() if key != "evidence_commitment_sha256"
        }
        self.assertEqual(record["evidence_commitment_sha256"], sync.canonical_hash(commitment_body))
        for side in ("first", "second"):
            sync.verify_envelope(
                record[side]["authenticated_envelope"],
                expected_sender="bravo",
                expected_recipient="alpha",
                key_hex="ab" * 32,
            )

    def test_public_network_claims_remain_explicitly_out_of_scope(self):
        self.assertIn("loopback_private_lab_only", self.evidence["limitations"])
        self.assertIn("no_sybil_or_eclipse_resistance", self.evidence["limitations"])
        self.assertIn("no_production_settlement", self.evidence["limitations"])


if __name__ == "__main__":
    unittest.main()
