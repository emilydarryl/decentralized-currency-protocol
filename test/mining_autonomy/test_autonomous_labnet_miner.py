#!/usr/bin/env python3

import importlib.util
import json
import pathlib
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "contrib" / "mining_autonomy" / "autonomous_labnet_miner.py"
SPEC = importlib.util.spec_from_file_location("autonomous_labnet_miner", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MINER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MINER
SPEC.loader.exec_module(MINER)


def payout_plan(coinbase_value=5_000_000_000):
    body = {
        "format": "soveroot-labnet-direct-payout-plan-v0",
        "chain": "labnet",
        "custody": "none",
        "settlement_status": "direct_coinbase_test_plan",
        "coinbase_value": coinbase_value,
        "receipt_set_commitment_sha256": "33" * 32,
        "eligible_receipt_count": 2,
        "total_work_units": 3,
        "outputs": [
            {
                "payout_script_hex": "51",
                "value": 2_000_000_000,
                "work_units": 1,
                "receipt_ids": ["11" * 32],
            },
            {
                "payout_script_hex": "52",
                "value": coinbase_value - 2_000_000_000,
                "work_units": 2,
                "receipt_ids": ["22" * 32],
            },
        ],
    }
    return {**body, "payout_plan_commitment_sha256": MINER.canonical_template_commitment(body)}


class EncodingTests(unittest.TestCase):
    def test_varint_boundaries(self):
        self.assertEqual(MINER.encode_varint(0xFC), b"\xfc")
        self.assertEqual(MINER.encode_varint(0xFD), b"\xfd\xfd\x00")
        self.assertEqual(MINER.encode_varint(0x10000), b"\xfe\x00\x00\x01\x00")

    def test_bip34_small_and_regular_heights(self):
        self.assertEqual(MINER.encode_block_height(1), b"\x51")
        self.assertEqual(MINER.encode_block_height(16), b"\x60")
        self.assertEqual(MINER.encode_block_height(17), b"\x01\x11")
        self.assertEqual(MINER.encode_block_height(128), b"\x02\x80\x00")

    def test_labnet_compact_target(self):
        target = MINER.compact_target(0x207FFFFF)
        self.assertEqual(target, 0x7FFFFF << (8 * 29))

    def test_invalid_compact_target_is_rejected(self):
        with self.assertRaises(MINER.MiningError):
            MINER.compact_target(0x20800000)


class BlockConstructionTests(unittest.TestCase):
    def test_coinbase_txid_excludes_witness_serialization(self):
        commitment = bytes.fromhex("6a24aa21a9ed" + "11" * 32)
        coinbase = MINER.build_coinbase(
            height=1,
            value=5_000_000_000,
            payout_script=b"\x51",
            witness_commitment=commitment,
        )
        self.assertEqual(coinbase.block_bytes[4:6], b"\x00\x01")
        self.assertIn(b"\x01\x20" + b"\x00" * 32, coinbase.block_bytes)
        self.assertEqual(len(coinbase.txid_hash), 32)

    def test_coinbase_serializes_and_conserves_direct_payout_outputs(self):
        outputs = [(2_000_000_000, b"\x51"), (3_000_000_000, b"\x52")]
        coinbase = MINER.build_coinbase(
            height=17,
            value=5_000_000_000,
            payout_outputs=outputs,
        )
        self.assertEqual(coinbase.serialized_outputs, MINER._serialize_outputs(outputs))
        with self.assertRaisesRegex(MINER.MiningError, "conserve"):
            MINER.build_coinbase(
                height=17,
                value=5_000_000_000,
                payout_outputs=[(1, b"\x51"), (2, b"\x52")],
            )

    def test_payout_plan_rejects_output_substitution(self):
        plan = payout_plan()
        MINER.validate_payout_plan(plan, 5_000_000_000)
        plan["outputs"][0]["payout_script_hex"] = "53"
        with self.assertRaisesRegex(MINER.MiningError, "canonical order|commitment"):
            MINER.validate_payout_plan(plan, 5_000_000_000)

    def test_payout_plan_rejects_receipt_reuse(self):
        plan = payout_plan()
        plan["outputs"][1]["receipt_ids"] = ["11" * 32]
        body = {key: value for key, value in plan.items() if key != "payout_plan_commitment_sha256"}
        plan["payout_plan_commitment_sha256"] = MINER.canonical_template_commitment(body)
        with self.assertRaisesRegex(MINER.MiningError, "multiple payout outputs"):
            MINER.validate_payout_plan(plan, 5_000_000_000)

    def test_merkle_root_duplicates_an_odd_leaf(self):
        leaves = [bytes([value]) * 32 for value in (1, 2, 3)]
        first = MINER.hash256(leaves[0] + leaves[1])
        second = MINER.hash256(leaves[2] + leaves[2])
        self.assertEqual(MINER.merkle_root(leaves), MINER.hash256(first + second))

    def test_coinbase_merkle_path_reconstructs_the_same_root(self):
        leaves = [bytes([value]) * 32 for value in (1, 2, 3)]
        path = MINER.coinbase_merkle_path(leaves)
        reconstructed = leaves[0]
        for sibling in path:
            reconstructed = MINER.hash256(reconstructed + sibling)
        self.assertEqual(reconstructed, MINER.merkle_root(leaves))

    def test_easy_labnet_header_is_solved_and_valid(self):
        prefix = b"\x00" * 68 + (1).to_bytes(4, "little") + (0x207FFFFF).to_bytes(4, "little")
        header, nonce, digest = MINER.solve_header(prefix, 0x207FFFFF, 100)
        self.assertEqual(len(header), 80)
        self.assertEqual(header[-4:], nonce.to_bytes(4, "little"))
        self.assertLessEqual(int.from_bytes(digest, "little"), MINER.compact_target(0x207FFFFF))

    def test_attempt_observer_sees_the_winning_header(self):
        observed = []
        prefix = b"\x00" * 68 + (1).to_bytes(4, "little") + (0x207FFFFF).to_bytes(4, "little")
        header, nonce, digest = MINER.solve_header(
            prefix,
            0x207FFFFF,
            100,
            lambda seen_header, seen_nonce, seen_digest, candidate: observed.append(
                (seen_header, seen_nonce, seen_digest, candidate)
            ),
        )
        self.assertTrue(observed[-1][3])
        self.assertEqual(observed[-1][:3], (header, nonce, digest))


class ShareReporterTests(unittest.TestCase):
    def test_reporter_rejects_non_loopback_endpoint(self):
        with self.assertRaisesRegex(MINER.MiningError, "loopback"):
            MINER.ShareReporter("http://pool.example/share", "worker", 1, 0.25)

    def test_delivery_failure_is_counted_without_raising(self):
        reporter = MINER.ShareReporter("http://127.0.0.1:29445/share", "worker", 1, 0.25)
        with mock.patch.object(MINER.urllib.request, "urlopen", side_effect=OSError("offline")):
            reporter.observe(
                b"\x00" * 80,
                0,
                b"\x11" * 32,
                False,
                height=1,
                previous_block_hash="00" * 32,
                payout_script_hex="51",
                template_commitment_sha256="22" * 32,
            )
        self.assertEqual(reporter.delivered, 0)
        self.assertEqual(reporter.failed, 1)


class SettlementPlanProviderTests(unittest.TestCase):
    class Response:
        def __init__(self, document):
            self.body = json.dumps(document).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_arguments):
            return False

        def read(self, _limit):
            return self.body

    def test_conflicting_replica_plans_fail_closed(self):
        first = payout_plan()
        second = payout_plan()
        second["outputs"][0]["value"] -= 1
        second["outputs"][1]["value"] += 1
        body = {key: value for key, value in second.items() if key != "payout_plan_commitment_sha256"}
        second["payout_plan_commitment_sha256"] = MINER.canonical_template_commitment(body)
        provider = MINER.SettlementPlanProvider(
            ["http://127.0.0.1:29445", "http://127.0.0.1:29448"], 1.0
        )
        with mock.patch.object(
            MINER.urllib.request,
            "urlopen",
            side_effect=[self.Response(first), self.Response(second)],
        ):
            with self.assertRaisesRegex(MINER.MiningError, "conflicting payout plans"):
                provider.fetch(5_000_000_000)

    def test_unavailable_replica_fails_pooled_settlement(self):
        provider = MINER.SettlementPlanProvider(
            ["http://127.0.0.1:29445", "http://127.0.0.1:29448"], 1.0
        )
        with mock.patch.object(MINER.urllib.request, "urlopen", side_effect=OSError("offline")):
            with self.assertRaisesRegex(MINER.MiningError, "unavailable"):
                provider.fetch(5_000_000_000)


