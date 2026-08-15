# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Tests for the external PoW attack-challenge artifact contract."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest

from contrib.pow_research_v1.external_attack_challenge import (
    ChallengeError,
    RESULTS_FORMAT,
    SUBMISSION_FORMAT,
    build_case_set,
    build_fresh_case_set,
    derive_fresh_seed_indices,
    evaluator_salt_commitment,
    load_challenge,
    validate_case_set,
    validate_submission,
    verify_results,
)
from contrib.pow_research_v1.powvm import Params, evaluate, prepare_epoch


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "contrib" / "pow_research_v1" / "external_attack_submission_template_v0.json"
QUALIFICATION = ROOT / "contrib" / "pow_research_v1" / "vectors" / "external_attack_qualification_v0.json"


def valid_submission() -> dict[str, object]:
    return {
        "format": SUBMISSION_FORMAT,
        "challenge_version": "0.1",
        "status": "SUBMISSION",
        "submission_id": "independent-test-1",
        "authors": ["Test Researcher"],
        "contact": "public@example.invalid",
        "source_url": "https://example.invalid/source",
        "source_revision": "1" * 40,
        "license": "MIT",
        "tracks": ["screening", "completion"],
        "entrypoint_argv": ["./attacker", "--request", "{request}", "--output", "{output}"],
        "strategy_summary": "Independent bounded regeneration policy.",
        "relationship_to_prior_work": "No repository attacker code copied.",
        "memory_model": {
            "declared_peak_attack_bytes": 131072,
            "external_storage_bytes": 0,
            "dynamic_allocation_after_start": False,
            "worker_threads": 1,
            "allocations": [
                {"name": "arena", "bytes": 126976, "purpose": "attack state"},
                {"name": "allocator", "bytes": 4096, "purpose": "allocator reserve"},
            ],
        },
        "operation_model": {
            "counter_fields": [
                "logical_value_requests",
                "replay_iterations",
                "metadata_probes",
                "checkpoint_probes",
                "other_charged_operations",
            ],
            "other_charged_operations_mapping": "All other attack-policy work.",
        },
        "build_argv": [["c++", "attacker.cpp", "-o", "attacker"]],
        "limitations": ["Test fixture only."],
        "submitter_salt_hex": "2" * 64,
    }


def empty_counts() -> dict[str, int]:
    return {
        "logical_value_requests": 0,
        "replay_iterations": 0,
        "metadata_probes": 0,
        "checkpoint_probes": 0,
        "other_charged_operations": 0,
    }


