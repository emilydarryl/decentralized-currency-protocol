#!/usr/bin/env python3

import importlib.util
import json
import pathlib
import sys
import tempfile
import threading
import unittest


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


class ReceiptValidationTests(unittest.TestCase):
    def test_valid_header_receipt_is_normalized(self):
        normalized = COORDINATOR.validate_receipt(valid_receipt())
        self.assertEqual(normalized["format"], "soveroot-labnet-work-receipt-v1")
        self.assertEqual(normalized["chain"], "labnet")
        self.assertTrue(normalized["block_candidate"])

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


if __name__ == "__main__":
    unittest.main()