class JobDeclaratorTests(unittest.TestCase):
    def declarator(self):
        return MINER.JobDeclarator(
            pathlib.Path(__file__),
            "127.0.0.1:29446",
            "test-public-key",
            1000,
        )

    def test_malformed_helper_output_enters_direct_fallback(self):
        completed = mock.Mock(returncode=0, stdout="not-json")
        with mock.patch.object(MINER.subprocess, "run", return_value=completed):
            result = self.declarator().declare({"template_commitment_sha256": "11" * 32})
        self.assertEqual(result["status"], "direct_fallback")
        self.assertEqual(result["reason"], "malformed_helper_reply")

    def test_helper_cannot_switch_the_committed_template(self):
        completed = mock.Mock(
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "accepted",
                    "transport_status": "authenticated",
                    "template_commitment_sha256": "22" * 32,
                }
            ),
        )
        with mock.patch.object(MINER.subprocess, "run", return_value=completed):
            result = self.declarator().declare({"template_commitment_sha256": "11" * 32})
        self.assertEqual(result["status"], "direct_fallback")
        self.assertEqual(result["reason"], "template_commitment_mismatch")


class CoordinatorSelectorTests(unittest.TestCase):
    class FakeCoordinator:
        def __init__(self, name, responses):
            self.name = name
            self.endpoint = f"127.0.0.1:{30000 + len(name)}"
            self.responses = iter(responses)
            self.templates = []

        def declare(self, template):
            self.templates.append(template.copy())
            return next(self.responses)

    def test_rejection_switches_coordinator_without_changing_template(self):
        template = {"template_commitment_sha256": "11" * 32}
        primary = self.FakeCoordinator(
            "primary",
            [{"status": "direct_fallback", "reason": "declaration:policy-rejection"}],
        )
        alternate = self.FakeCoordinator(
            "alternate",
            [
                {
                    "status": "accepted",
                    "transport_status": "authenticated",
                    "template_commitment_sha256": template["template_commitment_sha256"],
                    "job_id": 9,
                }
            ],
        )
        result = MINER.CoordinatorSelector([primary, alternate]).declare(template)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["coordinator"], "alternate")
        self.assertTrue(result["failover_used"])
        self.assertEqual(primary.templates, [template])
        self.assertEqual(alternate.templates, [template])

    def test_conflicting_views_quarantine_coordinator_for_two_miners(self):
        template = {"template_commitment_sha256": "22" * 32}
        registry = MINER.CoordinatorViewRegistry()
        first = self.FakeCoordinator(
            "equivocator",
            [
                {
                    "status": "accepted",
                    "transport_status": "authenticated",
                    "coordinator_state_commitment": "aa" * 32,
                }
            ],
        )
        second = self.FakeCoordinator(
            "equivocator",
            [
                {
                    "status": "accepted",
                    "transport_status": "authenticated",
                    "coordinator_state_commitment": "bb" * 32,
                }
            ],
        )
        self.assertEqual(
            MINER.CoordinatorSelector([first], registry).declare(template)["status"],
            "accepted",
        )
        result = MINER.CoordinatorSelector([second], registry).declare(template)
        self.assertEqual(result["status"], "direct_fallback")
        self.assertEqual(result["reason"], "all_configured_coordinators_failed")
        self.assertIn("equivocator", registry.quarantined)


