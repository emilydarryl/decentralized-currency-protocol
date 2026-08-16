# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Consistency checks for the public PoW v1 independent-research call."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CALL_PATH = ROOT / "contrib" / "pow_research_v1" / "independent_research_call_v0.json"
CHALLENGE_PATH = ROOT / "contrib" / "pow_research_v1" / "external_attack_challenge_v0.json"


class IndependentResearchCallV1Test(unittest.TestCase):
    def setUp(self) -> None:
        self.call = json.loads(CALL_PATH.read_text(encoding="utf-8"))
        self.challenge = json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))

    def test_call_matches_frozen_challenge(self) -> None:
        self.assertEqual(
            self.call["format"], "soveroot-pow-v1-independent-research-call-v0"
        )
        self.assertEqual(self.call["version"], "0.1")
        self.assertEqual(self.call["status"], "OPEN")
        summary = self.call["challenge"]
        self.assertEqual(summary["path"], str(CHALLENGE_PATH.relative_to(ROOT)).replace("\\", "/"))
        self.assertEqual(summary["version"], self.challenge["version"])
        self.assertEqual(
            summary["memory_budget_bytes"],
            self.challenge["memory_policy"]["total_attack_budget_bytes"],
        )
        self.assertEqual(
            summary["fresh_cases_per_track"],
            self.challenge["case_policy"]["fresh_case_count"],
        )
        self.assertEqual(
            summary["screening_operation_limit"],
            self.challenge["tracks"]["screening"]["operation_limit"],
        )
        self.assertEqual(
            summary["completion_operation_limit"],
            self.challenge["tracks"]["completion"]["operation_limit"],
        )
        self.assertEqual(set(self.call["tracks"]), set(self.challenge["tracks"]))

    def test_every_entry_point_exists(self) -> None:
        for label, path in self.call["entry_points"].items():
            with self.subTest(label=label, path=path):
                self.assertIsInstance(path, str)
                self.assertTrue(path)
                self.assertTrue((ROOT / path).is_file())

    def test_roles_cover_commit_review_execution_and_evidence(self) -> None:
        self.assertEqual(
            set(self.call["roles"]),
            {
                "attacker",
                "case_evaluator",
                "code_reviewer",
                "execution_reviewer",
                "evidence_reviewer",
            },
        )
        disclosures = set(self.call["independence_policy"]["required_disclosures"])
        self.assertIn("copied code", disclosures)
        self.assertIn("prior collaboration", disclosures)
        self.assertIn("financial or employment conflicts", disclosures)

    def test_call_is_fail_closed_and_makes_no_reward_claim(self) -> None:
        safety = self.call["safety_policy"]
        self.assertFalse(safety["execute_submissions_in_project_ci"])
        self.assertEqual(
            safety["required_execution_environment"], "disposable and network-disabled"
        )
        self.assertTrue(safety["forbid_credentials_and_personal_data"])
        self.assertTrue(all(value is False for value in self.call["reward_policy"].values()))

        evidence = self.call["evidence_policy"]
        self.assertTrue(evidence["retain_all_rows"])
        self.assertFalse(evidence["no_success_is_security_proof"])
        self.assertFalse(evidence["artifact_validation_proves_physical_memory"])
        self.assertEqual(evidence["current_gate_state"], "OPEN")
        self.assertEqual(evidence["current_gate_assessment"], "NOT_ASSESSED")
        self.assertTrue(all(value == 0 for value in self.call["public_counts"].values()))

    def test_public_guidance_preserves_core_warnings(self) -> None:
        researcher_guide = (ROOT / self.call["entry_points"]["researcher_guide"]).read_text(
            encoding="utf-8"
        )
        evaluator_runbook = (ROOT / self.call["entry_points"]["evaluator_runbook"]).read_text(
            encoding="utf-8"
        )
        submission_template = (
            ROOT / self.call["entry_points"]["submission_template"]
        ).read_text(encoding="utf-8")
        evaluator_template = (
            ROOT / self.call["entry_points"]["evaluator_template"]
        ).read_text(encoding="utf-8")

        self.assertIn("no bounty", researcher_guide.lower())
        self.assertIn("does not establish security", researcher_guide.lower())
        self.assertIn("never compiles or executes submitted attack code", researcher_guide)
        self.assertIn("disposable, network-disabled environment", evaluator_runbook)
        self.assertIn("Do not use project CI", evaluator_runbook)
        self.assertIn("evaluator-salt commitment", submission_template.lower())
        self.assertIn("will not run untrusted submissions", evaluator_template)


if __name__ == "__main__":
    unittest.main()
