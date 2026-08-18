#!/usr/bin/env python3
"""Build, solve, and submit a Soveroot labnet block outside the node daemon.

This is deliberately a labnet-only research tool.  It uses the inherited
SHA256d development proof of work and is not a production mining protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


class MiningError(RuntimeError):
    """Raised when the miner cannot safely construct or publish a block."""


def hash256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def encode_varint(value: int) -> bytes:
    if value < 0:
        raise MiningError("variable integers cannot be negative")
    if value < 0xFD:
        return bytes([value])
    if value <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", value)
    if value <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", value)
    if value <= 0xFFFFFFFFFFFFFFFF:
        return b"\xff" + struct.pack("<Q", value)
    raise MiningError("variable integer exceeds uint64")


def encode_script_number(value: int) -> bytes:
    if value < 0:
        raise MiningError("negative script numbers are not supported")
    if value == 0:
        return b""
    result = bytearray()
    while value:
        result.append(value & 0xFF)
        value >>= 8
    if result[-1] & 0x80:
        result.append(0)
    return bytes(result)


def push_data(data: bytes) -> bytes:
    length = len(data)
    if length <= 75:
        return bytes([length]) + data
    if length <= 0xFF:
        return b"\x4c" + bytes([length]) + data
    raise MiningError("coinbase tag is too large")


def encode_block_height(height: int) -> bytes:
    if height < 0:
        raise MiningError("block height cannot be negative")
    if height == 0:
        return b"\x00"
    if height <= 16:
        return bytes([0x50 + height])
    encoded = encode_script_number(height)
    return push_data(encoded)


def compact_target(bits: int) -> int:
    exponent = bits >> 24
    mantissa = bits & 0x007FFFFF
    if bits & 0x00800000 or mantissa == 0:
        raise MiningError("template contains an invalid compact target")
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))
    if target <= 0 or target >= 1 << 256:
        raise MiningError("template target is outside the 256-bit range")
    return target


def merkle_root(hashes: Sequence[bytes]) -> bytes:
    if not hashes:
        raise MiningError("a block must contain at least the coinbase transaction")
    layer = list(hashes)
    if any(len(item) != 32 for item in layer):
        raise MiningError("merkle leaves must be 32-byte hashes")
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [hash256(layer[index] + layer[index + 1]) for index in range(0, len(layer), 2)]
    return layer[0]


def coinbase_merkle_path(hashes: Sequence[bytes]) -> list[bytes]:
    if not hashes:
        raise MiningError("a block must contain at least the coinbase transaction")
    if any(len(item) != 32 for item in hashes):
        raise MiningError("merkle leaves must be 32-byte hashes")
    path: list[bytes] = []
    layer = list(hashes)
    index = 0
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        path.append(layer[index ^ 1])
        layer = [hash256(layer[offset] + layer[offset + 1]) for offset in range(0, len(layer), 2)]
        index //= 2
    return path


def _serialize_outputs(outputs: Sequence[tuple[int, bytes]]) -> bytes:
    result = bytearray(encode_varint(len(outputs)))
    for value, script in outputs:
        if value < 0 or value > 0x7FFFFFFFFFFFFFFF:
            raise MiningError("coinbase output value is outside the signed int64 range")
        result.extend(struct.pack("<q", value))
        result.extend(encode_varint(len(script)))
        result.extend(script)
    return bytes(result)


@dataclass(frozen=True)
class Coinbase:
    txid_hash: bytes
    block_bytes: bytes
    declaration_prefix: bytes
    declaration_suffix: bytes
    serialized_outputs: bytes


def build_coinbase(
    *,
    height: int,
    value: int,
    payout_script: bytes | None = None,
    payout_outputs: Sequence[tuple[int, bytes]] | None = None,
    coinbase_flags: bytes = b"",
    witness_commitment: bytes | None = None,
) -> Coinbase:
    tag = b"/Soveroot autonomous labnet v0/"
    script_sig = encode_block_height(height) + coinbase_flags + push_data(tag)
    if not 2 <= len(script_sig) <= 100:
        raise MiningError("coinbase scriptSig must contain between 2 and 100 bytes")
    if (payout_script is None) == (payout_outputs is None):
        raise MiningError("supply exactly one payout script or one payout-output plan")
    if payout_outputs is None:
        if not payout_script:
            raise MiningError("payout script cannot be empty")
        direct_outputs = [(value, payout_script)]
    else:
        direct_outputs = list(payout_outputs)
        if not direct_outputs:
            raise MiningError("payout-output plan cannot be empty")
        if any(not script for _, script in direct_outputs):
            raise MiningError("payout-output scripts cannot be empty")
        if len({script for _, script in direct_outputs}) != len(direct_outputs):
            raise MiningError("payout-output scripts must be unique")
        if sum(output_value for output_value, _ in direct_outputs) != value:
            raise MiningError("payout-output plan does not conserve the coinbase value")

    tx_input = (
        b"\x00" * 32
        + struct.pack("<I", 0xFFFFFFFF)
        + encode_varint(len(script_sig))
        + script_sig
        + struct.pack("<I", 0xFFFFFFFF)
    )
    outputs = direct_outputs
    if witness_commitment is not None:
        if not witness_commitment:
            raise MiningError("witness commitment script cannot be empty")
        outputs.append((0, witness_commitment))

    serialized_outputs = _serialize_outputs(outputs)
    declaration_prefix = (
        struct.pack("<I", 2)
        + encode_varint(1)
        + b"\x00" * 32
        + struct.pack("<I", 0xFFFFFFFF)
        + encode_varint(len(script_sig))
        + script_sig
    )
    declaration_suffix = struct.pack("<I", 0xFFFFFFFF) + serialized_outputs + struct.pack("<I", 0)
    base = declaration_prefix + declaration_suffix
    block_bytes = base
    if witness_commitment is not None:
        block_bytes = (
            struct.pack("<I", 2)
            + b"\x00\x01"
            + encode_varint(1)
            + tx_input
            + serialized_outputs
            + b"\x01\x20"
            + b"\x00" * 32
            + struct.pack("<I", 0)
        )
    return Coinbase(
        txid_hash=hash256(base),
        block_bytes=block_bytes,
        declaration_prefix=declaration_prefix,
        declaration_suffix=declaration_suffix,
        serialized_outputs=serialized_outputs,
    )


def canonical_template_commitment(template: dict[str, Any]) -> str:
    encoded = json.dumps(template, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_settlement_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlsplit(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.path not in ("", "/")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise MiningError("settlement peer must be an http://127.0.0.1:PORT base URL")
    try:
        port = parsed.port
    except ValueError as error:
        raise MiningError("settlement peer port is malformed") from error
    if port is None or not 1024 <= port <= 65535:
        raise MiningError("settlement peer port must be between 1024 and 65535")
    return f"http://127.0.0.1:{port}"


def validate_payout_plan(document: Any, coinbase_value: int) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise MiningError("payout plan must be a JSON object")
    required = {
        "format",
        "chain",
        "custody",
        "settlement_status",
        "coinbase_value",
        "receipt_set_commitment_sha256",
        "eligible_receipt_count",
        "total_work_units",
        "outputs",
        "payout_plan_commitment_sha256",
    }
    if set(document) != required:
        raise MiningError("payout plan contains missing or unknown fields")
    if (
        document["format"] != "soveroot-labnet-direct-payout-plan-v0"
        or document["chain"] != "labnet"
        or document["custody"] != "none"
        or document["settlement_status"] != "direct_coinbase_test_plan"
    ):
        raise MiningError("payout plan has the wrong safety or format boundary")
    if document["coinbase_value"] != coinbase_value:
        raise MiningError("payout plan coinbase value does not match the current template")
    for field in ("receipt_set_commitment_sha256", "payout_plan_commitment_sha256"):
        value = document[field]
        if not isinstance(value, str) or len(value) != 64:
            raise MiningError(f"{field} must be a 32-byte hexadecimal commitment")
        try:
            bytes.fromhex(value)
        except ValueError as error:
            raise MiningError(f"{field} must be hexadecimal") from error
    if (
        not isinstance(document["eligible_receipt_count"], int)
        or isinstance(document["eligible_receipt_count"], bool)
        or document["eligible_receipt_count"] <= 0
        or not isinstance(document["total_work_units"], int)
        or isinstance(document["total_work_units"], bool)
        or document["total_work_units"] <= 0
    ):
        raise MiningError("payout plan requires positive receipt and work totals")
    outputs = document["outputs"]
    if not isinstance(outputs, list) or not 2 <= len(outputs) <= 1000:
        raise MiningError("pooled payout plan must contain between two and 1000 outputs")
    scripts = []
    all_receipt_ids = []
    total_value = 0
    total_work = 0
    for output in outputs:
        if not isinstance(output, dict) or set(output) != {
            "payout_script_hex",
            "value",
            "work_units",
            "receipt_ids",
        }:
            raise MiningError("payout output contains missing or unknown fields")
        script = output["payout_script_hex"]
        if not isinstance(script, str) or not 2 <= len(script) <= 20_000:
            raise MiningError("payout output script must encode 1-10000 bytes")
        try:
            bytes.fromhex(script)
        except ValueError as error:
            raise MiningError("payout output script must be hexadecimal") from error
        value = output["value"]
        work_units = output["work_units"]
        receipt_ids = output["receipt_ids"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 546:
            raise MiningError("every direct payout must be at least 546 satoshis")
        if not isinstance(work_units, int) or isinstance(work_units, bool) or work_units <= 0:
            raise MiningError("every payout output must have positive work units")
        if (
            not isinstance(receipt_ids, list)
            or not receipt_ids
            or receipt_ids != sorted(receipt_ids)
            or any(not isinstance(item, str) or len(item) != 64 for item in receipt_ids)
        ):
            raise MiningError("payout output receipt identifiers must be sorted 32-byte hashes")
        try:
            for receipt_id in receipt_ids:
                bytes.fromhex(receipt_id)
        except ValueError as error:
            raise MiningError("payout output receipt identifiers must be hexadecimal") from error
        scripts.append(script)
        all_receipt_ids.extend(receipt_ids)
        total_value += value
        total_work += work_units
    if scripts != sorted(scripts) or len(set(scripts)) != len(scripts):
        raise MiningError("payout outputs must use unique scripts in canonical order")
    if total_value != coinbase_value:
        raise MiningError("payout outputs do not conserve the coinbase value")
    if total_work != document["total_work_units"]:
        raise MiningError("payout outputs do not conserve the declared work units")
    if len(set(all_receipt_ids)) != len(all_receipt_ids):
        raise MiningError("one receipt cannot be assigned to multiple payout outputs")
    if len(all_receipt_ids) != document["eligible_receipt_count"]:
        raise MiningError("payout outputs do not conserve the eligible receipt count")
    body = {key: value for key, value in document.items() if key != "payout_plan_commitment_sha256"}
    if canonical_template_commitment(body) != document["payout_plan_commitment_sha256"]:
        raise MiningError("payout plan commitment does not match its contents")
    return document


class SettlementPlanProvider:
    """Require multiple accounting replicas to agree before pooled settlement."""

    def __init__(self, endpoints: Sequence[str], timeout: float) -> None:
        self.endpoints = [validate_settlement_endpoint(endpoint) for endpoint in endpoints]
        if len(self.endpoints) < 2:
            raise MiningError("pooled settlement requires at least two accounting replicas")
        if len(set(self.endpoints)) != len(self.endpoints):
            raise MiningError("settlement peer endpoints must be unique")
        if timeout <= 0 or timeout > 5:
            raise MiningError("settlement timeout must be greater than zero and at most five seconds")
        self.timeout = timeout

    def fetch(self, coinbase_value: int) -> dict[str, Any]:
        plans = []
        for endpoint in self.endpoints:
            url = f"{endpoint}/plan?coinbase_value={coinbase_value}"
            try:
                with urllib.request.urlopen(url, timeout=self.timeout) as response:
                    body = response.read(1_048_577)
            except Exception as error:
                raise MiningError(f"settlement peer {endpoint} is unavailable: {error}") from error
            if len(body) > 1_048_576:
                raise MiningError("settlement peer response exceeds the size limit")
            try:
                plan = validate_payout_plan(json.loads(body), coinbase_value)
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise MiningError(f"settlement peer {endpoint} returned malformed JSON") from error
            structured_event(
                "settlement",
                "replica_plan_received",
                endpoint=endpoint,
                payout_plan_commitment_sha256=plan["payout_plan_commitment_sha256"],
                receipt_set_commitment_sha256=plan["receipt_set_commitment_sha256"],
            )
            plans.append(plan)
        if any(plan != plans[0] for plan in plans[1:]):
            raise MiningError("accounting replicas returned conflicting payout plans")
        return plans[0]


class JobDeclarator:
    """Invoke the pinned SV2 helper without granting it mining authority."""

    def __init__(
        self,
        helper: Path,
        endpoint: str,
        authority_public_key: str,
        timeout_ms: int,
        name: str = "coordinator",
    ) -> None:
        if not helper.is_file():
            raise MiningError(f"Stratum V2 helper was not found at {helper}")
        parsed = urllib.parse.urlsplit(f"//{endpoint}")
        if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port is None:
            raise MiningError("the labnet Stratum V2 endpoint must be a loopback host and port")
        if not authority_public_key or any(character.isspace() for character in authority_public_key):
            raise MiningError("the Stratum V2 authority public key is malformed")
        if timeout_ms <= 0 or timeout_ms > 10_000:
            raise MiningError("the Stratum V2 timeout must be between 1 and 10000 milliseconds")
        if not name or len(name) > 64 or any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for character in name
        ):
            raise MiningError("coordinator name must contain 1-64 safe label characters")
        self.name = name
        self.helper = helper
        self.endpoint = endpoint
        self.authority_public_key = authority_public_key
        self.timeout_ms = timeout_ms

    def declare(self, template: dict[str, Any]) -> dict[str, Any]:
        command = [
            str(self.helper),
            "declare",
            "--endpoint",
            self.endpoint,
            "--authority-public-key",
            self.authority_public_key,
            "--timeout-ms",
            str(self.timeout_ms),
        ]
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(template, separators=(",", ":"), sort_keys=True),
                capture_output=True,
                text=True,
                timeout=(self.timeout_ms / 1000) + 2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return {"status": "direct_fallback", "reason": f"transport:{type(error).__name__}"}
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {"status": "direct_fallback", "reason": "malformed_helper_reply"}
        if completed.returncode != 0 or not isinstance(response, dict):
            return {"status": "direct_fallback", "reason": "helper_failure"}
        if response.get("template_commitment_sha256") != template["template_commitment_sha256"]:
            return {"status": "direct_fallback", "reason": "template_commitment_mismatch"}
        if response.get("status") not in {"accepted", "direct_fallback"}:
            return {"status": "direct_fallback", "reason": "malformed_helper_status"}
        if response.get("transport_status") not in {"authenticated", "failed"}:
            return {"status": "direct_fallback", "reason": "malformed_transport_status"}
        if response["status"] == "accepted" and response["transport_status"] != "authenticated":
            return {"status": "direct_fallback", "reason": "unauthenticated_acceptance"}
        return response


class CoordinatorViewRegistry:
    """Detect conflicting test-profile views without trusting a coordinator."""

    def __init__(self) -> None:
        self._views: dict[tuple[str, str], str] = {}
        self.quarantined: set[str] = set()

    def observe(self, coordinator: str, template_commitment: str, state_commitment: str) -> bool:
        if coordinator in self.quarantined:
            return False
        key = (coordinator, template_commitment)
        previous = self._views.setdefault(key, state_commitment)
        if previous != state_commitment:
            self.quarantined.add(coordinator)
            return False
        return True


class CoordinatorSelector:
    """Try configured coordinators in order without changing the miner's job."""

    def __init__(
        self,
        coordinators: Sequence[JobDeclarator],
        view_registry: CoordinatorViewRegistry | None = None,
    ) -> None:
        if not coordinators:
            raise MiningError("at least one coordinator is required")
        names = [coordinator.name for coordinator in coordinators]
        if len(set(names)) != len(names):
            raise MiningError("coordinator names must be unique")
        self.coordinators = list(coordinators)
        self.view_registry = view_registry or CoordinatorViewRegistry()
        self.endpoint = ",".join(coordinator.endpoint for coordinator in coordinators)
        self.last_accepted: str | None = None

    def declare(self, template: dict[str, Any]) -> dict[str, Any]:
        attempts = []
        for index, coordinator in enumerate(self.coordinators):
            if coordinator.name in self.view_registry.quarantined:
                result = {"status": "direct_fallback", "reason": "coordinator_quarantined"}
            else:
                result = coordinator.declare(template)
            attempt = {
                "coordinator": coordinator.name,
                "status": result.get("status", "direct_fallback"),
                "reason": result.get("reason"),
                "template_commitment_sha256": template["template_commitment_sha256"],
            }
            attempts.append(attempt)
            structured_event("coordination", "coordinator_attempt_result", **attempt)
            if result.get("status") != "accepted":
                continue
            state_commitment = result.get("coordinator_state_commitment")
            if state_commitment is not None and (
                not isinstance(state_commitment, str)
                or not self.view_registry.observe(
                    coordinator.name,
                    template["template_commitment_sha256"],
                    state_commitment,
                )
            ):
                attempts[-1]["status"] = "direct_fallback"
                attempts[-1]["reason"] = "coordinator_equivocation"
                structured_event(
                    "coordination",
                    "coordinator_quarantined",
                    coordinator=coordinator.name,
                    reason="coordinator_equivocation",
                    template_commitment_sha256=template["template_commitment_sha256"],
                )
                continue
            previous = self.last_accepted
            self.last_accepted = coordinator.name
            return {
                **result,
                "coordinator": coordinator.name,
                "failover_used": index > 0,
                "switched": previous is not None and previous != coordinator.name,
                "attempts": attempts,
            }
        return {
            "status": "direct_fallback",
            "transport_status": "failed",
            "reason": "all_configured_coordinators_failed",
            "template_commitment_sha256": template["template_commitment_sha256"],
            "coordinator": None,
            "failover_used": bool(attempts),
            "switched": False,
            "attempts": attempts,
        }