class FakeLabnetRpc:
    def __init__(self, chain="labnet"):
        self.chain = chain
        self.best_hash = "00" * 32
        self.submitted_block = None

    def call(self, method, *arguments, wallet=None):
        if method == "getblockchaininfo":
            return {"chain": self.chain, "bestblockhash": self.best_hash}
        if method == "getaddressinfo":
            self.test_wallet = wallet
            self.test_address = arguments[0]
            return {"scriptPubKey": "51"}
        if method == "getblocktemplate":
            return {
                "version": 4,
                "previousblockhash": self.best_hash,
                "height": 1,
                "coinbasevalue": 5_000_000_000,
                "curtime": 1,
                "bits": "207fffff",
                "transactions": [],
                "coinbaseaux": {"flags": ""},
            }
        if method == "submitblock":
            self.submitted_block = bytes.fromhex(arguments[0])
            header = self.submitted_block[:80]
            digest = MINER.hash256(header)
            if int.from_bytes(digest, "little") > MINER.compact_target(0x207FFFFF):
                return "high-hash"
            if self.submitted_block[80] != 1:
                return "bad-transaction-count"
            self.best_hash = digest[::-1].hex()
            return None
        if method == "getbestblockhash":
            return self.best_hash
        raise AssertionError(f"unexpected RPC method: {method}")


