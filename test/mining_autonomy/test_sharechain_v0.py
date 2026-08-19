#!/usr/bin/env python3

import copy
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REFERENCE = load_module(
    "sharechain_v0_reference_test",
    ROOT / "contrib" / "mining_autonomy" / "sharechain_v0.py",
)
INDEPENDENT = load_module(
    "sharechain_v0_independent_test",
    ROOT / "contrib" / "mining_autonomy" / "independent_sharechain_v0.py",
)


class SharechainCorpusTests(unittest.TestCase):
    def test_generated_corpus_is_complete_and_valid(self):
        corpus = REFERENCE.build_corpus()
        results = REFERENCE.validate_corpus(corpus)
        self.assertEqual({item["name"] for item in results}, REFERENCE.REQUIRED_SCENARIOS)
        self.assertEqual(len(results), 15)

    def test_checked_in_corpus_matches_generator_exactly(self):
        checked_in = json.loads(REFERENCE.VECTOR_PATH.read_text(encoding="utf-8"))
        self.assertEqual(checked_in, REFERENCE.build_corpus())

    def test_independent_validator_matches_every_reference_result(self):
        corpus = REFERENCE.build_corpus()
        reference_results = REFERENCE.validate_corpus(corpus)
        independent_results = INDEPENDENT.verify_corpus(corpus)
        self.assertEqual(independent_results, reference_results)

    def test_profile_has_real_nonblock_shares_below_easier_share_target(self):
        self.assertGreater(REFERENCE.SHARE_TARGET, REFERENCE.NETWORK_TARGET)
        scenario = next(
            item for item in REFERENCE.build_corpus()["scenarios"]
            if item["name"] == "valid_linear_chain"
        )
        self.assertTrue(any(share["block_candidate"] is False for share in scenario["shares"]))
        for share in scenario["shares"]:
            proof = int.from_bytes(REFERENCE.hash256(bytes.fromhex(share["header_hex"])), "little")
            self.assertLessEqual(proof, REFERENCE.SHARE_TARGET)

    def test_tie_break_selects_lowest_share_identifier(self):
        scenario = next(
            item for item in REFERENCE.build_corpus()["scenarios"]
            if item["name"] == "equal_work_tie_break"
        )
        root_id = scenario["shares"][0]["share_id_sha256"]
        tips = sorted(share["share_id_sha256"] for share in scenario["shares"] if share["share_id_sha256"] != root_id)
        self.assertEqual(scenario["expected"]["state"]["selected_tip_share_id"], tips[0])

    def test_finality_and_payout_window_exclude_tip_and_parent(self):
        scenario = next(
            item for item in REFERENCE.build_corpus()["scenarios"]
            if item["name"] == "valid_linear_chain"
        )
        state = scenario["expected"]["state"]
        self.assertEqual(
            state["finalized_share_ids"],
            state["selected_path_share_ids"][:-REFERENCE.FINALITY_DEPTH],
        )
        self.assertEqual(
            state["payout_window_share_ids"],
            state["finalized_share_ids"][-REFERENCE.PAYOUT_WINDOW :],
        )
        self.assertEqual(
            sum(claim["work_units"] for claim in state["payout_claims"]),
            len(state["payout_window_share_ids"]) * REFERENCE.SHARE_WORK_UNITS,
        )

    def test_block_candidate_forces_the_next_trusted_round(self):
        scenario = next(
            item for item in REFERENCE.build_corpus()["scenarios"]
            if item["name"] == "valid_linear_chain"
        )
        block_share = scenario["shares"][2]
        successor = scenario["shares"][3]
        self.assertTrue(block_share["block_candidate"])
        self.assertEqual(successor["round_height"], block_share["round_height"] + 1)
        self.assertEqual(successor["round_previous_block_hash"], block_share["header_hash"])

    def test_stale_extension_after_block_is_rejected(self):
        scenario = next(
            item for item in REFERENCE.build_corpus()["scenarios"]
            if item["name"] == "stale_extension_after_block"
        )
        self.assertEqual(scenario["expected"], {"accepted": False, "reason": "round_transition"})

    def test_reassigned_proof_fails_even_with_valid_share_identifiers(self):
        scenario = next(
            item for item in REFERENCE.build_corpus()["scenarios"]
            if item["name"] == "proof_reassigned_to_other_payout"
        )
        first, reassigned = scenario["shares"][1:]
        self.assertEqual(first["work_id_sha256"], reassigned["work_id_sha256"])
        self.assertNotEqual(first["share_id_sha256"], reassigned["share_id_sha256"])
        self.assertEqual(scenario["expected"], {"accepted": False, "reason": "work_reassigned"})

    def test_rehashed_miner_target_change_still_fails(self):
        scenario = copy.deepcopy(
            next(
                item for item in REFERENCE.build_corpus()["scenarios"]
                if item["name"] == "valid_linear_chain"
            )
        )
        scenario["shares"][1]["share_target_hex"] = "ff" * 32
        REFERENCE.refresh_share_id(scenario["shares"][1])
        self.assertEqual(
            REFERENCE.assess(scenario["shares"], scenario["trusted_rounds"]),
            {"accepted": False, "reason": "share_target_mismatch"},
        )

    def test_reordering_and_restart_reconstruct_identical_state(self):
        corpus = REFERENCE.build_corpus()
        linear = next(item for item in corpus["scenarios"] if item["name"] == "valid_linear_chain")
        delayed = next(item for item in corpus["scenarios"] if item["name"] == "delayed_order_reconstruction")
        restart = next(item for item in corpus["scenarios"] if item["name"] == "restart_reconstruction")
        self.assertEqual(linear["expected"]["state"], delayed["expected"]["state"])
        self.assertEqual(linear["expected"]["state"], restart["expected"]["state"])

    def test_scenario_expectation_cannot_be_changed_without_commitment_failure(self):
        scenario = copy.deepcopy(REFERENCE.build_corpus()["scenarios"][0])
        scenario["expected"] = {"accepted": False, "reason": "rewritten"}
        with self.assertRaisesRegex(REFERENCE.ProfileError, "commitment"):
            REFERENCE.validate_scenario(scenario)

    def test_write_and_check_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "sharechain.json"
            self.assertEqual(REFERENCE.main(["--write", "--path", str(path)]), 0)
            first = path.read_bytes()
            self.assertEqual(REFERENCE.main(["--write", "--path", str(path)]), 0)
            self.assertEqual(first, path.read_bytes())
            self.assertEqual(REFERENCE.main(["--check", "--path", str(path)]), 0)


if __name__ == "__main__":
    unittest.main()