def structured_event(component: str, event: str, **fields: Any) -> None:
    print(
        json.dumps(
            {"component": component, "event": event, **fields},
            separators=(",", ":"),
            sort_keys=True,
        ),
        flush=True,
    )


def solve_header(
    prefix: bytes,
    bits: int,
    max_nonce: int,
    attempt_observer: Callable[[bytes, int, bytes, bool], None] | None = None,
) -> tuple[bytes, int, bytes]:
    if len(prefix) != 76:
        raise MiningError("block header prefix must be 76 bytes")
    if max_nonce < 0 or max_nonce > 0xFFFFFFFF:
        raise MiningError("maximum nonce must fit in uint32")
    target = compact_target(bits)
    for nonce in range(max_nonce + 1):
        header = prefix + struct.pack("<I", nonce)
        digest = hash256(header)
        meets_target = int.from_bytes(digest, "little") <= target
        if attempt_observer is not None:
            attempt_observer(header, nonce, digest, meets_target)
        if meets_target:
            return header, nonce, digest
    raise MiningError(f"no valid nonce found in range 0..{max_nonce}")


class LabnetCli:
    def __init__(self, cli: Path, datadir: Path, config: Path) -> None:
        self._base = [
            str(cli),
            "-chain=labnet",
            f"-datadir={datadir}",
            f"-conf={config}",
        ]

    def call(self, method: str, *arguments: str, wallet: str | None = None) -> Any:
        command = list(self._base)
        if wallet is not None:
            command.append(f"-rpcwallet={wallet}")
        command.extend([method, *arguments])
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as error:
            detail = getattr(error, "stderr", "") or str(error)
            raise MiningError(f"sovr-cli call failed for {method}: {detail.strip()}") from error
        output = completed.stdout.strip()
        if not output:
            return None
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return output


