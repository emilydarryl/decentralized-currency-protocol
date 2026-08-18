#!/usr/bin/env python3

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "contrib" / "mining_autonomy" / "build_resilience_evidence.py"
SPEC = importlib.util.spec_from_file_location("build_resilience_evidence", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
EVIDENCE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EVIDENCE
SPEC.loader.exec_module(EVIDENCE)


def fixture_events():
    commitments = [f"{index:064x}" for index in range(1, 8)]
    events = []
    failures = [
        None,
        "declaration:policy-rejection",
        "declaration:transport:connection-closed",
        "declaration:transport:timeout",
        "declaration:request-mismatch",
        "setup:downgrade",
        "transport:connect:refused",
    ]
    for index, commitment in enumerate(commitments):
        events.append(
            {
                "component": "template",
                "event": "miner_template_committed",
                "template_commitment_sha256": commitment,
            }
        )
        events.append(
            {
                "component": "coordination",
                "event": "coordinator_attempt_result",
                "coordinator": "primary",
                "status": "accepted" if failures[index] is None else "direct_fallback",
                "reason": failures[index],
                "template_commitment_sha256": commitment,
            }
        )
        if index != 0:
            events.append(
                {
                    "component": "coordination",
                    "event": "coordinator_attempt_result",
                    "coordinator": "alternate",
                    "status": "direct_fallback" if index == 6 else "accepted",
                    "reason": "transport:connect:refused" if index == 6 else None,
                    "template_commitment_sha256": commitment,
                }
            )
        events.append(
            {
                "component": "declaration",
                "event": "job_declaration_result",
                "status": "direct_fallback" if index == 6 else "accepted",
                "template_commitment_sha256": commitment,
            }
        )
        events.append(
            {
                "component": "publication",
                "event": "direct_submitblock_accepted",
                "block_hash": f"{index + 20:064x}",
                "template_commitment_sha256": commitment,
            }
        )
        events.append(
            {
                "component": "accounting",
                "event": "reporting_summary",
                "delivered": 6,
                "failed": 1 if index == 6 else 0,
            }
        )
    return events


class ResilienceEvidenceTests(unittest.TestCase):
    def write_fixture(self, directory):
        root = pathlib.Path(directory)
        miner = root / "miner.log"
        miner.write_text(
            "".join(json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n" for event in fixture_events()),
            encoding="utf-8",
        )
        claims = root / "claims.json"
        claims.write_text(
            json.dumps(
                {
                    "format": "soveroot-labnet-noncustodial-claims-v0",
                    "custody": "none",
                    "settlement_status": "accounting_claims_only_not_money",
                    "claims": [{"payout_script_hex": "51"}],
                }
            ),
            encoding="utf-8",
        )
        return miner, claims

    def test_complete_evidence_is_canonical_and_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            miner, claims = self.write_fixture(directory)
            first = EVIDENCE.build(miner, claims, 100, 107)
            second = EVIDENCE.build(miner, claims, 100, 107)
        self.assertEqual(first, second)
        self.assertEqual(first["direct_publications"], 7)
        self.assertTrue(all(first["failure_results"].values()))
        self.assertEqual(len(first["events_sha256"]), 64)

    def test_template_substitution_fails_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            miner, claims = self.write_fixture(directory)
            lines = miner.read_text(encoding="utf-8").splitlines()
            event = json.loads(lines[-2])
            event["template_commitment_sha256"] = "ff" * 32
            lines[-2] = json.dumps(event)
            miner.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(EVIDENCE.EvidenceError, "templates"):
                EVIDENCE.build(miner, claims, 100, 107)

    def test_final_block_requires_both_coordinators_to_be_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            miner, claims = self.write_fixture(directory)
            lines = miner.read_text(encoding="utf-8").splitlines()
            events = [json.loads(line) for line in lines]
            events = [
                event
                for event in events
                if not (
                    event.get("event") == "coordinator_attempt_result"
                    and event.get("coordinator") == "alternate"
                    and event.get("template_commitment_sha256") == f"{7:064x}"
                )
            ]
            miner.write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EVIDENCE.EvidenceError, "both configured coordinators"):
                EVIDENCE.build(miner, claims, 100, 107)


if __name__ == "__main__":
    unittest.main()