class ExternalAttackChallengeV1Test(unittest.TestCase):
    def setUp(self) -> None:
        self.challenge = load_challenge()
        self.submission = valid_submission()

    def test_template_and_complete_submission_validate(self) -> None:
        template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(
            validate_submission(template, self.challenge, allow_template=True),
            {"valid_template": True, "valid_submission": False},
        )
        summary = validate_submission(self.submission, self.challenge)
        self.assertTrue(summary["valid_submission"])
        self.assertEqual(summary["declared_peak_attack_bytes"], 131072)

    def test_memory_ledger_and_entrypoint_are_fail_closed(self) -> None:
        bad_memory = copy.deepcopy(self.submission)
        bad_memory["memory_model"]["allocations"][0]["bytes"] -= 1  # type: ignore[index]
        with self.assertRaisesRegex(ChallengeError, "allocation bytes"):
            validate_submission(bad_memory, self.challenge)
        bad_entrypoint = copy.deepcopy(self.submission)
        bad_entrypoint["entrypoint_argv"] = ["./attacker"]
        with self.assertRaisesRegex(ChallengeError, "placeholders"):
            validate_submission(bad_entrypoint, self.challenge)

    def test_case_sets_are_deterministic_and_committed(self) -> None:
        first = build_case_set(self.challenge, "screening", [8, 11])
        second = build_case_set(self.challenge, "screening", [8, 11])
        self.assertEqual(first, second)
        self.assertTrue(validate_case_set(first, self.challenge)["valid_case_set"])
        tampered = copy.deepcopy(first)
        tampered["cases"][0]["nonce"] = 1  # type: ignore[index]
        with self.assertRaisesRegex(ChallengeError, "commitment mismatch"):
            validate_case_set(tampered, self.challenge)

    def test_committed_qualification_cases_match_generator(self) -> None:
        committed = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
        self.assertEqual(
            committed,
            build_case_set(self.challenge, "qualification", [0, 1, 2]),
        )
        self.assertTrue(validate_case_set(committed, self.challenge)["valid_case_set"])

    def test_commit_reveal_fresh_cases_are_deterministic_and_unseen(self) -> None:
        evaluator_salt = bytes.fromhex("3" * 64)
        first = build_fresh_case_set(
            self.challenge, "screening", self.submission, evaluator_salt
        )
        second = build_fresh_case_set(
            self.challenge, "screening", self.submission, evaluator_salt
        )
        self.assertEqual(first, second)
        self.assertEqual(
            first["selection"]["evaluator_salt_commitment"],
            evaluator_salt_commitment(evaluator_salt),
        )
        selected = [case["seed_index"] for case in first["cases"]]
        self.assertEqual(len(selected), 8)
        self.assertFalse(set(selected) & set(range(16)))
        self.assertEqual(
            selected,
            derive_fresh_seed_indices(
                evaluator_salt=evaluator_salt,
                submitter_salt=bytes.fromhex(self.submission["submitter_salt_hex"]),
                source_revision=self.submission["source_revision"],
                excluded_indices=list(range(16)),
                count=8,
            ),
        )
        self.assertTrue(validate_case_set(first, self.challenge)["valid_case_set"])
        tampered = copy.deepcopy(first)
        tampered["selection"]["evaluator_salt_hex"] = "4" * 64
        unsigned = dict(tampered)
        unsigned.pop("case_set_commitment")
        tampered["case_set_commitment"] = hashlib.sha3_384(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        with self.assertRaisesRegex(ChallengeError, "commitment mismatch"):
            validate_case_set(tampered, self.challenge)

    def test_qualification_exact_proof_is_independently_checked(self) -> None:
        case_set = build_case_set(self.challenge, "qualification", [0])
        request = case_set["cases"][0]
        params = Params(**request["params"])
        proof = evaluate(
            prepare_epoch(bytes.fromhex(request["seed"]), params),
            bytes.fromhex(request["header"]),
            request["nonce"],
        ).to_dict()
        results = {
            "format": RESULTS_FORMAT,
            "challenge_version": "0.1",
            "submission_id": self.submission["submission_id"],
            "source_revision": self.submission["source_revision"],
            "track": "qualification",
            "case_set_commitment": case_set["case_set_commitment"],
            "cases": [{
                "case_id": request["case_id"],
                "status": "COMPLETE",
                "completed_iterations": request["canonical_iterations"],
                "accounted_peak_attack_bytes": 0,
                "external_storage_bytes": 0,
                "operation_counts": empty_counts(),
                "total_operations": 0,
                "transcript_commitment": hashlib.sha3_384(b"").hexdigest(),
                "execution_result": proof,
            }],
        }
        summary = verify_results(results, self.submission, case_set, self.challenge)
        self.assertEqual(summary["complete_proofs"], 1)
        self.assertFalse(summary["memory_claim_audited"])
        bad = copy.deepcopy(results)
        bad["cases"][0]["execution_result"]["digest"] = "0" * 96
        with self.assertRaisesRegex(ChallengeError, "canonical proof mismatch"):
            verify_results(bad, self.submission, case_set, self.challenge)

    def test_partial_screen_preserves_accounting_without_a_proof(self) -> None:
        single_case_challenge = copy.deepcopy(self.challenge)
        single_case_challenge["case_policy"]["fresh_case_count"] = 1
        case_set = build_fresh_case_set(
            single_case_challenge,
            "screening",
            self.submission,
            bytes.fromhex("5" * 64),
        )
        request = case_set["cases"][0]
        counts = empty_counts()
        counts.update({
            "logical_value_requests": 10,
            "replay_iterations": 4_999_870,
            "metadata_probes": 30,
            "checkpoint_probes": 40,
            "other_charged_operations": 50,
        })
        results = {
            "format": RESULTS_FORMAT,
            "challenge_version": "0.1",
            "submission_id": self.submission["submission_id"],
            "source_revision": self.submission["source_revision"],
            "track": "screening",
            "case_set_commitment": case_set["case_set_commitment"],
            "cases": [{
                "case_id": request["case_id"],
                "status": "EXHAUSTED",
                "completed_iterations": 777,
                "accounted_peak_attack_bytes": 131072,
                "external_storage_bytes": 0,
                "operation_counts": counts,
                "total_operations": sum(counts.values()),
                "transcript_commitment": hashlib.sha3_384(b"partial").hexdigest(),
                "execution_result": None,
            }],
        }
        summary = verify_results(
            results, self.submission, case_set, single_case_challenge
        )
        self.assertEqual(summary["complete_proofs"], 0)
        self.assertEqual(summary["maximum_completed_iterations"], 777)
        bad_total = copy.deepcopy(results)
        bad_total["cases"][0]["total_operations"] += 1
        with self.assertRaisesRegex(ChallengeError, "operation invariant"):
            verify_results(
                bad_total, self.submission, case_set, single_case_challenge
            )


if __name__ == "__main__":
    unittest.main()
