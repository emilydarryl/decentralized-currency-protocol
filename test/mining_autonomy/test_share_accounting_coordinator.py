#!/usr/bin/env python3

import importlib.util
import json
import pathlib
import sys
import tempfile
import threading
import unittest
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MINER = load_module(
    "coordinator_test_miner",
    ROOT / "contrib" / "mining_autonomy" / "autonomous_labnet_miner.py",
)
COORDINATOR = load_module(
    "share_accounting_coordinator",
    ROOT / "contrib" / "mining_autonomy" / "share_accounting_coordinator.py",
)


def valid_receipt():
    prefix = b"\x04\x00\x00\x00" + b"\x00" * 64 + (1).to_bytes(4, "little") + (0x207FFFFF).to_bytes(4, "little")
    header, nonce, digest = MINER.solve_header(prefix, 0x207FFFFF, 100)
    return {
        "chain": "labnet",
        "worker": "unit-worker",
        "height": 1,
        "previous_block_hash": "00" * 32,
        "header_hex": header.hex(),
        "nonce": nonce,
        "hash": digest[::-1].hex(),
        "block_candidate": True,
        "payout_script_hex": "51",
        "template_commitment_sha256": "22" * 32,
    }


def distinct_receipt(marker, worker, payout_script):
    previous_block_hash = f"{marker:02x}" * 32
    prefix = (
        b"\x04\x00\x00\x00"
        + bytes.fromhex(previous_block_hash)[::-1]
        + bytes([marker]) * 32
        + marker.to_bytes(4, "little")
        + (0x207FFFFF).to_bytes(4, "little")
    )
    header, nonce, digest = MINER.solve_header(prefix, 0x207FFFFF, 100)
    return {
        "chain": "labnet",
        "worker": worker,
        "height": marker,
        "previous_block_hash": previous_block_hash,
        "header_hex": header.hex(),
        "nonce": nonce,
        "hash": digest[::-1].hex(),
        "block_candidate": True,
        "payout_script_hex": payout_script,
        "template_commitment_sha256": f"{marker + 32:02x}" * 32,
    }