class ShareReporter:
    """Best-effort work-receipt reporter that never controls block creation."""

    def __init__(self, endpoint: str, worker: str, interval: int, timeout: float) -> None:
        parsed = urllib.parse.urlsplit(endpoint)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.path != "/share"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise MiningError("share endpoint must be an unauthenticated loopback http://.../share URL")
        if not worker or len(worker) > 64 or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in worker):
            raise MiningError("worker name must contain 1-64 letters, digits, dots, underscores, or hyphens")
        if interval <= 0:
            raise MiningError("share report interval must be positive")
        if timeout <= 0 or timeout > 5:
            raise MiningError("share report timeout must be greater than zero and at most five seconds")
        self.endpoint = endpoint
        self.worker = worker
        self.interval = interval
        self.timeout = timeout
        self.attempts = 0
        self.delivered = 0
        self.failed = 0

    def observe(
        self,
        header: bytes,
        nonce: int,
        digest: bytes,
        block_candidate: bool,
        *,
        height: int,
        previous_block_hash: str,
        payout_script_hex: str,
        template_commitment_sha256: str,
    ) -> None:
        self.attempts += 1
        if self.attempts % self.interval != 0 and not block_candidate:
            return
        receipt = {
            "chain": "labnet",
            "worker": self.worker,
            "height": height,
            "previous_block_hash": previous_block_hash,
            "header_hex": header.hex(),
            "nonce": nonce,
            "hash": digest[::-1].hex(),
            "block_candidate": block_candidate,
            "payout_script_hex": payout_script_hex,
            "template_commitment_sha256": template_commitment_sha256,
        }
        body = json.dumps(receipt, separators=(",", ":"), sort_keys=True).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status != 202:
                    raise OSError(f"coordinator returned HTTP {response.status}")
                response.read(1024)
            self.delivered += 1
        except Exception:
            # Accounting is optional. A broken or absent coordinator must not
            # gain the ability to halt block construction or publication.
            self.failed += 1


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MiningError(f"{label} RPC response must be a JSON object")
    return value


