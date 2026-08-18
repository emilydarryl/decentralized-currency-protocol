#!/usr/bin/env python3
"""Loopback-only, test-only share-accounting coordinator for Soveroot labnet."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Sequence


WORKER_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
MAX_REPLICA_BODY = 1_048_576
MIN_DIRECT_PAYOUT = 546


class AccountingError(ValueError):
    """Raised when a submitted work receipt is malformed or inconsistent."""


def hash256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def canonical_hash(value: Any) -> str:
    body = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def compact_target(bits: int) -> int:
    exponent = bits >> 24
    mantissa = bits & 0x007FFFFF
    if bits & 0x00800000 or mantissa == 0:
        raise AccountingError("header contains an invalid compact target")
    target = mantissa >> (8 * (3 - exponent)) if exponent <= 3 else mantissa << (8 * (exponent - 3))
    if target <= 0 or target >= 1 << 256:
        raise AccountingError("header target is outside the 256-bit range")
    return target


def validate_receipt(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise AccountingError("receipt must be a JSON object")
    required = {
        "chain",
        "worker",
        "height",
        "previous_block_hash",
        "header_hex",
        "nonce",
        "hash",
        "block_candidate",
        "payout_script_hex",
        "template_commitment_sha256",
    }
    missing = sorted(required - document.keys())
    if missing:
        raise AccountingError(f"receipt is missing fields: {', '.join(missing)}")
    if document["chain"] != "labnet":
        raise AccountingError("only chain=labnet receipts are accepted")
    worker = document["worker"]
    if not isinstance(worker, str) or not WORKER_PATTERN.fullmatch(worker):
        raise AccountingError("worker label is invalid")
    height = document["height"]
    nonce = document["nonce"]
    if not isinstance(height, int) or isinstance(height, bool) or height < 0:
        raise AccountingError("height must be a non-negative integer")
    if not isinstance(nonce, int) or isinstance(nonce, bool) or not 0 <= nonce <= 0xFFFFFFFF:
        raise AccountingError("nonce must be a uint32")
    if not isinstance(document["block_candidate"], bool):
        raise AccountingError("block_candidate must be boolean")
    for field in ("previous_block_hash", "hash"):
        value = document[field]
        if not isinstance(value, str) or len(value) != 64:
            raise AccountingError(f"{field} must be a 32-byte hexadecimal hash")
        try:
            bytes.fromhex(value)
        except ValueError as error:
            raise AccountingError(f"{field} must be hexadecimal") from error
    payout_script = document["payout_script_hex"]
    if not isinstance(payout_script, str) or not 2 <= len(payout_script) <= 20_000:
        raise AccountingError("payout_script_hex must encode 1-10000 bytes")
    try:
        bytes.fromhex(payout_script)
    except ValueError as error:
        raise AccountingError("payout_script_hex must be hexadecimal") from error
    commitment = document["template_commitment_sha256"]
    if not isinstance(commitment, str) or len(commitment) != 64:
        raise AccountingError("template_commitment_sha256 must be a 32-byte hexadecimal hash")
    try:
        bytes.fromhex(commitment)
    except ValueError as error:
        raise AccountingError("template_commitment_sha256 must be hexadecimal") from error
    try:
        header = bytes.fromhex(document["header_hex"])
    except (TypeError, ValueError) as error:
        raise AccountingError("header_hex must be hexadecimal") from error
    if len(header) != 80:
        raise AccountingError("header_hex must encode exactly 80 bytes")
    if struct.unpack("<I", header[76:80])[0] != nonce:
        raise AccountingError("reported nonce does not match the header")
    if header[4:36][::-1].hex() != document["previous_block_hash"]:
        raise AccountingError("reported previous block hash does not match the header")
    digest = hash256(header)
    if digest[::-1].hex() != document["hash"]:
        raise AccountingError("reported hash does not match the header")
    bits = struct.unpack("<I", header[72:76])[0]
    block_candidate = int.from_bytes(digest, "little") <= compact_target(bits)
    if block_candidate != document["block_candidate"]:
        raise AccountingError("reported block-candidate status is incorrect")
    work_identity = {
        "chain": "labnet",
        "height": height,
        "header_hex": document["header_hex"].lower(),
        "nonce": nonce,
    }
    normalized = {
        "format": "soveroot-labnet-work-receipt-v2",
        "chain": "labnet",
        "worker": worker,
        "height": height,
        "previous_block_hash": document["previous_block_hash"],
        "header_hex": document["header_hex"].lower(),
        "nonce": nonce,
        "hash": document["hash"].lower(),
        "bits": f"{bits:08x}",
        "block_candidate": block_candidate,
        "payout_script_hex": payout_script.lower(),
        "template_commitment_sha256": commitment.lower(),
        "work_id_sha256": canonical_hash(work_identity),
    }
    normalized["receipt_id_sha256"] = canonical_hash(normalized)
    return normalized


def load_receipts(ledger: Path) -> list[dict[str, Any]]:
    if not ledger.exists():
        return []
    receipts = []
    for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        try:
            receipt = json.loads(line)
        except json.JSONDecodeError as error:
            raise AccountingError(f"ledger line {number} is malformed JSON") from error
        if not isinstance(receipt, dict) or receipt.get("format") != "soveroot-labnet-work-receipt-v2":
            raise AccountingError(f"ledger line {number} is not a normalized v2 receipt")
        receipts.append(receipt)
    validate_receipt_collection(receipts)
    return receipts


def validate_normalized_receipt(receipt: Any) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise AccountingError("replicated receipt must be a JSON object")
    normalized = validate_receipt(receipt)
    if normalized != receipt:
        raise AccountingError("replicated receipt is not canonical normalized v2 data")
    return normalized


def validate_receipt_collection(receipts: Sequence[dict[str, Any]]) -> None:
    by_receipt: dict[str, dict[str, Any]] = {}
    by_work: dict[str, dict[str, Any]] = {}
    for raw_receipt in receipts:
        receipt = validate_normalized_receipt(raw_receipt)
        receipt_id = receipt["receipt_id_sha256"]
        work_id = receipt["work_id_sha256"]
        previous_receipt = by_receipt.get(receipt_id)
        if previous_receipt is not None:
            if previous_receipt != receipt:
                raise AccountingError("conflicting content for one receipt identifier")
            raise AccountingError("duplicate receipt identifier in receipt set")
        previous_work = by_work.get(work_id)
        if previous_work is not None and previous_work != receipt:
            raise AccountingError("one work identity has conflicting receipt content")
        by_receipt[receipt_id] = receipt
        by_work[work_id] = receipt


def merge_receipts(
    existing: Sequence[dict[str, Any]], incoming: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    validate_receipt_collection(existing)
    validate_receipt_collection(incoming)
    by_receipt = {receipt["receipt_id_sha256"]: receipt for receipt in existing}
    by_work = {receipt["work_id_sha256"]: receipt for receipt in existing}
    additions = []
    for receipt in sorted(incoming, key=lambda item: item["receipt_id_sha256"]):
        receipt_id = receipt["receipt_id_sha256"]
        work_id = receipt["work_id_sha256"]
        if receipt_id in by_receipt:
            if by_receipt[receipt_id] != receipt:
                raise AccountingError("conflicting content for one receipt identifier")
            continue
        if work_id in by_work and by_work[work_id] != receipt:
            raise AccountingError("one work identity has conflicting receipt content")
        by_receipt[receipt_id] = receipt
        by_work[work_id] = receipt
        additions.append(receipt)
    return additions


def append_receipts(ledger: Path, receipts: Sequence[dict[str, Any]]) -> int:
    existing = load_receipts(ledger)
    additions = merge_receipts(existing, receipts)
    if not additions:
        return 0
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8", newline="\n") as output:
        for receipt in additions:
            output.write(json.dumps(receipt, separators=(",", ":"), sort_keys=True) + "\n")
        output.flush()
        os.fsync(output.fileno())
    return len(additions)


def append_receipt(ledger: Path, receipt: dict[str, Any]) -> None:
    if append_receipts(ledger, [receipt]) != 1:
        raise AccountingError("duplicate work receipt")


def receipt_set_document(receipts: Sequence[dict[str, Any]]) -> dict[str, Any]:
    validate_receipt_collection(receipts)
    ordered = sorted(receipts, key=lambda item: item["receipt_id_sha256"])
    commitment_body = [
        {"receipt_id_sha256": item["receipt_id_sha256"], "work_id_sha256": item["work_id_sha256"]}
        for item in ordered
    ]
    return {
        "format": "soveroot-labnet-receipt-set-v0",
        "chain": "labnet",
        "receipt_count": len(ordered),
        "receipt_set_commitment_sha256": canonical_hash(commitment_body),
        "receipts": ordered,
    }


def work_units(bits_hex: str) -> int:
    target = compact_target(int(bits_hex, 16))
    return ((1 << 256) - 1) // (target + 1) + 1


def build_claims(receipts: Sequence[dict[str, Any]]) -> dict[str, Any]:
    receipt_set = receipt_set_document(receipts)
    eligible = [receipt for receipt in receipts if receipt.get("block_candidate") is True]
    grouped: dict[str, dict[str, Any]] = {}
    for receipt in eligible:
        script = receipt["payout_script_hex"]
        units = work_units(receipt["bits"])
        group = grouped.setdefault(script, {"work_units": 0, "receipt_ids": []})
        group["work_units"] += units
        group["receipt_ids"].append(receipt["receipt_id_sha256"])
    total = sum(group["work_units"] for group in grouped.values())
    claims = []
    for script in sorted(grouped):
        group = grouped[script]
        body = {
            "payout_script_hex": script,
            "work_units": group["work_units"],
            "share_numerator": group["work_units"],
            "share_denominator": total,
            "receipt_ids": sorted(group["receipt_ids"]),
        }
        claim_id = hashlib.sha256(
            json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).hexdigest()
        claims.append({**body, "claim_id_sha256": claim_id})
    return {
        "format": "soveroot-labnet-noncustodial-claims-v0",
        "chain": "labnet",
        "custody": "none",
        "settlement_status": "accounting_claims_only_not_money",
        "eligible_receipt_count": len(eligible),
        "total_work_units": total,
        "receipt_set_commitment_sha256": receipt_set["receipt_set_commitment_sha256"],
        "claims": claims,
    }


def build_payout_plan(receipts: Sequence[dict[str, Any]], coinbase_value: int) -> dict[str, Any]:
    if not isinstance(coinbase_value, int) or isinstance(coinbase_value, bool):
        raise AccountingError("coinbase_value must be an integer")
    if not 0 < coinbase_value <= 0x7FFFFFFFFFFFFFFF:
        raise AccountingError("coinbase_value is outside the signed int64 range")
    claims = build_claims(receipts)
    if not claims["claims"] or claims["total_work_units"] <= 0:
        raise AccountingError("no eligible work exists for a payout plan")
    total_work = claims["total_work_units"]
    allocations = []
    allocated = 0
    for claim in claims["claims"]:
        scaled = coinbase_value * claim["work_units"]
        value, remainder = divmod(scaled, total_work)
        allocations.append({**claim, "value": value, "rounding_remainder": remainder})
        allocated += value
    for allocation in sorted(
        allocations,
        key=lambda item: (-item["rounding_remainder"], item["payout_script_hex"]),
    )[: coinbase_value - allocated]:
        allocation["value"] += 1
    outputs = []
    for allocation in sorted(allocations, key=lambda item: item["payout_script_hex"]):
        if allocation["value"] < MIN_DIRECT_PAYOUT:
            raise AccountingError(
                f"direct payout to {allocation['payout_script_hex']} is below {MIN_DIRECT_PAYOUT} satoshis"
            )
        outputs.append(
            {
                "payout_script_hex": allocation["payout_script_hex"],
                "value": allocation["value"],
                "work_units": allocation["work_units"],
                "receipt_ids": allocation["receipt_ids"],
            }
        )
    if sum(output["value"] for output in outputs) != coinbase_value:
        raise AccountingError("payout plan does not conserve the coinbase value")
    body = {
        "format": "soveroot-labnet-direct-payout-plan-v0",
        "chain": "labnet",
        "custody": "none",
        "settlement_status": "direct_coinbase_test_plan",
        "coinbase_value": coinbase_value,
        "receipt_set_commitment_sha256": claims["receipt_set_commitment_sha256"],
        "eligible_receipt_count": claims["eligible_receipt_count"],
        "total_work_units": total_work,
        "outputs": outputs,
    }
    return {**body, "payout_plan_commitment_sha256": canonical_hash(body)}


def write_claims(path: Path, claims: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def validate_replica_endpoint(endpoint: Any) -> str:
    if not isinstance(endpoint, str):
        raise AccountingError("replica endpoint must be a string")
    parsed = urllib.parse.urlparse(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise AccountingError("replica endpoint must be an http://127.0.0.1:PORT base URL")
    try:
        port = parsed.port
    except ValueError as error:
        raise AccountingError("replica endpoint port is malformed") from error
    if port is None or not 1024 <= port <= 65535:
        raise AccountingError("replica endpoint port must be between 1024 and 65535")
    return f"http://127.0.0.1:{port}"


def fetch_receipt_set(endpoint: str, timeout: float = 2.0) -> dict[str, Any]:
    base = validate_replica_endpoint(endpoint)
    try:
        with urllib.request.urlopen(f"{base}/receipts", timeout=timeout) as response:
            body = response.read(MAX_REPLICA_BODY + 1)
    except Exception as error:
        raise AccountingError(f"could not fetch replica receipt set: {error}") from error
    if len(body) > MAX_REPLICA_BODY:
        raise AccountingError("replica receipt set exceeds the size limit")
    try:
        document = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise AccountingError("replica returned malformed receipt-set JSON") from error
    if not isinstance(document, dict) or document.get("format") != "soveroot-labnet-receipt-set-v0":
        raise AccountingError("replica returned the wrong receipt-set format")
    receipts = document.get("receipts")
    if not isinstance(receipts, list):
        raise AccountingError("replica receipt set is missing its receipt list")
    expected = receipt_set_document(receipts)
    if document != expected:
        raise AccountingError("replica receipt-set commitment or metadata is inconsistent")
    return document


class AccountingHandler(BaseHTTPRequestHandler):
    server_version = "SoverootLabnetAccounting/1"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health" and not parsed.query:
            self._send_json(200, {"chain": "labnet", "role": "accounting-only", "status": "ready"})
            return
        if parsed.path == "/claims" and not parsed.query:
            self._send_json(200, build_claims(load_receipts(self.server.ledger)))  # type: ignore[attr-defined]
            return
        if parsed.path == "/receipts" and not parsed.query:
            self._send_json(200, receipt_set_document(load_receipts(self.server.ledger)))  # type: ignore[attr-defined]
            return
        if parsed.path == "/plan":
            try:
                query = urllib.parse.parse_qs(parsed.query, strict_parsing=True)
                if set(query) != {"coinbase_value"} or len(query["coinbase_value"]) != 1:
                    raise AccountingError("plan requires exactly one coinbase_value")
                coinbase_value = int(query["coinbase_value"][0])
                plan = build_payout_plan(load_receipts(self.server.ledger), coinbase_value)  # type: ignore[attr-defined]
            except (AccountingError, ValueError) as error:
                self._send_json(400, {"error": str(error)})
                return
            self._send_json(200, plan)
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path not in ("/share", "/reconcile"):
            self._send_json(404, {"error": "not found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", ""))
            if not 1 <= content_length <= 8192:
                raise AccountingError("request body must contain 1-8192 bytes")
            document = json.loads(self.rfile.read(content_length))
            if self.path == "/share":
                receipt = validate_receipt(document)
                append_receipt(self.server.ledger, receipt)  # type: ignore[attr-defined]
                response = {
                    "accepted": True,
                    "receipt_id_sha256": receipt["receipt_id_sha256"],
                    "role": "accounting-only",
                }
            else:
                if not isinstance(document, dict) or set(document) != {"peer_endpoint"}:
                    raise AccountingError("reconcile requires exactly one peer_endpoint")
                peer_endpoint = validate_replica_endpoint(document["peer_endpoint"])
                if urllib.parse.urlparse(peer_endpoint).port == self.server.server_port:
                    raise AccountingError("a replica cannot reconcile from itself")
                peer_set = fetch_receipt_set(peer_endpoint)
                added = append_receipts(self.server.ledger, peer_set["receipts"])  # type: ignore[attr-defined]
                local_set = receipt_set_document(load_receipts(self.server.ledger))  # type: ignore[attr-defined]
                response = {
                    "accepted": True,
                    "added_receipts": added,
                    "receipt_count": local_set["receipt_count"],
                    "receipt_set_commitment_sha256": local_set["receipt_set_commitment_sha256"],
                    "role": "accounting-replica",
                }
            write_claims(
                self.server.claims,  # type: ignore[attr-defined]
                build_claims(load_receipts(self.server.ledger)),  # type: ignore[attr-defined]
            )
        except (AccountingError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            self._send_json(400, {"error": str(error)})
            return
        self._send_json(202, response)

    def log_message(self, message: str, *arguments: object) -> None:
        print(f"accounting: {self.address_string()} {message % arguments}", file=sys.stderr)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the test-only Soveroot labnet accounting coordinator.")
    parser.add_argument("--bind", default="127.0.0.1", help="must remain 127.0.0.1")
    parser.add_argument("--port", type=int, default=29445, help="loopback HTTP port")
    parser.add_argument("--ledger", type=Path, required=True, help="append-only JSONL receipt ledger")
    parser.add_argument("--claims", type=Path, required=True, help="deterministic noncustodial claims JSON")
    parser.add_argument("--ready-file", type=Path, help="created after the loopback listener is ready")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.bind != "127.0.0.1":
        raise AccountingError("the prototype coordinator must bind only to 127.0.0.1")
    if not 1024 <= args.port <= 65535:
        raise AccountingError("port must be between 1024 and 65535")
    server = HTTPServer((args.bind, args.port), AccountingHandler)
    server.ledger = args.ledger  # type: ignore[attr-defined]
    server.claims = args.claims  # type: ignore[attr-defined]
    write_claims(args.claims, build_claims(load_receipts(args.ledger)))
    if args.ready_file is not None:
        args.ready_file.parent.mkdir(parents=True, exist_ok=True)
        args.ready_file.write_text("ready\n", encoding="utf-8")
    print(f"Accounting replica listening on http://{args.bind}:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if args.ready_file is not None:
            args.ready_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AccountingError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
