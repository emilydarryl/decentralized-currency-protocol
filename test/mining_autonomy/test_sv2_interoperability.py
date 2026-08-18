#!/usr/bin/env python3

import json
import os
import pathlib
import socket
import subprocess
import tempfile
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contrib" / "mining_autonomy" / "vectors" / "sv2_interoperability_v0.json"
REFERENCE_MINER = ROOT / "contrib" / "mining_autonomy" / "autonomous_labnet_miner.py"
RUNNER = ROOT / "contrib" / "mining_autonomy" / "run_interoperability.py"


def free_loopback_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def load_runner():
    import importlib.util

    spec = importlib.util.spec_from_file_location("soveroot_interop_runner", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load interoperability runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InteroperabilityGateTests(unittest.TestCase):
    def test_matching_failed_negative_vector_still_fails_gate(self):
        runner = load_runner()
        report = {
            "authentication": {},
            "wire_transcript": [],
            "template_commitment_sha256": "commitment",
            "negative_results": [{"name": "bad", "passed": False}],
            "solved_block": {"block_hex": "00"},
        }
        with self.assertRaises(runner.InteroperabilityError):
            runner.compare(report, report, report["solved_block"])


class Sv2InteroperabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reference = os.environ.get("SOVEROOT_SV2_HELPER")
        independent = os.environ.get("SOVEROOT_SV2_INDEPENDENT_MINER")
        if not reference or not independent:
            raise unittest.SkipTest(
                "SOVEROOT_SV2_HELPER and SOVEROOT_SV2_INDEPENDENT_MINER are required"
            )
        cls.reference = pathlib.Path(reference).resolve()
        cls.independent = pathlib.Path(independent).resolve()
        if not cls.reference.is_file() or not cls.independent.is_file():
            raise unittest.SkipTest("interoperability binaries were not found")
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_byte_exact_reports_and_blocks_match(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = pathlib.Path(directory) / "evidence.json"
            completed = subprocess.run(
                [
                    "python3" if os.name != "nt" else "python",
                    RUNNER,
                    "--reference-helper",
                    self.reference,
                    "--independent-miner",
                    self.independent,
                    "--reference-miner",
                    REFERENCE_MINER,
                    "--fixture",
                    FIXTURE,
                    "--output",
                    evidence,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertIn("Exact authentication, wire", completed.stdout)
            report = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertTrue(report["all_exact_results_match"])
            self.assertTrue(all(report["comparisons"].values()))
            self.assertEqual(len(report["reference"]["wire_transcript"]), 8)

    def run_live(self, mode, authority_override=None):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            authority = root / "authority.json"
            ready = root / "ready.json"
            candidate = root / "candidate.json"
            candidate.write_text(
                json.dumps(self.fixture["candidate"], separators=(",", ":"), sort_keys=True),
                encoding="utf-8",
            )
            public_key = subprocess.run(
                [self.reference, "generate-authority", "--output", authority],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            endpoint = f"127.0.0.1:{free_loopback_port()}"
            server = subprocess.Popen(
                [
                    self.reference,
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
                        self.independent,
                        "declare",
                        "--candidate",
                        candidate,
                        "--endpoint",
                        endpoint,
                        "--authority-public-key",
                        authority_override or public_key,
                        "--timeout-ms",
                        "1000",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return json.loads(completed.stdout)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
                if server.stderr is not None:
                    server.stderr.close()

    def test_independent_manual_codec_reaches_reference_coordinator(self):
        result = self.run_live("accept")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["transport_status"], "authenticated")
        self.assertEqual(result["job_id"], 9)
        message_types = [frame["message_type"] for frame in result["transcript"]]
        self.assertIn(0x57, message_types)
        self.assertIn(0x22, message_types)
        self.assertIn(0x23, message_types)

    def test_reference_rejection_forces_independent_fallback(self):
        result = self.run_live("reject")
        self.assertEqual(result["status"], "direct_fallback")
        self.assertEqual(result["transport_status"], "authenticated")
        self.assertEqual(result["reason"], "declaration:policy-rejection")

    def test_wrong_authority_fails_before_any_sv2_message(self):
        with tempfile.TemporaryDirectory() as directory:
            wrong = pathlib.Path(directory) / "wrong.json"
            wrong_key = subprocess.run(
                [self.reference, "generate-authority", "--output", wrong],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            result = self.run_live("accept", authority_override=wrong_key)
        self.assertEqual(result["status"], "direct_fallback")
        self.assertEqual(result["transport_status"], "failed")
        self.assertIn("noise-authentication", result["reason"])
        self.assertEqual(result["transcript"], [])


if __name__ == "__main__":
    unittest.main()