def mine_one_block(
    rpc: LabnetCli,
    *,
    wallet: str,
    address: str,
    max_nonce: int,
    share_reporter: ShareReporter | None = None,
    job_declarator: JobDeclarator | CoordinatorSelector | None = None,
    settlement_provider: SettlementPlanProvider | None = None,
) -> dict[str, Any]:
    chain_info = require_dict(rpc.call("getblockchaininfo"), "getblockchaininfo")
    if chain_info.get("chain") != "labnet":
        raise MiningError("refusing to mine: connected node did not report chain=labnet")

    address_info = require_dict(rpc.call("getaddressinfo", address, wallet=wallet), "getaddressinfo")
    script_hex = address_info.get("scriptPubKey")
    if not isinstance(script_hex, str):
        raise MiningError("wallet did not return a payout script")
    try:
        payout_script = bytes.fromhex(script_hex)
    except ValueError as error:
        raise MiningError("wallet returned a malformed payout script") from error

    template = require_dict(
        rpc.call("getblocktemplate", json.dumps({"rules": ["segwit"]}, separators=(",", ":"))),
        "getblocktemplate",
    )
    required = ("version", "previousblockhash", "height", "coinbasevalue", "curtime", "bits", "transactions")
    missing = [field for field in required if field not in template]
    if missing:
        raise MiningError(f"block template is missing required fields: {', '.join(missing)}")
    if template["previousblockhash"] != chain_info.get("bestblockhash"):
        raise MiningError("block template is stale before mining began")
    transactions = template["transactions"]
    if not isinstance(transactions, list):
        raise MiningError("template transactions field must be a list")

    coinbase_aux = template.get("coinbaseaux", {})
    if not isinstance(coinbase_aux, dict):
        raise MiningError("template coinbaseaux field must be an object")
    try:
        flags = bytes.fromhex(coinbase_aux.get("flags", ""))
        witness_hex = template.get("default_witness_commitment")
        witness_commitment = bytes.fromhex(witness_hex) if witness_hex is not None else None
        previous_hash = bytes.fromhex(template["previousblockhash"])[::-1]
        bits = int(template["bits"], 16)
        version = int(template["version"])
        height = int(template["height"])
        coinbase_value = int(template["coinbasevalue"])
        block_time = int(template["curtime"])
    except (TypeError, ValueError) as error:
        raise MiningError("block template contains malformed encoded fields") from error
    if len(previous_hash) != 32:
        raise MiningError("template previous block hash must be 32 bytes")

    payout_plan = None
    direct_outputs = None
    if settlement_provider is not None:
        payout_plan = settlement_provider.fetch(coinbase_value)
        direct_outputs = [
            (output["value"], bytes.fromhex(output["payout_script_hex"]))
            for output in payout_plan["outputs"]
        ]
        structured_event(
            "settlement",
            "payout_plan_committed",
            payout_plan_commitment_sha256=payout_plan["payout_plan_commitment_sha256"],
            receipt_set_commitment_sha256=payout_plan["receipt_set_commitment_sha256"],
            output_count=len(direct_outputs),
        )
    coinbase = build_coinbase(
        height=height,
        value=coinbase_value,
        payout_script=payout_script if direct_outputs is None else None,
        payout_outputs=direct_outputs,
        coinbase_flags=flags,
        witness_commitment=witness_commitment,
    )
    transaction_hashes = [coinbase.txid_hash]
    transaction_bytes = [coinbase.block_bytes]
    for index, transaction in enumerate(transactions):
        if not isinstance(transaction, dict):
            raise MiningError(f"template transaction {index} must be an object")
        try:
            txid_hash = bytes.fromhex(transaction["txid"])[::-1]
            raw_transaction = bytes.fromhex(transaction["data"])
        except (KeyError, TypeError, ValueError) as error:
            raise MiningError(f"template transaction {index} is malformed") from error
        if len(txid_hash) != 32 or not raw_transaction:
            raise MiningError(f"template transaction {index} has invalid data")
        transaction_hashes.append(txid_hash)
        transaction_bytes.append(raw_transaction)

    root = merkle_root(transaction_hashes)
    semantic_template: dict[str, Any] = {
        "chain": "labnet",
        "height": height,
        "previous_block_hash": template["previousblockhash"],
        "version": version & 0xFFFFFFFF,
        "bits": bits,
        "curtime": block_time,
        "coinbase_value": coinbase_value,
        "payout_script_hex": payout_script.hex(),
        "payout_mode": "direct_share_settlement" if payout_plan is not None else "solo_wallet",
        "payout_scripts_hex": (
            [output["payout_script_hex"] for output in payout_plan["outputs"]]
            if payout_plan is not None
            else [payout_script.hex()]
        ),
        "payout_plan_commitment_sha256": (
            payout_plan["payout_plan_commitment_sha256"] if payout_plan is not None else None
        ),
        "coinbase_tx_version": 2,
        "coinbase_prefix_hex": coinbase.declaration_prefix.hex(),
        "coinbase_suffix_hex": coinbase.declaration_suffix.hex(),
        "coinbase_tx_hex": coinbase.block_bytes.hex(),
        "coinbase_outputs_hex": coinbase.serialized_outputs.hex(),
        "coinbase_tx_input_n_sequence": 0xFFFFFFFF,
        "coinbase_tx_locktime": 0,
        "transaction_ids": [item[::-1].hex() for item in transaction_hashes[1:]],
        "transaction_data": [item.hex() for item in transaction_bytes[1:]],
        "coinbase_merkle_path": [item.hex() for item in coinbase_merkle_path(transaction_hashes)],
        "merkle_root_internal_hex": root.hex(),
        "target_le_hex": compact_target(bits).to_bytes(32, "little").hex(),
    }
    semantic_template["template_commitment_sha256"] = canonical_template_commitment(semantic_template)
    structured_event(
        "template",
        "miner_template_committed",
        height=height,
        template_commitment_sha256=semantic_template["template_commitment_sha256"],
        transaction_count=len(transaction_bytes),
    )
    declaration_result = {"status": "direct_fallback", "reason": "coordinator_not_configured"}
    if job_declarator is not None:
        structured_event("transport", "coordinator_connection_attempted", endpoint=job_declarator.endpoint)
        declaration_result = job_declarator.declare(semantic_template)
        structured_event(
            "transport",
            "coordinator_session_result",
            status=declaration_result.get("transport_status", "failed"),
            reason=declaration_result.get("reason"),
        )
    structured_event(
        "declaration",
        "job_declaration_result",
        status=declaration_result["status"],
        reason=declaration_result.get("reason", "accepted_by_coordinator"),
        template_commitment_sha256=semantic_template["template_commitment_sha256"],
    )
    header_prefix = (
        struct.pack("<I", version & 0xFFFFFFFF)
        + previous_hash
        + root
        + struct.pack("<I", block_time)
        + struct.pack("<I", bits)
    )
    observer = None
    if share_reporter is not None:
        observer = lambda header, nonce, digest, block_candidate: share_reporter.observe(
            header,
            nonce,
            digest,
            block_candidate,
            height=height,
            previous_block_hash=template["previousblockhash"],
            payout_script_hex=payout_script.hex(),
            template_commitment_sha256=semantic_template["template_commitment_sha256"],
        )
    structured_event(
        "solving",
        "started",
        declaration_status=declaration_result["status"],
        template_commitment_sha256=semantic_template["template_commitment_sha256"],
    )
    header, nonce, digest = solve_header(header_prefix, bits, max_nonce, observer)
    block = header + encode_varint(len(transaction_bytes)) + b"".join(transaction_bytes)
    block_hash = digest[::-1].hex()
    structured_event(
        "solving",
        "solution_found",
        block_hash=block_hash,
        nonce=nonce,
        template_commitment_sha256=semantic_template["template_commitment_sha256"],
    )

    submission = rpc.call("submitblock", block.hex())
    if submission not in (None, "null"):
        raise MiningError(f"node rejected the independently built block: {submission}")
    if rpc.call("getbestblockhash") != block_hash:
        raise MiningError("node accepted no error but did not adopt the submitted block")
    structured_event(
        "publication",
        "direct_submitblock_accepted",
        block_hash=block_hash,
        template_commitment_sha256=semantic_template["template_commitment_sha256"],
    )
    if payout_plan is not None:
        structured_event(
            "settlement",
            "direct_coinbase_settlement_published",
            block_hash=block_hash,
            payout_plan_commitment_sha256=payout_plan["payout_plan_commitment_sha256"],
            output_count=len(payout_plan["outputs"]),
        )
    structured_event(
        "accounting",
        "reporting_summary",
        enabled=share_reporter is not None,
        delivered=share_reporter.delivered if share_reporter is not None else 0,
        failed=share_reporter.failed if share_reporter is not None else 0,
    )
    return {
        "block_hash": block_hash,
        "height": height,
        "nonce": nonce,
        "transactions": len(transaction_bytes),
        "declaration_status": declaration_result["status"],
        "declaration_reason": declaration_result.get("reason"),
        "template_commitment_sha256": semantic_template["template_commitment_sha256"],
        "payout_plan_commitment_sha256": (
            payout_plan["payout_plan_commitment_sha256"] if payout_plan is not None else None
        ),
        "share_reports_delivered": share_reporter.delivered if share_reporter is not None else 0,
        "share_reports_failed": share_reporter.failed if share_reporter is not None else 0,
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construct, solve, and directly submit one inherited-PoW Soveroot labnet block."
    )
    parser.add_argument("--cli", type=Path, required=True, help="path to sovr-cli")
    parser.add_argument("--datadir", type=Path, required=True, help="Soveroot labnet data directory")
    parser.add_argument("--conf", type=Path, required=True, help="Soveroot labnet configuration file")
    parser.add_argument("--wallet", default="miner", help="wallet containing the payout address")
    parser.add_argument("--address", required=True, help="labnet payout address")
    parser.add_argument("--max-nonce", type=int, default=10_000_000, help="largest nonce to try")
    parser.add_argument("--share-endpoint", help="optional loopback accounting endpoint ending in /share")
    parser.add_argument("--worker", default="labnet-miner", help="accounting-only worker label")
    parser.add_argument("--share-report-interval", type=int, default=1, help="report every Nth work attempt")
    parser.add_argument("--share-timeout", type=float, default=0.25, help="maximum seconds per optional report")
    parser.add_argument(
        "--settlement-peer",
        action="append",
        default=[],
        metavar="HTTP://127.0.0.1:PORT",
        help="repeatable accounting replica; every configured peer must return the identical payout plan",
    )
    parser.add_argument("--settlement-timeout", type=float, default=2.0, help="maximum seconds per payout-plan peer")
    parser.add_argument("--sv2-helper", type=Path, help="path to the pinned Stratum V2 declaration helper")
    parser.add_argument("--sv2-endpoint", help="loopback host:port for the test Job Declarator Server")
    parser.add_argument("--sv2-authority-public-key", help="pinned coordinator Noise authority public key")
    parser.add_argument("--sv2-timeout-ms", type=int, default=2000, help="bounded declaration timeout")
    parser.add_argument(
        "--sv2-coordinator",
        action="append",
        default=[],
        metavar="NAME,HOST:PORT,PUBLIC_KEY",
        help="repeatable ordered coordinator; retries preserve the exact miner-created template",
    )
    parser.add_argument("--blocks", type=int, default=1, help="number of blocks to mine in this process")
    parser.add_argument("--inter-block-delay", type=float, default=0, help="test-only pause between blocks")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.cli.is_file():
        raise MiningError(f"sovr-cli was not found at {args.cli}")
    if not 1 <= args.blocks <= 100:
        raise MiningError("block count must be between 1 and 100")
    if not 0 <= args.inter_block_delay <= 60:
        raise MiningError("inter-block delay must be between zero and 60 seconds")
    if args.settlement_peer and args.blocks != 1:
        raise MiningError("one agreed payout plan may settle exactly one block")
    share_reporter = None
    if args.share_endpoint:
        share_reporter = ShareReporter(
            args.share_endpoint,
            args.worker,
            args.share_report_interval,
            args.share_timeout,
        )
    settlement_provider = None
    if args.settlement_peer:
        settlement_provider = SettlementPlanProvider(args.settlement_peer, args.settlement_timeout)
    job_declarator: JobDeclarator | CoordinatorSelector | None = None
    sv2_values = (args.sv2_helper, args.sv2_endpoint, args.sv2_authority_public_key)
    if args.sv2_coordinator:
        if args.sv2_endpoint is not None or args.sv2_authority_public_key is not None:
            raise MiningError("legacy endpoint/key options cannot be combined with --sv2-coordinator")
        if args.sv2_helper is None:
            raise MiningError("--sv2-helper is required with --sv2-coordinator")
        coordinators = []
        for value in args.sv2_coordinator:
            parts = value.split(",", 2)
            if len(parts) != 3:
                raise MiningError("--sv2-coordinator must be NAME,HOST:PORT,PUBLIC_KEY")
            name, endpoint, public_key = parts
            coordinators.append(
                JobDeclarator(
                    args.sv2_helper,
                    endpoint,
                    public_key,
                    args.sv2_timeout_ms,
                    name=name,
                )
            )
        job_declarator = CoordinatorSelector(coordinators)
    elif any(value is not None for value in sv2_values):
        if not all(value is not None for value in sv2_values):
            raise MiningError(
                "--sv2-helper, --sv2-endpoint, and --sv2-authority-public-key must be supplied together"
            )
        job_declarator = JobDeclarator(
            args.sv2_helper,
            args.sv2_endpoint,
            args.sv2_authority_public_key,
            args.sv2_timeout_ms,
        )
    rpc = LabnetCli(args.cli, args.datadir, args.conf)
    for block_index in range(args.blocks):
        result = mine_one_block(
            rpc,
            wallet=args.wallet,
            address=args.address,
            max_nonce=args.max_nonce,
            share_reporter=share_reporter,
            job_declarator=job_declarator,
            settlement_provider=settlement_provider,
        )
        print(f"Autonomous external block accepted: {result['block_hash']}", flush=True)
        print(f"Height: {result['height']}", flush=True)
        print(f"Nonce: {result['nonce']}", flush=True)
        print(f"Transactions selected from the miner's own node: {result['transactions']}", flush=True)
        print(f"Job declaration status: {result['declaration_status']}", flush=True)
        print(f"Template commitment: {result['template_commitment_sha256']}", flush=True)
        if result["payout_plan_commitment_sha256"] is not None:
            print(
                f"Direct payout plan commitment: {result['payout_plan_commitment_sha256']}",
                flush=True,
            )
        if share_reporter is not None:
            print(f"Share reports delivered: {result['share_reports_delivered']}", flush=True)
            print(f"Share reports failed without stopping mining: {result['share_reports_failed']}", flush=True)
        if block_index + 1 < args.blocks and args.inter_block_delay:
            time.sleep(args.inter_block_delay)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MiningError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
