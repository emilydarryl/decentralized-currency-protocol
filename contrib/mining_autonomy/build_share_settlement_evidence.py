#!/usr/bin/env python3
"""Validate retained two-replica and direct-coinbase labnet evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence


class SettlementEvidenceError(RuntimeError):
    pass


def canonical_hash(value: Any) -> str:
    body = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def load_document(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SettlementEvidenceError(f"{label} is not readable canonical JSON") from error
    if not isinstance(document, dict):
        raise SettlementEvidenceError(f"{label} must be a JSON object")
    return document


def read_events(path: Path) -> list[dict[str, Any]]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise SettlementEvidenceError("miner emitted malformed structured JSON") from error
        if isinstance(event, dict) and "component" in event and "event" in event:
            events.append(event)
    return events


def value_to_satoshis(value: Any) -> int:
    try:
        decimal = Decimal(str(value)) * Decimal(100_000_000)
    except (InvalidOperation, ValueError) as error:
        raise SettlementEvidenceError("coinbase output value is malformed") from error
    integral = decimal.to_integral_value()
    if decimal != integral:
        raise SettlementEvidenceError("coinbase output value has sub-satoshi precision")
    return int(integral)


def verify_receipt_set(document: dict[str, Any]) -> None:
    if document.get("format") != "soveroot-labnet-receipt-set-v0" or document.get("chain") != "labnet":
        raise SettlementEvidenceError("receipt snapshot has the wrong format or chain")
    receipts = document.get("receipts")
    if not isinstance(receipts, list) or len(receipts) < 3:
        raise SettlementEvidenceError("receipt snapshot must contain at least three receipts")
    if document.get("receipt_count") != len(receipts):
        raise SettlementEvidenceError("receipt snapshot count is inconsistent")
    receipt_ids = [receipt.get("receipt_id_sha256") for receipt in receipts if isinstance(receipt, dict)]
    work_ids = [receipt.get("work_id_sha256") for receipt in receipts if isinstance(receipt, dict)]
    if (
        len(receipt_ids) != len(receipts)
        or len(set(receipt_ids)) != len(receipt_ids)
        or len(work_ids) != len(receipts)
        or len(set(work_ids)) != len(work_ids)
    ):
        raise SettlementEvidenceError("receipt snapshot contains duplicate or malformed identities")
    ordered = sorted(receipts, key=lambda item: item["receipt_id_sha256"])
    if receipts != ordered:
        raise SettlementEvidenceError("receipt snapshot is not in canonical order")
    body = [
        {"receipt_id_sha256": item["receipt_id_sha256"], "work_id_sha256": item["work_id_sha256"]}
        for item in ordered
    ]
    if document.get("receipt_set_commitment_sha256") != canonical_hash(body):
        raise SettlementEvidenceError("receipt-set commitment is inconsistent")


def verify_plan(plan: dict[str, Any], receipt_set: dict[str, Any]) -> None:
    if (
        plan.get("format") != "soveroot-labnet-direct-payout-plan-v0"
        or plan.get("chain") != "labnet"
        or plan.get("custody") != "none"
        or plan.get("settlement_status") != "direct_coinbase_test_plan"
    ):
        raise SettlementEvidenceError("payout plan overstates its format or safety boundary")
    if plan.get("receipt_set_commitment_sha256") != receipt_set["receipt_set_commitment_sha256"]:
        raise SettlementEvidenceError("payout plan is not bound to the reconciled receipt set")
    outputs = plan.get("outputs")
    if not isinstance(outputs, list) or len(outputs) < 2:
        raise SettlementEvidenceError("payout plan must contain at least two direct outputs")
    scripts = []
    receipt_ids = []
    total_value = 0
    total_work = 0
    for output in outputs:
        if not isinstance(output, dict) or set(output) != {
            "payout_script_hex",
            "value",
            "work_units",
            "receipt_ids",
        }:
            raise SettlementEvidenceError("payout plan contains a malformed output")
        script = output["payout_script_hex"]
        if not isinstance(script, str) or not script or len(script) % 2:
            raise SettlementEvidenceError("payout output script is malformed")
        try:
            bytes.fromhex(script)
        except ValueError as error:
            raise SettlementEvidenceError("payout output script is not hexadecimal") from error
        if not isinstance(output["value"], int) or isinstance(output["value"], bool) or output["value"] < 546:
            raise SettlementEvidenceError("payout output is below the direct-settlement minimum")
        if (
            not isinstance(output["work_units"], int)
            or isinstance(output["work_units"], bool)
            or output["work_units"] <= 0
        ):
            raise SettlementEvidenceError("payout output has invalid work accounting")
        ids = output["receipt_ids"]
        if not isinstance(ids, list) or not ids or ids != sorted(ids):
            raise SettlementEvidenceError("payout output receipt identifiers are not canonical")
        try:
            if any(not isinstance(item, str) or len(item) != 64 for item in ids):
                raise ValueError
            for item in ids:
                bytes.fromhex(item)
        except ValueError as error:
            raise SettlementEvidenceError("payout output receipt identifier is malformed") from error
        scripts.append(script)
        receipt_ids.extend(ids)
        total_value += output["value"]
        total_work += output["work_units"]
    if scripts != sorted(scripts) or len(set(scripts)) != len(scripts):
        raise SettlementEvidenceError("payout scripts are not unique and canonically ordered")
    if len(set(receipt_ids)) != len(receipt_ids):
        raise SettlementEvidenceError("one receipt is assigned to multiple payout outputs")
    if set(receipt_ids) != {
        receipt["receipt_id_sha256"] for receipt in receipt_set["receipts"] if receipt.get("block_candidate")
    }:
        raise SettlementEvidenceError("payout plan does not cover exactly the eligible receipt set")
    if total_value != plan.get("coinbase_value"):
        raise SettlementEvidenceError("payout plan does not conserve the coinbase value")
    if total_work != plan.get("total_work_units"):
        raise SettlementEvidenceError("payout plan does not conserve the declared work units")
    if plan.get("eligible_receipt_count") != len(receipt_ids):
        raise SettlementEvidenceError("payout plan eligible receipt count is inconsistent")
    body = {key: value for key, value in plan.items() if key != "payout_plan_commitment_sha256"}
    if plan.get("payout_plan_commitment_sha256") != canonical_hash(body):
        raise SettlementEvidenceError("payout-plan commitment is inconsistent")


def build(
    receipt_set_a_path: Path,
    receipt_set_b_path: Path,
    plan_a_path: Path,
    plan_b_path: Path,
    block_path: Path,
    settlement_log_path: Path,
    seed_a_miner_log_path: Path,
    seed_b_miner_log_path: Path,
    offline_miner_log_path: Path,
    recovery_path: Path,
    start_height: int,
    end_height: int,
) -> dict[str, Any]:
    receipt_set_a = load_document(receipt_set_a_path, "replica A receipt snapshot")
    receipt_set_b = load_document(receipt_set_b_path, "replica B receipt snapshot")
    verify_receipt_set(receipt_set_a)
    verify_receipt_set(receipt_set_b)
    if receipt_set_a != receipt_set_b:
        raise SettlementEvidenceError("accounting replicas did not converge byte for byte")

    plan_a = load_document(plan_a_path, "replica A payout plan")
    plan_b = load_document(plan_b_path, "replica B payout plan")
    verify_plan(plan_a, receipt_set_a)
    verify_plan(plan_b, receipt_set_b)
    if plan_a != plan_b:
        raise SettlementEvidenceError("accounting replicas returned different payout plans")

    recovery = load_document(recovery_path, "replica recovery result")
    if (
        recovery.get("accepted") is not True
        or not isinstance(recovery.get("added_receipts"), int)
        or recovery["added_receipts"] < 1
        or recovery.get("receipt_count") != receipt_set_a["receipt_count"]
        or recovery.get("receipt_set_commitment_sha256")
        != receipt_set_a["receipt_set_commitment_sha256"]
    ):
        raise SettlementEvidenceError("stale replica did not prove recovery to the final receipt set")

    seed_publications = []
    for label, path in (("seed A", seed_a_miner_log_path), ("seed B", seed_b_miner_log_path)):
        events = read_events(path)
        publications = [event for event in events if event.get("event") == "direct_submitblock_accepted"]
        if len(publications) != 1 or not isinstance(publications[0].get("block_hash"), str):
            raise SettlementEvidenceError(f"{label} did not retain exactly one direct publication")
        seed_publications.append(publications[0])

    offline_events = read_events(offline_miner_log_path)
    offline_publications = [event for event in offline_events if event.get("event") == "direct_submitblock_accepted"]
    offline_reporting = [event for event in offline_events if event.get("event") == "reporting_summary"]
    if len(offline_publications) != 1 or not offline_reporting or offline_reporting[-1].get("delivered", 0) < 1:
        raise SettlementEvidenceError("mining did not continue through one-replica unavailability")
    eligible_hashes = {
        receipt["hash"] for receipt in receipt_set_a["receipts"] if receipt.get("block_candidate") is True
    }
    publication_hashes = {
        event["block_hash"] for event in [*seed_publications, offline_publications[0]]
    }
    if eligible_hashes != publication_hashes:
        raise SettlementEvidenceError("eligible receipts do not match the three directly published source blocks")

    settlement_events = read_events(settlement_log_path)
    replica_plans = [event for event in settlement_events if event.get("event") == "replica_plan_received"]
    plan_commits = [event for event in settlement_events if event.get("event") == "payout_plan_committed"]
    publications = [
        event for event in settlement_events if event.get("event") == "direct_coinbase_settlement_published"
    ]
    expected_commitment = plan_a["payout_plan_commitment_sha256"]
    if (
        len(replica_plans) != 2
        or any(event.get("payout_plan_commitment_sha256") != expected_commitment for event in replica_plans)
        or len(plan_commits) != 1
        or plan_commits[0].get("payout_plan_commitment_sha256") != expected_commitment
        or len(publications) != 1
        or publications[0].get("payout_plan_commitment_sha256") != expected_commitment
    ):
        raise SettlementEvidenceError("miner did not commit and publish the two-replica payout plan")

    block = load_document(block_path, "decoded settlement block")
    transactions = block.get("tx")
    if not isinstance(transactions, list) or not transactions or not isinstance(transactions[0], dict):
        raise SettlementEvidenceError("decoded block is missing its coinbase transaction")
    coinbase = transactions[0]
    inputs = coinbase.get("vin")
    if not isinstance(inputs, list) or not inputs or "coinbase" not in inputs[0]:
        raise SettlementEvidenceError("first decoded transaction is not coinbase")
    actual_outputs = []
    for output in coinbase.get("vout", []):
        if not isinstance(output, dict) or not isinstance(output.get("scriptPubKey"), dict):
            raise SettlementEvidenceError("decoded coinbase contains a malformed output")
        satoshis = value_to_satoshis(output.get("value"))
        if satoshis > 0:
            actual_outputs.append(
                {
                    "payout_script_hex": output["scriptPubKey"].get("hex"),
                    "value": satoshis,
                }
            )
    expected_outputs = [
        {"payout_script_hex": output["payout_script_hex"], "value": output["value"]}
        for output in plan_a["outputs"]
    ]
    if actual_outputs != expected_outputs:
        raise SettlementEvidenceError("decoded coinbase outputs do not match the agreed payout plan")
    if block.get("hash") != publications[0].get("block_hash"):
        raise SettlementEvidenceError("published settlement event does not match the decoded block")
    if end_height != start_height + 4:
        raise SettlementEvidenceError("labnet chain did not advance by the expected four blocks")

    return {
        "format": "soveroot-labnet-replicated-share-settlement-evidence-v0",
        "chain": "labnet",
        "custody": "none",
        "start_height": start_height,
        "end_height": end_height,
        "replica_count": 2,
        "replica_receipt_sets_identical": True,
        "replica_failure_recovery_proven": True,
        "source_block_hashes": sorted(publication_hashes),
        "offline_mining_block_hash": offline_publications[0]["block_hash"],
        "receipt_count": receipt_set_a["receipt_count"],
        "receipt_set_commitment_sha256": receipt_set_a["receipt_set_commitment_sha256"],
        "payout_plan_commitment_sha256": expected_commitment,
        "direct_payout_outputs": expected_outputs,
        "coinbase_value": plan_a["coinbase_value"],
        "settlement_block_hash": block["hash"],
        "settlement_coinbase_txid": coinbase.get("txid"),
        "direct_publication": True,
        "limits": [
            "private_labnet_only",
            "no_global_sharechain_consensus",
            "no_sybil_or_censorship_resistance_claim",
            "not_final_soveroot_pow",
        ],
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt-set-a", type=Path, required=True)
    parser.add_argument("--receipt-set-b", type=Path, required=True)
    parser.add_argument("--plan-a", type=Path, required=True)
    parser.add_argument("--plan-b", type=Path, required=True)
    parser.add_argument("--block", type=Path, required=True)
    parser.add_argument("--settlement-log", type=Path, required=True)
    parser.add_argument("--seed-a-miner-log", type=Path, required=True)
    parser.add_argument("--seed-b-miner-log", type=Path, required=True)
    parser.add_argument("--offline-miner-log", type=Path, required=True)
    parser.add_argument("--recovery", type=Path, required=True)
    parser.add_argument("--start-height", type=int, required=True)
    parser.add_argument("--end-height", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    evidence = build(
        args.receipt_set_a,
        args.receipt_set_b,
        args.plan_a,
        args.plan_b,
        args.block,
        args.settlement_log,
        args.seed_a_miner_log,
        args.seed_b_miner_log,
        args.offline_miner_log,
        args.recovery,
        args.start_height,
        args.end_height,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Replicated share settlement evidence: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SettlementEvidenceError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