class ReceiptValidationTests(unittest.TestCase):
    def test_valid_header_receipt_is_normalized(self):
        normalized = COORDINATOR.validate_receipt(valid_receipt())
        self.assertEqual(normalized["format"], "soveroot-labnet-work-receipt-v2")
        self.assertEqual(normalized["chain"], "labnet")
        self.assertTrue(normalized["block_candidate"])
        self.assertEqual(len(normalized["work_id_sha256"]), 64)

    def test_forged_hash_is_rejected(self):
        receipt = valid_receipt()
        receipt["hash"] = "11" * 32
        with self.assertRaisesRegex(COORDINATOR.AccountingError, "hash does not match"):
            COORDINATOR.validate_receipt(receipt)

    def test_non_labnet_receipt_is_rejected(self):
        receipt = valid_receipt()
        receipt["chain"] = "regtest"
        with self.assertRaisesRegex(COORDINATOR.AccountingError, "chain=labnet"):
            COORDINATOR.validate_receipt(receipt)

    def test_duplicate_receipt_is_rejected(self):
        normalized = COORDINATOR.validate_receipt(valid_receipt())
        with tempfile.TemporaryDirectory() as directory:
            ledger = pathlib.Path(directory) / "receipts.jsonl"
            COORDINATOR.append_receipt(ledger, normalized)
            with self.assertRaisesRegex(COORDINATOR.AccountingError, "duplicate"):
                COORDINATOR.append_receipt(ledger, normalized)
            lines = ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]), normalized)

    def test_one_proof_cannot_be_reassigned_to_another_worker_or_script(self):
        first = COORDINATOR.validate_receipt(valid_receipt())
        reassigned = valid_receipt()
        reassigned["worker"] = "other-worker"
        reassigned["payout_script_hex"] = "52"
        second = COORDINATOR.validate_receipt(reassigned)
        self.assertEqual(first["work_id_sha256"], second["work_id_sha256"])
        self.assertNotEqual(first["receipt_id_sha256"], second["receipt_id_sha256"])
        with self.assertRaisesRegex(COORDINATOR.AccountingError, "work identity"):
            COORDINATOR.merge_receipts([first], [second])

    def test_claims_bind_work_to_payout_script_without_custody(self):
        first = COORDINATOR.validate_receipt(valid_receipt())
        second_document = valid_receipt()
        second_document["worker"] = "second-worker"
        second_document["payout_script_hex"] = "52"
        second_document["header_hex"] = (
            bytes.fromhex(second_document["header_hex"][:152])
            + (second_document["nonce"] + 1).to_bytes(4, "little")
        ).hex()
        header = bytes.fromhex(second_document["header_hex"])
        digest = COORDINATOR.hash256(header)
        second_document["nonce"] += 1
        second_document["hash"] = digest[::-1].hex()
        second_document["block_candidate"] = (
            int.from_bytes(digest, "little")
            <= COORDINATOR.compact_target(int.from_bytes(header[72:76], "little"))
        )
        second = COORDINATOR.validate_receipt(second_document)
        claims = COORDINATOR.build_claims([first, second])
        self.assertEqual(claims["custody"], "none")
        self.assertEqual(claims["settlement_status"], "accounting_claims_only_not_money")
        self.assertTrue(all("payout_script_hex" in claim for claim in claims["claims"]))

    def test_payout_plan_is_deterministic_and_conserves_coinbase(self):
        receipts = [
            COORDINATOR.validate_receipt(distinct_receipt(1, "worker-a", "51")),
            COORDINATOR.validate_receipt(distinct_receipt(2, "worker-b", "52")),
            COORDINATOR.validate_receipt(distinct_receipt(3, "worker-b", "52")),
        ]
        first = COORDINATOR.build_payout_plan(receipts, 5_000_000_000)
        second = COORDINATOR.build_payout_plan(list(reversed(receipts)), 5_000_000_000)
        self.assertEqual(first, second)
        self.assertEqual(sum(output["value"] for output in first["outputs"]), 5_000_000_000)
        self.assertEqual([output["payout_script_hex"] for output in first["outputs"]], ["51", "52"])
        self.assertGreater(first["outputs"][1]["value"], first["outputs"][0]["value"])
        commitment = first.pop("payout_plan_commitment_sha256")
        self.assertEqual(commitment, COORDINATOR.canonical_hash(first))

    def test_dust_payout_plan_fails_closed(self):
        receipts = [
            COORDINATOR.validate_receipt(distinct_receipt(1, "worker-a", "51")),
            COORDINATOR.validate_receipt(distinct_receipt(2, "worker-b", "52")),
        ]
        with self.assertRaisesRegex(COORDINATOR.AccountingError, "below 546"):
            COORDINATOR.build_payout_plan(receipts, 1_000)

    def test_reporter_and_http_coordinator_interoperate(self):
        receipt = valid_receipt()
        header = bytes.fromhex(receipt["header_hex"])
        digest = bytes.fromhex(receipt["hash"])[::-1]
        with tempfile.TemporaryDirectory() as directory:
            ledger = pathlib.Path(directory) / "receipts.jsonl"
            claims = pathlib.Path(directory) / "claims.json"
            server = COORDINATOR.HTTPServer(("127.0.0.1", 0), COORDINATOR.AccountingHandler)
            server.ledger = ledger
            server.claims = claims
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                reporter = MINER.ShareReporter(
                    f"http://127.0.0.1:{server.server_port}/share",
                    "integration-worker",
                    1,
                    1.0,
                )
                reporter.observe(
                    header,
                    receipt["nonce"],
                    digest,
                    True,
                    height=receipt["height"],
                    previous_block_hash=receipt["previous_block_hash"],
                    payout_script_hex=receipt["payout_script_hex"],
                    template_commitment_sha256=receipt["template_commitment_sha256"],
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            lines = ledger.read_text(encoding="utf-8").splitlines()
            claim_document = json.loads(claims.read_text(encoding="utf-8"))
        self.assertEqual(reporter.delivered, 1)
        self.assertEqual(reporter.failed, 0)
        self.assertEqual(len(lines), 1)
        self.assertEqual(claim_document["custody"], "none")

    def test_two_http_replicas_reconcile_to_identical_sets_and_plans(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            servers = []
            threads = []
            endpoints = []
            for name in ("a", "b"):
                ledger = root / f"{name}.jsonl"
                claims = root / f"{name}-claims.json"
                server = COORDINATOR.HTTPServer(("127.0.0.1", 0), COORDINATOR.AccountingHandler)
                server.ledger = ledger
                server.claims = claims
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                servers.append(server)
                threads.append(thread)
                endpoints.append(f"http://127.0.0.1:{server.server_port}")
            COORDINATOR.append_receipt(
                servers[0].ledger,
                COORDINATOR.validate_receipt(distinct_receipt(1, "worker-a", "51")),
            )
            COORDINATOR.append_receipt(
                servers[1].ledger,
                COORDINATOR.validate_receipt(distinct_receipt(2, "worker-b", "52")),
            )
            try:
                for target, peer in ((endpoints[0], endpoints[1]), (endpoints[1], endpoints[0])):
                    request = urllib.request.Request(
                        f"{target}/reconcile",
                        data=json.dumps({"peer_endpoint": peer}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=2) as response:
                        self.assertEqual(response.status, 202)
                sets = [COORDINATOR.fetch_receipt_set(endpoint) for endpoint in endpoints]
                plans = []
                for endpoint in endpoints:
                    with urllib.request.urlopen(
                        f"{endpoint}/plan?coinbase_value=5000000000", timeout=2
                    ) as response:
                        plans.append(json.load(response))
            finally:
                for server in servers:
                    server.shutdown()
                    server.server_close()
                for thread in threads:
                    thread.join(timeout=2)
        self.assertEqual(sets[0], sets[1])
        self.assertEqual(plans[0], plans[1])
        self.assertEqual(sets[0]["receipt_count"], 2)


if __name__ == "__main__":
    unittest.main()
