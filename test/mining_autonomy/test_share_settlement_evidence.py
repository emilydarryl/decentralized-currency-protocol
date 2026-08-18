#!/usr/bin/env python3

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "share_settlement_evidence",
    ROOT / "contrib" / "mining_autonomy" / "build_share_settlement_evidence.py",
)
assert SPEC is not None and SPEC.loader is not None
EVIDENCE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EVIDENCE
SPEC.loader.exec_module(EVIDENCE)


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def fixture_documents():
    receipts = []
    for marker, script in (("11", "51"), ("22", "52"), ("33", "52")):
        receipts.append(
            {
                "receipt_id_sha256": marker * 32,
                "work_id_sha256": chr(ord(marker[0]) + 4) * 64,
                "block_candidate": True,
                "hash": {"11": "aa", "22": "bb", "33": "cc"}[marker] * 32,
                "payout_script_hex": script,
            }
        )
    receipts.sort(key=lambda item: item["receipt_id_sha256"])
    commitment_body = [
        {"receipt_id_sha256": item["receipt_id_sha256"], "work_id_sha256": item["work_id_sha256"]}
        for item in receipts
    ]
    receipt_set = {
        "format": "soveroot-labnet-receipt-set-v0",
        "chain": "labnet",
        "receipt_count": 3,
        "receipt_set_commitment_sha256": EVIDENCE.canonical_hash(commitment_body),
        "receipts": receipts,
    }
    outputs = [
        {"payout_script_hex": "51", "value": 2_000_000_000, "work_units": 1, "receipt_ids": ["11" * 32]},
        {
            "payout_script_hex": "52",
            "value": 3_000_000_000,
            "work_units": 2,
            "receipt_ids": ["22" * 32, "33" * 32],
        },
    ]
    plan_body = {
        "format": "soveroot-labnet-direct-payout-plan-v0",
        "chain": "labnet",
        "custody": "none",
        "settlement_status": "direct_coinbase_test_plan",
        "coinbase_value": 5_000_000_000,
        "receipt_set_commitment_sha256": receipt_set["receipt_set_commitment_sha256"],
        "eligible_receipt_count": 3,
        "total_work_units": 3,
        "outputs": outputs,
    }
    plan = {**plan_body, "payout_plan_commitment_sha256": EVIDENCE.canonical_hash(plan_body)}
    block = {
        "hash": "aa" * 32,
        "tx": [
            {
                "txid": "bb" * 32,
                "vin": [{"coinbase": "00"}],
                "vout": [
                    {"value": 20, "scriptPubKey": {"hex": "51"}},
                    {"value": 30, "scriptPubKey": {"hex": "52"}},
                    {"value": 0, "scriptPubKey": {"hex": "6a"}},
                ],
            }
        ],
    }
    commitment = plan["payout_plan_commitment_sha256"]
    settlement_events = [
        {"component": "autonomous_labnet_miner", "event": "replica_plan_received", "payout_plan_commitment_sha256": commitment},
        {"component": "autonomous_labnet_miner", "event": "replica_plan_received", "payout_plan_commitment_sha256": commitment},
        {"component": "autonomous_labnet_miner", "event": "payout_plan_committed", "payout_plan_commitment_sha256": commitment},
        {"component": "autonomous_labnet_miner", "event": "direct_coinbase_settlement_published", "payout_plan_commitment_sha256": commitment, "block_hash": block["hash"]},
    ]
    offline_events = [
        {"component": "autonomous_labnet_miner", "event": "direct_submitblock_accepted", "block_hash": "cc" * 32},
        {"component": "autonomous_labnet_miner", "event": "reporting_summary", "delivered": 1},
    ]
    seed_events = [
        [{"component": "autonomous_labnet_miner", "event": "direct_submitblock_accepted", "block_hash": "aa" * 32}],
        [{"component": "autonomous_labnet_miner", "event": "direct_submitblock_accepted", "block_hash": "bb" * 32}],
    ]
    recovery = {
        "accepted": True,
        "added_receipts": 1,
        "receipt_count": 3,
        "receipt_set_commitment_sha256": receipt_set["receipt_set_commitment_sha256"],
    }
    return receipt_set, plan, block, settlement_events, seed_events, offline_events, recovery


class SettlementEvidenceTests(unittest.TestCase):
    def build(self, mutate=None):
        receipt_set, plan, block, settlement_events, seed_events, offline_events, recovery = fixture_documents()
        if mutate is not None:
            mutate(receipt_set, plan, block)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            paths = {name: root / f"{name}.json" for name in ("receipts_a", "receipts_b", "plan_a", "plan_b", "block", "recovery")}
            write_json(paths["receipts_a"], receipt_set)
            write_json(paths["receipts_b"], receipt_set)
            write_json(paths["plan_a"], plan)
            write_json(paths["plan_b"], plan)
            write_json(paths["block"], block)
            write_json(paths["recovery"], recovery)
            settlement_log = root / "settlement.log"
            seed_a_log = root / "seed-a.log"
            seed_b_log = root / "seed-b.log"
            offline_log = root / "offline.log"
            settlement_log.write_text("\n".join(json.dumps(event) for event in settlement_events) + "\n", encoding="utf-8")
            seed_a_log.write_text("\n".join(json.dumps(event) for event in seed_events[0]) + "\n", encoding="utf-8")
            seed_b_log.write_text("\n".join(json.dumps(event) for event in seed_events[1]) + "\n", encoding="utf-8")
            offline_log.write_text("\n".join(json.dumps(event) for event in offline_events) + "\n", encoding="utf-8")
            return EVIDENCE.build(
                paths["receipts_a"], paths["receipts_b"], paths["plan_a"], paths["plan_b"],
                paths["block"], settlement_log, seed_a_log, seed_b_log, offline_log,
                paths["recovery"], 10, 14,
            )

    def test_valid_evidence_is_deterministic(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first, second)
        self.assertTrue(first["replica_failure_recovery_proven"])
        self.assertEqual(len(first["direct_payout_outputs"]), 2)

    def test_coinbase_output_substitution_fails(self):
        def mutate(_receipts, _plan, block):
            block["tx"][0]["vout"][0]["scriptPubKey"]["hex"] = "53"

        with self.assertRaisesRegex(EVIDENCE.SettlementEvidenceError, "coinbase outputs"):
            self.build(mutate)

    def test_payout_plan_omitting_receipt_fails(self):
        def mutate(_receipts, plan, _block):
            plan["outputs"][1]["receipt_ids"] = ["22" * 32]
            body = {key: value for key, value in plan.items() if key != "payout_plan_commitment_sha256"}
            plan["payout_plan_commitment_sha256"] = EVIDENCE.canonical_hash(body)

        with self.assertRaisesRegex(EVIDENCE.SettlementEvidenceError, "eligible receipt set"):
            self.build(mutate)


if __name__ == "__main__":
    unittest.main()
