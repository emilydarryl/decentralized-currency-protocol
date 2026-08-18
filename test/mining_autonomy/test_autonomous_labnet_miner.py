#!/usr/bin/env python3

import importlib.util
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

    def test_merkle_root_duplicates_an_odd_leaf(self):
        leaves = [bytes([value]) * 32 for value in (1, 2, 3)]
        first = MINER.hash256(leaves[0] + leaves[1])
        second = MINER.hash256(leaves[2] + leaves[2])
        self.assertEqual(MINER.merkle_root(leaves), MINER.hash256(first + second))

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
            )
        self.assertEqual(reporter.delivered, 0)
        self.assertEqual(reporter.failed, 1)


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
