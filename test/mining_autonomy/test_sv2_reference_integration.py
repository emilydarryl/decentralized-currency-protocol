#!/usr/bin/env python3

import hashlib
import json
import os
import pathlib
import socket
import subprocess
import tempfile
import time
import unittest


def free_loopback_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def candidate():
    transaction = bytes.fromhex("0102")
    transaction_hash = hashlib.sha256(hashlib.sha256(transaction).digest()).digest()
    return {
        "chain": "labnet",
        "previous_block_hash": "00" * 32,
        "version": 4,
        "bits": 0x207FFFFF,
        "curtime": 1,
        "coinbase_tx_version": 2,
        "coinbase_prefix_hex": "0200000001" + "00" * 32 + "ffffffff01",
        "coinbase_suffix_hex": "ffffffff0100f2052a01000000015100000000",
        "coinbase_outputs_hex": "0100f2052a010000000151",
        "coinbase_tx_input_n_sequence": 0xFFFFFFFF,
        "coinbase_tx_locktime": 0,
        "transaction_ids": [transaction_hash[::-1].hex()],
        "transaction_data": [transaction.hex()],
        "coinbase_merkle_path": [transaction_hash.hex()],
        "target_le_hex": "ff" * 31 + "7f",
        "template_commitment_sha256": "11" * 32,
    }


class Sv2ReferenceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("SOVEROOT_SV2_HELPER")
        if not configured:
            raise unittest.SkipTest("SOVEROOT_SV2_HELPER is not set")
        cls.helper = pathlib.Path(configured).resolve()
        if not cls.helper.is_file():
            raise unittest.SkipTest(f"Stratum V2 helper not found: {cls.helper}")

    def run_scenario(self, mode, authority_override=None):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            authority = root / "authority.json"
            ready = root / "ready.json"
            generated = subprocess.run(
                [self.helper, "generate-authority", "--output", authority],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            public_key = generated.stdout.strip()
            endpoint = f"127.0.0.1:{free_loopback_port()}"
            server = subprocess.Popen(
                [
                    self.helper,
                    "serve",
                    "--endpoint",
                    endpoint,
                    "--authority-file",
                    authority,
                    "--mode",
                    mode,
                    "--ready-file",
                    ready,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                for _ in range(100):
                    if ready.is_file():
                        break
                    if server.poll() is not None:
                        self.fail(f"coordinator stopped early: {server.stderr.read()}")
                    time.sleep(0.02)
                self.assertTrue(ready.is_file(), "coordinator did not become ready")
                completed = subprocess.run(
                    [
                        self.helper,
                        "declare",
                        "--endpoint",
                        endpoint,
                        "--authority-public-key",
                        authority_override or public_key,
                        "--timeout-ms",
                        "1000",
                    ],
                    input=json.dumps(candidate(), separators=(",", ":"), sort_keys=True),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return json.loads(completed.stdout), public_key
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
                if server.stderr is not None:
                    server.stderr.close()

    def test_authenticated_acceptance_reaches_custom_job_success(self):
        result, _ = self.run_scenario("accept")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["transport_status"], "authenticated")
        self.assertEqual(result["job_id"], 9)
        self.assertEqual(result["template_commitment_sha256"], "11" * 32)

    def test_declaration_rejection_enters_direct_fallback(self):
        result, _ = self.run_scenario("reject")
        self.assertEqual(result["status"], "direct_fallback")
        self.assertEqual(result["transport_status"], "authenticated")
        self.assertEqual(result["reason"], "declaration:policy-rejection")

    def test_coordinator_loss_enters_direct_fallback(self):
        result, _ = self.run_scenario("drop")
        self.assertEqual(result["status"], "direct_fallback")
        self.assertEqual(result["transport_status"], "authenticated")
        self.assertIn(
            result["reason"],
            {"declaration:transport:connection-closed", "declaration:transport:timeout"},
        )

    def test_wrong_pinned_authority_cannot_authenticate(self):
        with tempfile.TemporaryDirectory() as directory:
            wrong_file = pathlib.Path(directory) / "wrong.json"
            wrong = subprocess.run(
                [self.helper, "generate-authority", "--output", wrong_file],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            result, _ = self.run_scenario("accept", authority_override=wrong)
        self.assertEqual(result["status"], "direct_fallback")
        self.assertEqual(result["transport_status"], "failed")
        self.assertIn("noise-authentication", result["reason"])


if __name__ == "__main__":
    unittest.main()