class MiningWorkflowTests(unittest.TestCase):
    def test_external_miner_builds_solves_and_submits_a_block(self):
        rpc = FakeLabnetRpc()
        result = MINER.mine_one_block(
            rpc,
            wallet="miner",
            address="labnet-address",
            max_nonce=100,
        )
        self.assertEqual(result["height"], 1)
        self.assertEqual(result["transactions"], 1)
        self.assertEqual(result["block_hash"], rpc.best_hash)
        self.assertEqual(rpc.test_wallet, "miner")
        self.assertIsNotNone(rpc.submitted_block)
        self.assertEqual(result["declaration_status"], "direct_fallback")

    def test_agreed_plan_is_committed_and_paid_directly_in_coinbase(self):
        class AgreedPlanProvider:
            def fetch(self, coinbase_value):
                self.requested_value = coinbase_value
                return payout_plan(coinbase_value)

        rpc = FakeLabnetRpc()
        provider = AgreedPlanProvider()
        result = MINER.mine_one_block(
            rpc,
            wallet="miner",
            address="labnet-address",
            max_nonce=100,
            settlement_provider=provider,
        )
        self.assertEqual(provider.requested_value, 5_000_000_000)
        self.assertEqual(
            result["payout_plan_commitment_sha256"],
            payout_plan()["payout_plan_commitment_sha256"],
        )
        expected_outputs = MINER._serialize_outputs(
            [(2_000_000_000, b"\x51"), (3_000_000_000, b"\x52")]
        )
        self.assertIn(expected_outputs, rpc.submitted_block)

    def test_accepted_declaration_solves_and_directly_publishes_exact_committed_template(self):
        class AcceptingDeclarator:
            endpoint = "127.0.0.1:34254"

            def declare(self, template):
                self.template = template
                return {
                    "status": "accepted",
                    "transport_status": "authenticated",
                    "template_commitment_sha256": template["template_commitment_sha256"],
                }

        rpc = FakeLabnetRpc()
        declarator = AcceptingDeclarator()
        result = MINER.mine_one_block(
            rpc,
            wallet="miner",
            address="labnet-address",
            max_nonce=100,
            job_declarator=declarator,
        )
        self.assertEqual(result["declaration_status"], "accepted")
        self.assertEqual(
            result["template_commitment_sha256"],
            declarator.template["template_commitment_sha256"],
        )
        self.assertEqual(declarator.template["previous_block_hash"], "00" * 32)
        self.assertEqual(declarator.template["coinbase_tx_hex"], rpc.submitted_block[81:].hex())
        self.assertEqual(result["block_hash"], rpc.best_hash)

    def test_rejected_declaration_cannot_stop_direct_publication(self):
        class RejectingDeclarator:
            endpoint = "127.0.0.1:34254"

            def declare(self, template):
                return {
                    "status": "direct_fallback",
                    "transport_status": "authenticated",
                    "reason": "declaration:policy-rejection",
                    "template_commitment_sha256": template["template_commitment_sha256"],
                }

        rpc = FakeLabnetRpc()
        result = MINER.mine_one_block(
            rpc,
            wallet="miner",
            address="labnet-address",
            max_nonce=100,
            job_declarator=RejectingDeclarator(),
        )
        self.assertEqual(result["declaration_status"], "direct_fallback")
        self.assertEqual(result["declaration_reason"], "declaration:policy-rejection")
        self.assertEqual(result["block_hash"], rpc.best_hash)

    def test_external_miner_fails_closed_on_another_chain(self):
        with self.assertRaisesRegex(MINER.MiningError, "chain=labnet"):
            MINER.mine_one_block(
                FakeLabnetRpc(chain="regtest"),
                wallet="miner",
                address="labnet-address",
                max_nonce=100,
            )


if __name__ == "__main__":
    unittest.main()
