#!/usr/bin/env python3
"""Prepare and verify a fail-closed four-operator share-sync laboratory kit."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import secrets
import stat
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import sharechain_multihost_v1 as safety
import sharechain_routed_v1 as routed
import sharechain_sync_v0 as sync
import sharechain_v0 as reference


PRIVATE_FORMAT = "soveroot-share-sync-operator-private-v1"
MANIFEST_FORMAT = "soveroot-share-sync-operator-manifest-v1"
EVIDENCE_FORMAT = "soveroot-share-sync-operator-evidence-v1"
SUMMARY_FORMAT = "soveroot-share-sync-operator-evidence-summary-v1"
CAMPAIGN_FORMAT = "soveroot-share-sync-operator-campaign-v1"
MANIFEST_DOMAIN = b"soveroot/share-sync/operator-manifest/v1\x00"
EVIDENCE_DOMAIN = b"soveroot/share-sync/operator-evidence/v1\x00"
PRIVATE_NAME = "operator-private.json"
MANIFEST_NAME = "operator-manifest.json"
CONFIG_NAME = "node-config.json"
REQUIRED_OPERATOR_COUNT = safety.MIN_DIVERSE_PEERS + 1


class OperatorKitError(RuntimeError):
    """A fail-closed operator-kit validation error."""


def _require_text(value: Any, label: str, limit: int = 64) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or not value.isascii():
        raise OperatorKitError(f"{label} must be 1-{limit} ASCII characters")
    return value


def _require_ip(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise OperatorKitError(f"{label} must be an IP literal")
    try:
        address = ipaddress.ip_address(value)
    except ValueError as error:
        raise OperatorKitError(f"{label} must be an IP literal") from error
    if address.is_unspecified or address.is_multicast or address.is_loopback:
        raise OperatorKitError(f"{label} must be a non-loopback unicast address")
    return value


def _require_port(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 65535:
        raise OperatorKitError("port must be an integer from 1 through 65535")
    return value


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OperatorKitError(f"cannot read canonical JSON from {path}") from error


def _write_new_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if private and os.name == "posix":
        path.parent.chmod(0o700)
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600 if private else 0o644)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            handle.write(encoded)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if private and os.name == "posix":
        path.chmod(0o600)


def _require_private_permissions(path: Path) -> None:
    if os.name != "posix":
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise OperatorKitError(f"private file permissions are too broad: {path} ({mode:o})")


def private_path(directory: Path) -> Path:
    return directory / "private" / PRIVATE_NAME


def manifest_path(directory: Path) -> Path:
    return directory / "public" / MANIFEST_NAME


def config_path(directory: Path) -> Path:
    return directory / "private" / CONFIG_NAME


def _manifest_body(
    *, node_id: str, host: str, port: int, identity_public_key_hex: str,
    operator_group: str, transport: str,
) -> dict[str, Any]:
    node_id = _require_text(node_id, "node id", 32)
    host = _require_ip(host, "host")
    port = _require_port(port)
    operator_group = _require_text(operator_group, "operator group")
    transport = _require_text(transport, "transport", 32)
    safety.require_hex(identity_public_key_hex, 32, "identity_key", "identity public key")
    return {
        "format": MANIFEST_FORMAT,
        "network_id": safety.NETWORK_ID,
        "node_id": node_id,
        "host": host,
        "port": port,
        "endpoint": f"{host}:{port}",
        "identity_algorithm": safety.IDENTITY_ALGORITHM,
        "identity_public_key_hex": identity_public_key_hex,
        "operator_group": operator_group,
        "transport": transport,
    }


def build_manifest(
    *, node_id: str, host: str, port: int, identity_seed_hex: str,
    operator_group: str, transport: str,
) -> dict[str, Any]:
    body = _manifest_body(
        node_id=node_id,
        host=host,
        port=port,
        identity_public_key_hex=safety.identity_public_key(identity_seed_hex),
        operator_group=operator_group,
        transport=transport,
    )
    return {
        **body,
        "signature_hex": safety.identity_sign(
            identity_seed_hex, MANIFEST_DOMAIN + safety.canonical_bytes(body)
        ),
    }


def verify_manifest(value: Any) -> dict[str, Any]:
    fields = {
        "format", "network_id", "node_id", "host", "port", "endpoint",
        "identity_algorithm", "identity_public_key_hex", "operator_group",
        "transport", "signature_hex",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise OperatorKitError("operator manifest fields are not canonical")
    body = _manifest_body(
        node_id=value["node_id"],
        host=value["host"],
        port=value["port"],
        identity_public_key_hex=value["identity_public_key_hex"],
        operator_group=value["operator_group"],
        transport=value["transport"],
    )
    if value["format"] != MANIFEST_FORMAT or value["network_id"] != safety.NETWORK_ID:
        raise OperatorKitError("operator manifest uses the wrong profile or network")
    if value["identity_algorithm"] != safety.IDENTITY_ALGORITHM:
        raise OperatorKitError("operator manifest uses an unsupported identity algorithm")
    if value["endpoint"] != body["endpoint"]:
        raise OperatorKitError("operator manifest endpoint does not match its route")
    safety.require_hex(value["signature_hex"], 64, "manifest_signature", "manifest signature")
    if not safety.identity_verify(
        value["identity_public_key_hex"],
        MANIFEST_DOMAIN + safety.canonical_bytes(body),
        value["signature_hex"],
    ):
        raise OperatorKitError("operator manifest signature is invalid")
    return dict(value)


def load_manifest(path: Path) -> dict[str, Any]:
    return verify_manifest(_read_json(path))


def load_private(path: Path) -> dict[str, Any]:
    _require_private_permissions(path)
    value = _read_json(path)
    fields = {"format", "node_id", "identity_seed_hex", "control_key_hex"}
    if not isinstance(value, dict) or set(value) != fields or value["format"] != PRIVATE_FORMAT:
        raise OperatorKitError("operator private-state fields are not canonical")
    _require_text(value["node_id"], "node id", 32)
    safety.require_hex(value["identity_seed_hex"], 32, "identity_seed", "identity seed")
    safety.require_hex(value["control_key_hex"], 32, "control_key", "control key")
    return value


def initialize_operator(
    directory: Path, *, node_id: str, host: str, port: int,
    operator_group: str, transport: str, identity_seed_hex: str,
    control_key_hex: str,
) -> dict[str, Any]:
    targets = (private_path(directory), manifest_path(directory))
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise FileExistsError(f"operator initialization refuses existing paths: {existing}")
    _require_text(node_id, "node id", 32)
    safety.require_hex(identity_seed_hex, 32, "identity_seed", "identity seed")
    safety.require_hex(control_key_hex, 32, "control_key", "control key")
    private = {
        "format": PRIVATE_FORMAT,
        "node_id": node_id,
        "identity_seed_hex": identity_seed_hex,
        "control_key_hex": control_key_hex,
    }
    manifest = build_manifest(
        node_id=node_id,
        host=host,
        port=port,
        identity_seed_hex=identity_seed_hex,
        operator_group=operator_group,
        transport=transport,
    )
    _write_new_json(private_path(directory), private, private=True)
    _write_new_json(manifest_path(directory), manifest)
    return manifest


def validate_manifest_set(values: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(values) != REQUIRED_OPERATOR_COUNT:
        raise OperatorKitError(
            f"operator set requires exactly {REQUIRED_OPERATOR_COUNT} signed manifests"
        )
    manifests = [verify_manifest(value) for value in values]
    for field in ("node_id", "endpoint", "identity_public_key_hex", "operator_group"):
        if len({manifest[field] for manifest in manifests}) != REQUIRED_OPERATOR_COUNT:
            raise OperatorKitError(f"operator manifests must have distinct {field} values")
    if len({safety.source_prefix(manifest["host"]) for manifest in manifests}) != REQUIRED_OPERATOR_COUNT:
        raise OperatorKitError("operator manifests must use four distinct source prefixes")
    for local in manifests:
        safety.select_diverse_peers([
            {
                "peer_id": peer["node_id"],
                "address": peer["host"],
                "operator_group": peer["operator_group"],
                "transport": peer["transport"],
                "priority": priority,
            }
            for priority, peer in enumerate(manifests)
            if peer["node_id"] != local["node_id"]
        ])
    return sorted(manifests, key=lambda item: item["node_id"])


def assemble_config(
    directory: Path, peer_manifest_paths: Sequence[Path], *, control_host: str = "127.0.0.1"
) -> dict[str, Any]:
    private = load_private(private_path(directory))
    local = load_manifest(manifest_path(directory))
    if private["node_id"] != local["node_id"] or safety.identity_public_key(
        private["identity_seed_hex"]
    ) != local["identity_public_key_hex"]:
        raise OperatorKitError("local private identity does not match the public manifest")
    peers = [load_manifest(path) for path in peer_manifest_paths]
    manifests = validate_manifest_set([local, *peers])
    peer_rows = [
        {
            "node_id": peer["node_id"],
            "host": peer["host"],
            "port": peer["port"],
            "endpoint": peer["endpoint"],
            "identity_public_key_hex": peer["identity_public_key_hex"],
            "operator_group": peer["operator_group"],
            "transport": peer["transport"],
        }
        for peer in manifests
        if peer["node_id"] != local["node_id"]
    ]
    private_directory = directory.resolve() / "private"
    config = {
        "format": routed.CONFIG_FORMAT,
        "node_id": local["node_id"],
        "listen_host": local["host"],
        "listen_port": local["port"],
        "endpoint": local["endpoint"],
        "control_host": control_host,
        "state_path": str(private_directory / "share-state.json"),
        "transport_state_path": str(private_directory / "transport-state.json"),
        "control_key_hex": private["control_key_hex"],
        "identity_seed_hex": private["identity_seed_hex"],
        "operator_group": local["operator_group"],
        "transport": local["transport"],
        "network_id": safety.NETWORK_ID,
        "trusted_rounds": reference.trusted_rounds(),
        "limits": {
            "sync": sync.LIMITS,
            "safety": safety.LIMITS,
            "transport": routed.TRANSPORT_LIMITS,
        },
        "peers": peer_rows,
    }
    target = config_path(directory)
    _write_new_json(target, config, private=True)
    routed.load_config(target)
    return config


def build_campaign() -> dict[str, Any]:
    scenario = next(
        item for item in reference.build_corpus()["scenarios"]
        if item["name"] == "valid_linear_chain"
    )
    root, one, two, three, four = scenario["shares"]
    files = {
        "alpha-initial.json": [root],
        "bravo-initial.json": [two],
        "charlie-initial.json": [four, three],
        "delta-initial.json": [root],
        "alpha-step.json": [one],
    }
    body = {
        "format": CAMPAIGN_FORMAT,
        "network_id": safety.NETWORK_ID,
        "scenario": "valid_linear_chain",
        "files": {
            name: safety.canonical_hash(shares) for name, shares in sorted(files.items())
        },
        "ordered_steps": [
            {"operator": "alpha", "action": "sync", "peer": "bravo"},
            {"operator": "alpha", "action": "import", "file": "alpha-step.json"},
            {"operator": "alpha", "action": "sync", "peer": "bravo"},
            {"operator": "bravo", "action": "sync", "peer": "charlie"},
            {"operator": "charlie", "action": "sync", "peer": "alpha"},
            {"operator": "delta", "action": "sync", "peer": "alpha"},
            {"operator": "alpha", "action": "sync", "peer": "delta"},
        ],
    }
    return {
        "manifest": {
            **body,
            "campaign_commitment_sha256": safety.canonical_hash(body),
        },
        "files": files,
    }


def write_campaign(directory: Path) -> dict[str, Any]:
    campaign = build_campaign()
    targets = [directory / name for name in campaign["files"]]
    targets.append(directory / "campaign.json")
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise FileExistsError(f"campaign generation refuses existing paths: {existing}")
    for name, shares in campaign["files"].items():
        _write_new_json(directory / name, shares)
    _write_new_json(directory / "campaign.json", campaign["manifest"])
    return campaign["manifest"]


def verify_campaign(value: Any) -> dict[str, Any]:
    expected = build_campaign()["manifest"]
    if value != expected:
        raise OperatorKitError("campaign manifest does not match the frozen v1 campaign")
    return dict(value)


def _load_local_config(directory: Path) -> dict[str, Any]:
    target = config_path(directory)
    _require_private_permissions(target)
    return routed.load_config(target)


def build_evidence(
    private: dict[str, Any], manifest: dict[str, Any], status: dict[str, Any],
    *, run_id: str, campaign_commitment_sha256: str, source_revision: str,
    observed_tick: int | None = None,
) -> dict[str, Any]:
    run_id = _require_text(run_id, "run id", 64)
    safety.require_hex(
        campaign_commitment_sha256, 32, "campaign_hash", "campaign commitment"
    )
    safety.require_hex(source_revision, 20, "source_revision", "source revision")
    manifest = verify_manifest(manifest)
    if private["node_id"] != manifest["node_id"] or safety.identity_public_key(
        private["identity_seed_hex"]
    ) != manifest["identity_public_key_hex"]:
        raise OperatorKitError("evidence signer does not match its manifest")
    try:
        transport = status["routed_transport"]
        body = {
            "format": EVIDENCE_FORMAT,
            "network_id": safety.NETWORK_ID,
            "run_id": run_id,
            "campaign_commitment_sha256": campaign_commitment_sha256,
            "source_revision": source_revision,
            "observed_tick": int(time.time()) if observed_tick is None else observed_tick,
            "manifest": manifest,
            "manifest_commitment_sha256": safety.canonical_hash(manifest),
            "node_id": manifest["node_id"],
            "state_commitment_sha256": status["state_commitment_sha256"],
            "selected_tip_share_id": status["selected_state"]["selected_tip_share_id"],
            "accepted_share_count": status["accepted_share_count"],
            "orphan_count": status["orphan_count"],
            "accepted_inbound_sessions": transport["accepted_inbound_sessions"],
            "accepted_inbound_frames": transport["accepted_inbound_frames"],
            "observed_source_prefixes": transport["observed_source_prefixes"],
        }
    except (KeyError, TypeError, ValueError) as error:
        raise OperatorKitError("node status cannot produce operator evidence") from error
    verify_evidence_fields(body)
    return {
        **body,
        "signature_hex": safety.identity_sign(
            private["identity_seed_hex"], EVIDENCE_DOMAIN + safety.canonical_bytes(body)
        ),
    }


def verify_evidence_fields(value: dict[str, Any]) -> None:
    if value["format"] != EVIDENCE_FORMAT or value["network_id"] != safety.NETWORK_ID:
        raise OperatorKitError("operator evidence uses the wrong profile or network")
    _require_text(value["run_id"], "run id", 64)
    safety.require_hex(
        value["campaign_commitment_sha256"], 32, "campaign_hash", "campaign commitment"
    )
    safety.require_hex(value["source_revision"], 20, "source_revision", "source revision")
    _require_text(value["node_id"], "node id", 32)
    if not isinstance(value["observed_tick"], int) or isinstance(value["observed_tick"], bool) or value["observed_tick"] < 0:
        raise OperatorKitError("operator evidence tick must be a non-negative integer")
    safety.require_hex(value["manifest_commitment_sha256"], 32, "manifest_hash", "manifest commitment")
    safety.require_hex(value["state_commitment_sha256"], 32, "state_hash", "state commitment")
    safety.require_hex(value["selected_tip_share_id"], 32, "selected_tip", "selected tip")
    for field in (
        "accepted_share_count", "orphan_count", "accepted_inbound_sessions",
        "accepted_inbound_frames",
    ):
        if not isinstance(value[field], int) or isinstance(value[field], bool) or value[field] < 0:
            raise OperatorKitError(f"operator evidence {field} must be a non-negative integer")
    prefixes = value["observed_source_prefixes"]
    if (
        not isinstance(prefixes, list)
        or not prefixes
        or len(prefixes) > sync.MAX_PEERS
        or len(prefixes) != len(set(prefixes))
        or any(
            not isinstance(prefix, str) or safety.source_prefix(prefix.split("/")[0]) != prefix
            for prefix in prefixes
        )
    ):
        raise OperatorKitError("operator evidence source prefixes are not canonical")


def verify_evidence(value: Any) -> dict[str, Any]:
    body_fields = {
        "format", "network_id", "run_id", "campaign_commitment_sha256",
        "source_revision", "observed_tick", "manifest",
        "manifest_commitment_sha256", "node_id", "state_commitment_sha256",
        "selected_tip_share_id", "accepted_share_count", "orphan_count",
        "accepted_inbound_sessions", "accepted_inbound_frames",
        "observed_source_prefixes",
    }
    if not isinstance(value, dict) or set(value) != body_fields | {"signature_hex"}:
        raise OperatorKitError("operator evidence fields are not canonical")
    manifest = verify_manifest(value["manifest"])
    if value["node_id"] != manifest["node_id"]:
        raise OperatorKitError("operator evidence node does not match its manifest")
    if value["manifest_commitment_sha256"] != safety.canonical_hash(manifest):
        raise OperatorKitError("operator evidence manifest commitment is invalid")
    body = {field: value[field] for field in body_fields}
    verify_evidence_fields(body)
    safety.require_hex(value["signature_hex"], 64, "evidence_signature", "evidence signature")
    if not safety.identity_verify(
        manifest["identity_public_key_hex"],
        EVIDENCE_DOMAIN + safety.canonical_bytes(body),
        value["signature_hex"],
    ):
        raise OperatorKitError("operator evidence signature is invalid")
    return dict(value)


def verify_evidence_set(values: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if len(values) != REQUIRED_OPERATOR_COUNT:
        raise OperatorKitError(
            f"evidence set requires exactly {REQUIRED_OPERATOR_COUNT} signed reports"
        )
    evidence = [verify_evidence(value) for value in values]
    manifests = validate_manifest_set([item["manifest"] for item in evidence])
    node_ids = {item["node_id"] for item in evidence}
    if node_ids != {manifest["node_id"] for manifest in manifests}:
        raise OperatorKitError("evidence reports do not match the operator set")
    run_ids = {item["run_id"] for item in evidence}
    campaign_commitments = {item["campaign_commitment_sha256"] for item in evidence}
    source_revisions = {item["source_revision"] for item in evidence}
    commitments = {item["state_commitment_sha256"] for item in evidence}
    tips = {item["selected_tip_share_id"] for item in evidence}
    counts = {item["accepted_share_count"] for item in evidence}
    orphan_counts = {item["orphan_count"] for item in evidence}
    if len(run_ids) != 1:
        raise OperatorKitError("operator evidence reports use different run ids")
    if len(campaign_commitments) != 1 or len(source_revisions) != 1:
        raise OperatorKitError("operator evidence reports use different campaigns or source revisions")
    if (
        len(commitments) != 1
        or len(tips) != 1
        or len(counts) != 1
        or next(iter(counts)) == 0
        or orphan_counts != {0}
    ):
        raise OperatorKitError("operator evidence does not show one non-empty converged state")
    if any(
        item["accepted_inbound_sessions"] == 0 or item["accepted_inbound_frames"] == 0
        for item in evidence
    ):
        raise OperatorKitError("every operator must record inbound peer sessions and frames")
    summary = {
        "format": SUMMARY_FORMAT,
        "network_id": safety.NETWORK_ID,
        "run_id": next(iter(run_ids)),
        "campaign_commitment_sha256": next(iter(campaign_commitments)),
        "source_revision": next(iter(source_revisions)),
        "operator_count": REQUIRED_OPERATOR_COUNT,
        "state_commitment_sha256": next(iter(commitments)),
        "selected_tip_share_id": next(iter(tips)),
        "accepted_share_count": next(iter(counts)),
        "orphan_count": 0,
        "manifest_set_commitment_sha256": safety.canonical_hash(manifests),
        "evidence_set_commitment_sha256": safety.canonical_hash(
            sorted(evidence, key=lambda item: item["node_id"])
        ),
        "all_signatures_valid": True,
        "all_operators_converged": True,
    }
    return summary


def _status(config: dict[str, Any]) -> dict[str, Any]:
    response = routed._send_control(config, {"op": "status"})
    if response.get("op") != "status_response":
        raise OperatorKitError("node returned an invalid status response")
    return response["status"]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    initializer = subparsers.add_parser("init")
    initializer.add_argument("--directory", type=Path, required=True)
    initializer.add_argument("--node-id", required=True)
    initializer.add_argument("--host", required=True)
    initializer.add_argument("--port", type=int, default=19444)
    initializer.add_argument("--operator-group", required=True)
    initializer.add_argument("--transport", required=True)
    validator = subparsers.add_parser("validate-manifests")
    validator.add_argument("--manifest", type=Path, action="append", required=True)
    assembler = subparsers.add_parser("assemble")
    assembler.add_argument("--directory", type=Path, required=True)
    assembler.add_argument("--peer-manifest", type=Path, action="append", required=True)
    assembler.add_argument("--control-host", default="127.0.0.1")
    campaign = subparsers.add_parser("write-campaign")
    campaign.add_argument("--directory", type=Path, required=True)
    for command in ("serve", "status", "stop"):
        child = subparsers.add_parser(command)
        child.add_argument("--directory", type=Path, required=True)
    synchronizer = subparsers.add_parser("sync")
    synchronizer.add_argument("--directory", type=Path, required=True)
    synchronizer.add_argument("--peer", required=True)
    importer = subparsers.add_parser("import-shares")
    importer.add_argument("--directory", type=Path, required=True)
    importer.add_argument("--shares", type=Path, required=True)
    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--directory", type=Path, required=True)
    snapshot.add_argument("--run-id", required=True)
    snapshot.add_argument("--campaign", type=Path, required=True)
    snapshot.add_argument("--source-revision", required=True)
    snapshot.add_argument("--output", type=Path, required=True)
    verifier = subparsers.add_parser("verify-evidence")
    verifier.add_argument("--evidence", type=Path, action="append", required=True)
    verifier.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "init":
        manifest = initialize_operator(
            args.directory,
            node_id=args.node_id,
            host=args.host,
            port=args.port,
            operator_group=args.operator_group,
            transport=args.transport,
            identity_seed_hex=secrets.token_hex(32),
            control_key_hex=secrets.token_hex(32),
        )
        print(json.dumps({
            "manifest": str(manifest_path(args.directory)),
            "manifest_commitment_sha256": safety.canonical_hash(manifest),
            "node_id": manifest["node_id"],
        }, indent=2, sort_keys=True))
        return 0
    if args.command == "validate-manifests":
        manifests = validate_manifest_set([load_manifest(path) for path in args.manifest])
        print(json.dumps({
            "operator_count": len(manifests),
            "manifest_set_commitment_sha256": safety.canonical_hash(manifests),
            "valid": True,
        }, indent=2, sort_keys=True))
        return 0
    if args.command == "assemble":
        config = assemble_config(
            args.directory, args.peer_manifest, control_host=args.control_host
        )
        print(json.dumps({
            "config": str(config_path(args.directory)),
            "node_id": config["node_id"],
            "peer_count": len(config["peers"]),
        }, indent=2, sort_keys=True))
        return 0
    if args.command == "write-campaign":
        campaign = write_campaign(args.directory)
        print(json.dumps({
            "campaign": str(args.directory / "campaign.json"),
            "campaign_commitment_sha256": campaign["campaign_commitment_sha256"],
        }, indent=2, sort_keys=True))
        return 0
    if args.command == "verify-evidence":
        evidence = [_read_json(path) for path in args.evidence]
        result = verify_evidence_set(evidence)
        if args.output is not None:
            _write_new_json(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    config = _load_local_config(args.directory)
    if args.command == "serve":
        return routed.serve(config)
    if args.command == "status":
        result: Any = _status(config)
    elif args.command == "stop":
        result = routed._send_control(config, {"op": "stop"})
    elif args.command == "sync":
        result = routed._send_control(config, {"op": "sync", "peer_id": args.peer})
    elif args.command == "import-shares":
        shares = _read_json(args.shares)
        if not isinstance(shares, list):
            raise OperatorKitError("share import must be a JSON array")
        result = routed._send_control(config, {"op": "import", "shares": shares})
    elif args.command == "snapshot":
        private = load_private(private_path(args.directory))
        manifest = load_manifest(manifest_path(args.directory))
        campaign = verify_campaign(_read_json(args.campaign))
        evidence = build_evidence(
            private,
            manifest,
            _status(config),
            run_id=args.run_id,
            campaign_commitment_sha256=campaign["campaign_commitment_sha256"],
            source_revision=args.source_revision,
        )
        _write_new_json(args.output, evidence)
        result = {
            "evidence": str(args.output),
            "evidence_commitment_sha256": safety.canonical_hash(evidence),
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError, OperatorKitError, routed.RoutedError, safety.SafetyError,
        sync.SyncError, reference.ProfileError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
