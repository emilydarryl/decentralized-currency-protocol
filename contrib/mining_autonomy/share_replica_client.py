#!/usr/bin/env python3
"""Operate loopback-only Soveroot labnet share-accounting replicas."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Sequence


class ReplicaClientError(RuntimeError):
    pass


def endpoint(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.path not in ("", "/")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise argparse.ArgumentTypeError("endpoint must be an http://127.0.0.1:PORT base URL")
    try:
        port = parsed.port
    except ValueError as error:
        raise argparse.ArgumentTypeError("endpoint port is malformed") from error
    if port is None or not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("endpoint port must be between 1024 and 65535")
    return f"http://127.0.0.1:{port}"


def request_json(
    url: str, *, document: dict[str, Any] | None = None, expected_status: int = 200
) -> dict[str, Any]:
    data = None
    method = "GET"
    headers = {}
    if document is not None:
        data = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            if response.status != expected_status:
                raise ReplicaClientError(f"unexpected HTTP status {response.status}")
            body = response.read(1_048_577)
    except Exception as error:
        raise ReplicaClientError(f"request failed for {url}: {error}") from error
    if len(body) > 1_048_576:
        raise ReplicaClientError("replica response exceeds the size limit")
    try:
        result = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ReplicaClientError("replica returned malformed JSON") from error
    if not isinstance(result, dict):
        raise ReplicaClientError("replica response must be a JSON object")
    return result


def write_document(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    health = subparsers.add_parser("health", help="require one replica to be available")
    health.add_argument("--endpoint", required=True, type=endpoint)

    reconcile = subparsers.add_parser("reconcile", help="make a target pull canonical receipts from a peer")
    reconcile.add_argument("--target", required=True, type=endpoint)
    reconcile.add_argument("--peer", required=True, type=endpoint)
    reconcile.add_argument("--output", type=Path)

    receipts = subparsers.add_parser("receipts", help="retain one canonical receipt-set snapshot")
    receipts.add_argument("--endpoint", required=True, type=endpoint)
    receipts.add_argument("--output", required=True, type=Path)

    plan = subparsers.add_parser("plan", help="retain one payout plan for a coinbase value")
    plan.add_argument("--endpoint", required=True, type=endpoint)
    plan.add_argument("--coinbase-value", required=True, type=int)
    plan.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "health":
        result = request_json(f"{args.endpoint}/health")
        if result.get("chain") != "labnet" or result.get("status") != "ready":
            raise ReplicaClientError("replica health response is not ready for labnet")
    elif args.command == "reconcile":
        result = request_json(
            f"{args.target}/reconcile",
            document={"peer_endpoint": args.peer},
            expected_status=202,
        )
        if result.get("accepted") is not True:
            raise ReplicaClientError("replica rejected reconciliation")
        if args.output is not None:
            write_document(args.output, result)
    elif args.command == "receipts":
        result = request_json(f"{args.endpoint}/receipts")
        if result.get("format") != "soveroot-labnet-receipt-set-v0":
            raise ReplicaClientError("replica returned the wrong receipt-set format")
        write_document(args.output, result)
    else:
        if args.coinbase_value <= 0:
            raise ReplicaClientError("coinbase value must be positive")
        result = request_json(f"{args.endpoint}/plan?coinbase_value={args.coinbase_value}")
        if result.get("format") != "soveroot-labnet-direct-payout-plan-v0":
            raise ReplicaClientError("replica returned the wrong payout-plan format")
        write_document(args.output, result)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReplicaClientError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
