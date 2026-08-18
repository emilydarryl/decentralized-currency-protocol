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
    }


class ReceiptValidationTests(unittest.TestCase):
    def test_valid_header_receipt_is_normalized(self):
        normalized = COORDINATOR.validate_receipt(valid_receipt())
        self.assertEqual(normalized["format"], "soveroot-labnet-work-receipt-v0")
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

    def test_ledger_is_append_only_json_lines(self):
        normalized = COORDINATOR.validate_receipt(valid_receipt())
        with tempfile.TemporaryDirectory() as directory:
            ledger = pathlib.Path(directory) / "receipts.jsonl"
            COORDINATOR.append_receipt(ledger, normalized)
            COORDINATOR.append_receipt(ledger, normalized)
            lines = ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0]), normalized)
        self.assertEqual(json.loads(lines[1]), normalized)

    def test_reporter_and_http_coordinator_interoperate(self):
        receipt = valid_receipt()
        header = bytes.fromhex(receipt["header_hex"])
        digest = bytes.fromhex(receipt["hash"])[::-1]
        with tempfile.TemporaryDirectory() as directory:
            ledger = pathlib.Path(directory) / "receipts.jsonl"
            server = COORDINATOR.HTTPServer(("127.0.0.1", 0), COORDINATOR.AccountingHandler)
            server.ledger = ledger
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
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            lines = ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(reporter.delivered, 1)
        self.assertEqual(reporter.failed, 0)
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
