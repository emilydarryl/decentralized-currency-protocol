#!/usr/bin/env python3

import copy
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "contrib" / "mining_autonomy" / "sv2_job_declaration_vectors.py"
SPEC = importlib.util.spec_from_file_location("sv2_job_declaration_vectors", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VECTORS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VECTORS
SPEC.loader.exec_module(VECTORS)


class CorpusTests(unittest.TestCase):
    def test_generated_corpus_is_valid_and_complete(self):
        corpus = VECTORS.build_corpus()
        VECTORS.validate_corpus(corpus)
        self.assertEqual({item["name"] for item in corpus["scenarios"]}, VECTORS.REQUIRED_SCENARIOS)

    def test_checked_in_vectors_match_generator(self):
        actual = json.loads(VECTORS.VECTOR_PATH.read_text(encoding="utf-8"))
        self.assertEqual(actual, VECTORS.build_corpus())
        VECTORS.validate_corpus(actual)

    def test_tampered_transcript_is_rejected(self):
        scenario = copy.deepcopy(VECTORS.build_scenarios()[0])
        scenario["events"][-1]["job_id"] = "coordinator-substitute"
        with self.assertRaisesRegex(VECTORS.VectorError, "transcript hash mismatch"):
            VECTORS.validate_scenario(scenario)

    def test_rehashed_coordinator_template_substitution_is_rejected(self):
        scenario = copy.deepcopy(VECTORS.build_scenarios()[0])
        scenario["events"].insert(
            -2,
            {
                "seq": len(scenario["events"]) - 1,
                "direction": "coordinator_to_miner",
                "type": "coordinator_created_template",
            },
        )
        for index, item in enumerate(scenario["events"], start=1):
            item["seq"] = index
        unsigned = {key: value for key, value in scenario.items() if key != "transcript_sha256"}
        scenario["transcript_sha256"] = VECTORS.sha256_hex(unsigned)
        with self.assertRaisesRegex(VECTORS.VectorError, "coordinator-created templates are forbidden"):
            VECTORS.validate_scenario(scenario)

    def test_failure_without_direct_fallback_is_rejected(self):
        scenario = copy.deepcopy(
            next(item for item in VECTORS.build_scenarios() if item["name"] == "token_timeout")
        )
        scenario["events"] = [item for item in scenario["events"] if item["type"] != "direct_fallback"]
        for index, item in enumerate(scenario["events"], start=1):
            item["seq"] = index
        unsigned = {key: value for key, value in scenario.items() if key != "transcript_sha256"}
        scenario["transcript_sha256"] = VECTORS.sha256_hex(unsigned)
        with self.assertRaisesRegex(VECTORS.VectorError, "missing ordered event subsequence"):
            VECTORS.validate_scenario(scenario)

    def test_authentication_failure_cannot_continue_coordinator_traffic(self):
        scenario = copy.deepcopy(
            next(item for item in VECTORS.build_scenarios() if item["name"] == "mitm_authentication_failure")
        )
        scenario["events"].insert(
            2,
            {
                "seq": 3,
                "direction": "miner_to_coordinator",
                "type": "setup_connection",
            },
        )
        for index, item in enumerate(scenario["events"], start=1):
            item["seq"] = index
        unsigned = {key: value for key, value in scenario.items() if key != "transcript_sha256"}
        scenario["transcript_sha256"] = VECTORS.sha256_hex(unsigned)
        with self.assertRaisesRegex(VECTORS.VectorError, "traffic continued after failed authentication"):
            VECTORS.validate_scenario(scenario)

    def test_write_and_check_modes_use_deterministic_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "vectors.json"
            original = VECTORS.VECTOR_PATH
            VECTORS.VECTOR_PATH = path
            try:
                self.assertEqual(VECTORS.main(["--write"]), 0)
                first = path.read_bytes()
                self.assertEqual(VECTORS.main(["--write"]), 0)
                self.assertEqual(first, path.read_bytes())
                self.assertEqual(VECTORS.main(["--check"]), 0)
            finally:
                VECTORS.VECTOR_PATH = original


if __name__ == "__main__":
    unittest.main()
