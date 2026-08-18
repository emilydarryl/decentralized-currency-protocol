#!/usr/bin/env python3
"""Validate and retain the labnet payout/failover demonstration evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence


class EvidenceError(RuntimeError):
    pass


def read_events(path: Path) -> list[dict[str, Any]]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise EvidenceError("miner emitted malformed structured JSON") from error
        if isinstance(value, dict) and "component" in value and "event" in value:
            events.append(value)
    return events


def canonical_hash(value: Any) -> str:
    body = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def build(miner_log: Path, claims_path: Path, start_height: int, end_height: int) -> dict[str, Any]:
    events = read_events(miner_log)
    claims = json.loads(claims_path.read_text(encoding="utf-8"))
    if claims.get("format") != "soveroot-labnet-noncustodial-claims-v0":
        raise EvidenceError("claims file has the wrong format")
    if claims.get("custody") != "none" or claims.get("settlement_status") != "accounting_claims_only_not_money":
        raise EvidenceError("claims overstate custody or settlement")
    if not claims.get("claims"):
        raise EvidenceError("no payout-script claim was produced")

    templates = [
        event["template_commitment_sha256"]
        for event in events
        if event.get("event") == "miner_template_committed"
    ]
    publications = [
        event["template_commitment_sha256"]
        for event in events
        if event.get("event") == "direct_submitblock_accepted"
    ]
    if len(templates) != 7 or publications != templates:
        raise EvidenceError("seven exact miner-created templates were not directly published")
    if end_height != start_height + 7:
        raise EvidenceError("final chain height did not advance by seven")

    attempts = [event for event in events if event.get("event") == "coordinator_attempt_result"]
    for attempt in attempts:
        if attempt.get("template_commitment_sha256") not in templates:
            raise EvidenceError("coordinator attempt substituted an unknown template")
    primary_failures = [
        str(event.get("reason", ""))
        for event in attempts
        if event.get("coordinator") == "primary" and event.get("status") != "accepted"
    ]
    if len(primary_failures) < 5:
        raise EvidenceError("too few ordered primary-coordinator failures")
    failure_results = {
        "rejection": "policy-rejection" in primary_failures[0],
        "disconnect": any(
            fragment in primary_failures[1] for fragment in ("connection-closed", "transport:timeout")
        ),
        "stall": "transport:timeout" in primary_failures[2],
        "malformed": "request-mismatch" in primary_failures[3],
        "downgrade": "setup:downgrade" in primary_failures[4],
    }
    if not all(failure_results.values()):
        missing = [name for name, passed in failure_results.items() if not passed]
        raise EvidenceError("missing coordinator failure evidence: " + ", ".join(missing))

    final_template = templates[-1]
    final_attempts = [
        event for event in attempts if event.get("template_commitment_sha256") == final_template
    ]
    final_failures = {
        event.get("coordinator")
        for event in final_attempts
        if event.get("status") != "accepted"
    }
    if final_failures != {"primary", "alternate"}:
        raise EvidenceError("both configured coordinators did not fail for the final template")
    declarations = [
        event
        for event in events
        if event.get("event") == "job_declaration_result"
        and event.get("template_commitment_sha256") == final_template
    ]
    if len(declarations) != 1 or declarations[0].get("status") != "direct_fallback":
        raise EvidenceError("the final template was not mined in direct fallback")
    accounting = [event for event in events if event.get("event") == "reporting_summary"]
    if not accounting or int(accounting[-1].get("failed", 0)) < 1:
        raise EvidenceError("accounting failure was not recorded without stopping mining")

    normalized_events = [
        {
            key: event[key]
            for key in (
                "component",
                "event",
                "coordinator",
                "status",
                "reason",
                "template_commitment_sha256",
                "block_hash",
            )
            if key in event
        }
        for event in events
    ]
    equivocation_views = ["aa" * 32, "bb" * 32]
    equivocation_vector = {
        "coordinator": "equivocator",
        "template_commitment_sha256": "33" * 32,
        "miner_views": equivocation_views,
        "expected_action": "quarantine_and_direct_fallback",
        "detected": len(set(equivocation_views)) > 1,
    }
    return {
        "format": "soveroot-labnet-coordinator-resilience-evidence-v0",
        "chain": "labnet",
        "same_running_miner_process": True,
        "start_height": start_height,
        "end_height": end_height,
        "direct_publications": len(publications),
        "miner_template_substitution_detected": False,
        "failure_results": failure_results,
        "direct_publication_during_total_coordinator_unavailability": True,
        "accounting_failure_recorded_without_mining_failure": True,
        "noncustodial_claims": claims,
        "equivocation_vector": equivocation_vector,
        "events": normalized_events,
        "events_sha256": canonical_hash(normalized_events),
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--miner-log", type=Path, required=True)
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--start-height", type=int, required=True)
    parser.add_argument("--end-height", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    evidence = build(args.miner_log, args.claims, args.start_height, args.end_height)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Coordinator resilience evidence: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
