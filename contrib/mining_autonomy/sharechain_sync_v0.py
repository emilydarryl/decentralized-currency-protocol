#!/usr/bin/env python3
"""Authenticated, bounded three-peer sharechain synchronization for private labnet."""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import ipaddress
import json
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path
from typing import Any, Sequence

import independent_sharechain_v0 as independent
import sharechain_v0 as reference


PROTOCOL = "soveroot-share-sync-labnet-v0"
STATE_FORMAT = "soveroot-share-sync-state-v0"
AUTH_DOMAIN = b"soveroot/share-sync/auth/v0\x00"
CONTROL_ID = "local-controller"
ZERO_ID = "00" * 32

MAX_MESSAGE_BYTES = 131_072
MAX_SHARES_PER_MESSAGE = 64
MAX_KNOWN_SHARES = 4_096
MAX_INVENTORY_IDS_PER_MESSAGE = 512
MAX_INVENTORY_PAGES = 8
MAX_ORPHANS = 16
MAX_ORPHAN_AGE_TICKS = 64
MAX_PEERS = 8
MAX_CONCURRENT_CONNECTIONS = 8
MAX_ANNOUNCEMENT_SLOTS_PER_PEER = 128
MAX_EQUIVOCATIONS = 128
MAX_SYNC_OPERATIONS = 144
SOCKET_TIMEOUT_SECONDS = 5.0

LIMITS = {
    "max_message_bytes": MAX_MESSAGE_BYTES,
    "max_shares_per_message": MAX_SHARES_PER_MESSAGE,
    "max_known_shares": MAX_KNOWN_SHARES,
    "max_inventory_ids_per_message": MAX_INVENTORY_IDS_PER_MESSAGE,
    "max_inventory_pages": MAX_INVENTORY_PAGES,
    "max_orphans": MAX_ORPHANS,
    "max_orphan_age_ticks": MAX_ORPHAN_AGE_TICKS,
    "max_peers": MAX_PEERS,
    "max_concurrent_connections": MAX_CONCURRENT_CONNECTIONS,
    "max_announcement_slots_per_peer": MAX_ANNOUNCEMENT_SLOTS_PER_PEER,
    "max_equivocations": MAX_EQUIVOCATIONS,
    "max_sync_operations": MAX_SYNC_OPERATIONS,
}


class SyncError(RuntimeError):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=True).encode("ascii")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require_hex(value: Any, size: int, reason: str, label: str) -> str:
    if not isinstance(value, str) or len(value) != size * 2 or value != value.lower():
        raise SyncError(reason, f"{label} must be canonical lowercase {size}-byte hex")
    try:
        bytes.fromhex(value)
    except ValueError as error:
        raise SyncError(reason, f"{label} must be hexadecimal") from error
    return value


def require_loopback(value: Any, reason: str, label: str) -> str:
    if not isinstance(value, str):
        raise SyncError(reason, f"{label} must be a loopback IP address")
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError as error:
        raise SyncError(reason, f"{label} must be a loopback IP address") from error
    if not parsed.is_loopback:
        raise SyncError(reason, f"{label} must be a loopback IP address")
    return value


def envelope_body(sender_id: str, recipient_id: str, sequence: int, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(sequence, int) or isinstance(sequence, bool) or not 0 < sequence < 1 << 63:
        raise SyncError("message_sequence", "message sequence must be a positive signed 63-bit integer")
    return {
        "format": PROTOCOL,
        "sender_id": sender_id,
        "recipient_id": recipient_id,
        "sequence": sequence,
        "payload": payload,
    }


def sign_envelope(
    sender_id: str,
    recipient_id: str,
    sequence: int,
    payload: dict[str, Any],
    key_hex: str,
) -> dict[str, Any]:
    key = bytes.fromhex(require_hex(key_hex, 32, "auth_key", "authentication key"))
    body = envelope_body(sender_id, recipient_id, sequence, payload)
    mac = hmac.new(key, AUTH_DOMAIN + canonical_bytes(body), hashlib.sha256).hexdigest()
    return {**body, "mac_sha256": mac}


def verify_envelope(
    envelope: Any,
    *,
    expected_sender: str,
    expected_recipient: str,
    key_hex: str,
) -> dict[str, Any]:
    fields = {"format", "sender_id", "recipient_id", "sequence", "payload", "mac_sha256"}
    if not isinstance(envelope, dict) or set(envelope) != fields:
        raise SyncError("message_fields", "message fields are not canonical")
    if envelope["format"] != PROTOCOL:
        raise SyncError("message_profile", "message uses the wrong protocol profile")
    if envelope["sender_id"] != expected_sender or envelope["recipient_id"] != expected_recipient:
        raise SyncError("message_route", "message sender or recipient is not the pinned route")
    if not isinstance(envelope["payload"], dict):
        raise SyncError("message_payload", "message payload must be an object")
    require_hex(envelope["mac_sha256"], 32, "message_authentication", "message MAC")
    expected = sign_envelope(
        expected_sender,
        expected_recipient,
        envelope["sequence"],
        envelope["payload"],
        key_hex,
    )["mac_sha256"]
    if not hmac.compare_digest(expected, envelope["mac_sha256"]):
        raise SyncError("message_authentication", "message MAC does not match the pinned peer key")
    return envelope


def load_config(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    fields = {
        "format",
        "node_id",
        "listen_host",
        "listen_port",
        "state_path",
        "control_key_hex",
        "trusted_rounds",
        "limits",
        "peers",
    }
    if not isinstance(document, dict) or set(document) != fields:
        raise SyncError("config_fields", "configuration fields are not canonical")
    if document["format"] != PROTOCOL:
        raise SyncError("config_profile", "configuration uses the wrong profile")
    node_id = document["node_id"]
    if not isinstance(node_id, str) or not node_id or len(node_id) > 32 or not node_id.isascii():
        raise SyncError("node_id", "node id must be 1-32 ASCII characters")
    require_loopback(document["listen_host"], "non_loopback", "private-lab listener")
    if not isinstance(document["listen_port"], int) or not 1 <= document["listen_port"] <= 65535:
        raise SyncError("listen_port", "listen port is invalid")
    if not isinstance(document["state_path"], str) or not document["state_path"]:
        raise SyncError("state_path", "state path is required")
    require_hex(document["control_key_hex"], 32, "control_key", "control key")
    reference.validate_rounds(document["trusted_rounds"])
    if document["limits"] != LIMITS:
        raise SyncError("config_limits", "configuration changes frozen resource limits")
    peers = document["peers"]
    if not isinstance(peers, list) or not 1 <= len(peers) <= MAX_PEERS:
        raise SyncError("peer_table", "peer table size is invalid")
    peer_fields = {"node_id", "host", "port", "shared_key_hex"}
    seen = set()
    for peer in peers:
        if not isinstance(peer, dict) or set(peer) != peer_fields:
            raise SyncError("peer_table", "peer entry fields are not canonical")
        if peer["node_id"] == node_id or peer["node_id"] in seen:
            raise SyncError("peer_table", "peer ids must be unique and exclude the local node")
        if not isinstance(peer["node_id"], str) or not peer["node_id"].isascii():
            raise SyncError("peer_table", "peer id is invalid")
        require_loopback(peer["host"], "non_loopback", "private-lab peer")
        if not isinstance(peer["port"], int) or not 1 <= peer["port"] <= 65535:
            raise SyncError("peer_table", "peer port is invalid")
        require_hex(peer["shared_key_hex"], 32, "peer_table", "peer shared key")
        seen.add(peer["node_id"])
    return document


def send_message(host: str, port: int, envelope: dict[str, Any]) -> dict[str, Any]:
    encoded = canonical_bytes(envelope) + b"\n"
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise SyncError("message_too_large", "outgoing message exceeds the frozen byte limit")
    with socket.create_connection((host, port), timeout=SOCKET_TIMEOUT_SECONDS) as connection:
        connection.settimeout(SOCKET_TIMEOUT_SECONDS)
        connection.sendall(encoded)
        reader = connection.makefile("rb")
        response = reader.readline(MAX_MESSAGE_BYTES + 1)
    if not response or len(response) > MAX_MESSAGE_BYTES or not response.endswith(b"\n"):
        raise SyncError("invalid_response", "peer returned no canonical bounded response")
    try:
        value = json.loads(response.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SyncError("invalid_response", "peer response is not canonical ASCII JSON") from error
    return value


class ShareSyncNode:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = copy.deepcopy(config)
        self.node_id = config["node_id"]
        self.state_path = Path(config["state_path"])
        self.rounds = copy.deepcopy(config["trusted_rounds"])
        self.round_index = reference.validate_rounds(self.rounds)
        self.peers = {item["node_id"]: copy.deepcopy(item) for item in config["peers"]}
        self.lock = threading.RLock()
        self.server: BoundedThreadingTCPServer | None = None
        self.state = self._load_state()

    def _empty_state(self) -> dict[str, Any]:
        return {
            "format": STATE_FORMAT,
            "node_id": self.node_id,
            "tick": 0,
            "accepted_shares": [],
            "orphans": [],
            "inbound_sequences": {},
            "outbound_sequences": {},
            "announcements": {},
            "equivocations": [],
            "rejection_counts": {},
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._empty_state()
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or set(state) != set(self._empty_state()):
            raise SyncError("state_fields", "persisted state fields are not canonical")
        if state["format"] != STATE_FORMAT or state["node_id"] != self.node_id:
            raise SyncError("state_profile", "persisted state belongs to another profile or node")
        if not isinstance(state["tick"], int) or state["tick"] < 0:
            raise SyncError("state_tick", "persisted tick is invalid")
        if not isinstance(state["accepted_shares"], list):
            raise SyncError("state_shares", "persisted accepted shares must be a list")
        self._validate_graph_pair(state["accepted_shares"])
        if not isinstance(state["orphans"], list) or len(state["orphans"]) > MAX_ORPHANS:
            raise SyncError("state_orphans", "persisted orphan set exceeds the frozen limit")
        for orphan in state["orphans"]:
            if not isinstance(orphan, dict) or set(orphan) != {"share", "arrival_tick"}:
                raise SyncError("state_orphans", "persisted orphan fields are invalid")
            reference.validate_share(orphan["share"], self.round_index)
            if (
                not isinstance(orphan["arrival_tick"], int)
                or isinstance(orphan["arrival_tick"], bool)
                or not 0 <= orphan["arrival_tick"] <= state["tick"]
            ):
                raise SyncError("state_orphans", "persisted orphan arrival tick is invalid")
        records = list(state["accepted_shares"]) + [item["share"] for item in state["orphans"]]
        if len(records) > MAX_KNOWN_SHARES:
            raise SyncError("state_shares", "persisted known-share set exceeds the frozen limit")
        if len({item["share_id_sha256"] for item in records}) != len(records):
            raise SyncError("state_shares", "persisted state repeats a share identifier")
        if len({item["work_id_sha256"] for item in records}) != len(records):
            raise SyncError("state_shares", "persisted state repeats a proof identity")
        allowed_routes = set(self.peers) | {CONTROL_ID}
        for field in ("inbound_sequences", "outbound_sequences"):
            rows = state[field]
            if not isinstance(rows, dict) or not set(rows).issubset(allowed_routes):
                raise SyncError("state_sequences", "persisted sequence routes are invalid")
            if any(
                not isinstance(value, int) or isinstance(value, bool) or not 0 < value < 1 << 63
                for value in rows.values()
            ):
                raise SyncError("state_sequences", "persisted sequence values are invalid")
        announcements = state["announcements"]
        if not isinstance(announcements, dict) or not set(announcements).issubset(self.peers):
            raise SyncError("state_announcements", "persisted announcement peers are invalid")
        for slots in announcements.values():
            if not isinstance(slots, dict) or len(slots) > MAX_ANNOUNCEMENT_SLOTS_PER_PEER:
                raise SyncError("state_announcements", "persisted announcement history exceeds its limit")
            if any(not isinstance(key, str) or not key.isdecimal() for key in slots):
                raise SyncError("state_announcements", "persisted announcement slot is invalid")
            if any(len(canonical_bytes(record)) > MAX_MESSAGE_BYTES * 2 for record in slots.values()):
                raise SyncError("state_announcements", "persisted announcement record is oversized")
        if not isinstance(state["equivocations"], list) or len(state["equivocations"]) > MAX_EQUIVOCATIONS:
            raise SyncError("state_equivocations", "persisted equivocation evidence exceeds its limit")
        rejection_counts = state["rejection_counts"]
        if (
            not isinstance(rejection_counts, dict)
            or len(rejection_counts) > 64
            or any(
                not isinstance(key, str)
                or not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                for key, value in rejection_counts.items()
            )
        ):
            raise SyncError("state_rejections", "persisted rejection counters are invalid")
        return state

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)

    def _record_rejection(self, reason: str) -> None:
        counts = self.state["rejection_counts"]
        counts[reason] = counts.get(reason, 0) + 1

    def _validate_graph_pair(self, shares: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not shares:
            return None
        reference_state = reference.evaluate_graph(shares, self.rounds)
        independent_state = independent.select_state(shares, self.rounds)
        if reference_state != independent_state:
            raise SyncError("validator_disagreement", "reference and independent sharechain states disagree")
        return reference_state

    def _accepted_ids(self) -> set[str]:
        return {item["share_id_sha256"] for item in self.state["accepted_shares"]}

    def _all_records(self) -> list[dict[str, Any]]:
        shares = list(self.state["accepted_shares"]) + [item["share"] for item in self.state["orphans"]]
        return sorted(shares, key=lambda item: (item["sequence"], item["share_id_sha256"]))

    def _work_ids(self) -> dict[str, str]:
        return {item["work_id_sha256"]: item["share_id_sha256"] for item in self._all_records()}

    def _prune_orphans(self) -> int:
        before = len(self.state["orphans"])
        minimum_tick = self.state["tick"] - MAX_ORPHAN_AGE_TICKS
        self.state["orphans"] = [
            item for item in self.state["orphans"] if item["arrival_tick"] >= minimum_tick
        ]
        removed = before - len(self.state["orphans"])
        if removed:
            self.state["rejection_counts"]["orphan_expired"] = (
                self.state["rejection_counts"].get("orphan_expired", 0) + removed
            )
        return removed

    def _promote_orphans(self) -> int:
        promoted = 0
        progress = True
        while progress:
            progress = False
            accepted_ids = self._accepted_ids()
            for record in sorted(
                list(self.state["orphans"]),
                key=lambda item: (item["share"]["sequence"], item["share"]["share_id_sha256"]),
            ):
                share = record["share"]
                if share["previous_share_id"] != ZERO_ID and share["previous_share_id"] not in accepted_ids:
                    continue
                candidate = self.state["accepted_shares"] + [share]
                try:
                    self._validate_graph_pair(candidate)
                except (reference.ProfileError, independent.Reject, SyncError) as error:
                    self.state["orphans"].remove(record)
                    reason = getattr(error, "reason", "orphan_invalid_after_parent")
                    self._record_rejection(reason)
                    progress = True
                    continue
                self.state["accepted_shares"].append(share)
                self.state["orphans"].remove(record)
                promoted += 1
                progress = True
        return promoted

    def _import_one(self, share: Any) -> str:
        reference.validate_share(share, self.round_index)
        share_id = share["share_id_sha256"]
        records = self._all_records()
        existing = next((item for item in records if item["share_id_sha256"] == share_id), None)
        if existing is not None:
            if existing != share:
                raise SyncError("share_collision", "one share id has conflicting content")
            return "duplicate"
        prior_work = self._work_ids().get(share["work_id_sha256"])
        if prior_work is not None:
            raise SyncError("duplicate_work_identity", "one proof appears under more than one share")
        if len(records) >= MAX_KNOWN_SHARES:
            raise SyncError("known_share_limit", "known-share limit is full")
        parent_known = share["previous_share_id"] == ZERO_ID or share["previous_share_id"] in self._accepted_ids()
        if not parent_known:
            if len(self.state["orphans"]) >= MAX_ORPHANS:
                raise SyncError("orphan_limit", "pending-orphan limit is full")
            self.state["orphans"].append({"share": copy.deepcopy(share), "arrival_tick": self.state["tick"]})
            return "orphan"
        self._validate_graph_pair(self.state["accepted_shares"] + [share])
        self.state["accepted_shares"].append(copy.deepcopy(share))
        self._promote_orphans()
        return "accepted"

    def import_shares(self, shares: Any) -> dict[str, Any]:
        if not isinstance(shares, list) or len(shares) > MAX_SHARES_PER_MESSAGE:
            raise SyncError("share_batch_limit", "share batch exceeds the frozen per-message limit")
        with self.lock:
            self.state["tick"] += 1
            expired = self._prune_orphans()
            summary = {"accepted": 0, "orphaned": 0, "duplicates": 0, "rejected": 0, "expired": expired}
            reasons: dict[str, int] = {}
            for share in shares:
                try:
                    result = self._import_one(share)
                    if result == "accepted":
                        summary["accepted"] += 1
                    elif result == "orphan":
                        summary["orphaned"] += 1
                    else:
                        summary["duplicates"] += 1
                except (reference.ProfileError, independent.Reject, SyncError) as error:
                    reason = getattr(error, "reason", "share_rejected")
                    summary["rejected"] += 1
                    reasons[reason] = reasons.get(reason, 0) + 1
                    self._record_rejection(reason)
            self._promote_orphans()
            self._save()
            return {**summary, "reasons": reasons}

    def _state_view(self) -> dict[str, Any]:
        graph_state = self._validate_graph_pair(self.state["accepted_shares"])
        commitment = canonical_hash(graph_state) if graph_state is not None else canonical_hash(None)
        return {
            "node_id": self.node_id,
            "tick": self.state["tick"],
            "accepted_share_count": len(self.state["accepted_shares"]),
            "orphan_count": len(self.state["orphans"]),
            "equivocation_count": len(self.state["equivocations"]),
            "selected_state": graph_state,
            "state_commitment_sha256": commitment,
            "rejection_counts": copy.deepcopy(self.state["rejection_counts"]),
        }

    def status(self) -> dict[str, Any]:
        with self.lock:
            return self._state_view()

    def _next_outbound(self, recipient: str) -> int:
        current = self.state["outbound_sequences"].get(recipient, 0) + 1
        self.state["outbound_sequences"][recipient] = current
        self._save()
        return current

    def _key_for_sender(self, sender: str) -> str:
        if sender == CONTROL_ID:
            return self.config["control_key_hex"]
        peer = self.peers.get(sender)
        if peer is None:
            raise SyncError("unknown_peer", "sender is absent from the pinned peer table")
        return peer["shared_key_hex"]

    def _authenticate_inbound(self, envelope: Any) -> dict[str, Any]:
        if not isinstance(envelope, dict):
            raise SyncError("message_fields", "message must be an object")
        sender = envelope.get("sender_id")
        if not isinstance(sender, str):
            raise SyncError("message_route", "message sender is invalid")
        key = self._key_for_sender(sender)
        checked = verify_envelope(
            envelope,
            expected_sender=sender,
            expected_recipient=self.node_id,
            key_hex=key,
        )
        prior = self.state["inbound_sequences"].get(sender, 0)
        if checked["sequence"] <= prior:
            raise SyncError("message_replay", "message sequence is not newer than the pinned peer state")
        self.state["inbound_sequences"][sender] = checked["sequence"]
        self._save()
        return checked

    def _sign_response(self, recipient: str, payload: dict[str, Any]) -> dict[str, Any]:
        sequence = self._next_outbound(recipient)
        return sign_envelope(self.node_id, recipient, sequence, payload, self._key_for_sender(recipient))

    def _announcement(self) -> dict[str, Any]:
        view = self._state_view()
        return {
            "slot": self.state["tick"],
            "state_commitment_sha256": view["state_commitment_sha256"],
            "selected_tip_share_id": (
                ZERO_ID if view["selected_state"] is None else view["selected_state"]["selected_tip_share_id"]
            ),
        }

    def _observe_announcement(self, envelope: dict[str, Any]) -> None:
        announcement = envelope["payload"].get("announcement")
        if announcement is None:
            return
        fields = {"slot", "state_commitment_sha256", "selected_tip_share_id"}
        if not isinstance(announcement, dict) or set(announcement) != fields:
            raise SyncError("announcement_fields", "announcement fields are not canonical")
        if not isinstance(announcement["slot"], int) or announcement["slot"] < 0:
            raise SyncError("announcement_slot", "announcement slot is invalid")
        require_hex(announcement["state_commitment_sha256"], 32, "announcement_commitment", "state commitment")
        require_hex(announcement["selected_tip_share_id"], 32, "announcement_commitment", "selected tip")
        sender = envelope["sender_id"]
        slots = self.state["announcements"].setdefault(sender, {})
        key = str(announcement["slot"])
        previous = slots.get(key)
        record = {"announcement": copy.deepcopy(announcement), "authenticated_envelope": copy.deepcopy(envelope)}
        if previous is None:
            if len(slots) >= MAX_ANNOUNCEMENT_SLOTS_PER_PEER:
                oldest = min(slots, key=lambda item: int(item))
                if announcement["slot"] <= int(oldest):
                    return
                del slots[oldest]
            slots[key] = record
            return
        if previous["announcement"] != announcement:
            evidence = {
                "sender_id": sender,
                "slot": announcement["slot"],
                "first": previous,
                "second": record,
            }
            evidence["evidence_commitment_sha256"] = canonical_hash(evidence)
            if len(self.state["equivocations"]) >= MAX_EQUIVOCATIONS:
                raise SyncError("equivocation_limit", "equivocation evidence limit is full")
            if evidence["evidence_commitment_sha256"] not in {
                item["evidence_commitment_sha256"] for item in self.state["equivocations"]
            }:
                self.state["equivocations"].append(evidence)

    def handle_envelope(self, raw: Any) -> dict[str, Any]:
        with self.lock:
            envelope = self._authenticate_inbound(raw)
            self.state["tick"] += 1
            self._prune_orphans()
            self._observe_announcement(envelope)
            sender = envelope["sender_id"]
            payload = envelope["payload"]
            op = payload.get("op")
            if sender == CONTROL_ID:
                if op == "status":
                    response_payload = {"op": "status_response", "status": self._state_view()}
                elif op == "import":
                    response_payload = {"op": "import_response", "summary": self.import_shares(payload.get("shares"))}
                elif op == "tick":
                    count = payload.get("count")
                    if not isinstance(count, int) or not 1 <= count <= MAX_ORPHAN_AGE_TICKS + 1:
                        raise SyncError("tick_count", "control tick count is invalid")
                    self.state["tick"] += count
                    removed = self._prune_orphans()
                    response_payload = {"op": "tick_response", "expired": removed}
                elif op == "sync":
                    peer_id = payload.get("peer_id")
                    response_payload = {"op": "sync_response", "summary": self.sync_peer(peer_id)}
                elif op == "stop":
                    response_payload = {"op": "stop_response", "stopping": True}
                    if self.server is not None:
                        threading.Thread(target=self.server.shutdown, daemon=True).start()
                else:
                    raise SyncError("control_operation", "unknown local control operation")
                self._save()
                return self._sign_response(CONTROL_ID, response_payload)
            if op == "inventory":
                cursor = payload.get("cursor")
                if not isinstance(cursor, int) or isinstance(cursor, bool) or not 0 <= cursor <= MAX_KNOWN_SHARES:
                    raise SyncError("inventory_cursor", "peer inventory cursor is invalid")
                records = self._all_records()
                page = records[cursor : cursor + MAX_INVENTORY_IDS_PER_MESSAGE]
                next_cursor = cursor + len(page)
                response_payload = {
                    "op": "inventory_response",
                    "share_ids": [item["share_id_sha256"] for item in page],
                    "next_cursor": None if next_cursor >= len(records) else next_cursor,
                    "announcement": self._announcement(),
                }
            elif op == "pull":
                requested = payload.get("share_ids")
                if not isinstance(requested, list) or len(requested) > MAX_SHARES_PER_MESSAGE:
                    raise SyncError("pull_limit", "share pull exceeds the per-message limit")
                if len(set(requested)) != len(requested):
                    raise SyncError("pull_identifiers", "share pull repeats an identifier")
                for share_id in requested:
                    require_hex(share_id, 32, "pull_identifiers", "requested share id")
                records = {item["share_id_sha256"]: item for item in self._all_records()}
                response_payload = {
                    "op": "pull_response",
                    "shares": [records[share_id] for share_id in requested if share_id in records],
                    "announcement": self._announcement(),
                }
            elif op == "push":
                summary = self.import_shares(payload.get("shares"))
                response_payload = {
                    "op": "push_response",
                    "summary": summary,
                    "announcement": self._announcement(),
                }
            else:
                raise SyncError("peer_operation", "unknown peer operation")
            self._save()
            return self._sign_response(sender, response_payload)

    def _peer_round_trip(self, peer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        peer = self.peers.get(peer_id)
        if peer is None:
            raise SyncError("unknown_peer", "sync target is absent from the pinned peer table")
        with self.lock:
            payload = {**payload, "announcement": self._announcement()}
            sequence = self._next_outbound(peer_id)
            envelope = sign_envelope(self.node_id, peer_id, sequence, payload, peer["shared_key_hex"])
        response = send_message(peer["host"], peer["port"], envelope)
        with self.lock:
            checked = self._authenticate_inbound(response)
            self._observe_announcement(checked)
            self._save()
            return checked["payload"]

    def sync_peer(self, peer_id: Any) -> dict[str, Any]:
        if not isinstance(peer_id, str):
            raise SyncError("unknown_peer", "sync target id is invalid")
        totals = {"operations": 0, "received": 0, "pushed": 0, "rejected": 0, "converged": False}
        peer_known: list[str] = []
        cursor = 0
        for _ in range(MAX_INVENTORY_PAGES):
            response = self._peer_round_trip(peer_id, {"op": "inventory", "cursor": cursor})
            totals["operations"] += 1
            if response.get("op") != "inventory_response":
                raise SyncError("invalid_response", "peer returned the wrong inventory response")
            page = response.get("share_ids")
            next_cursor = response.get("next_cursor")
            if not isinstance(page, list) or len(page) > MAX_INVENTORY_IDS_PER_MESSAGE:
                raise SyncError("inventory_limit", "peer inventory page exceeds the limit")
            for share_id in page:
                require_hex(share_id, 32, "inventory_identifier", "inventory share id")
            peer_known.extend(page)
            if len(peer_known) > MAX_KNOWN_SHARES or len(set(peer_known)) != len(peer_known):
                raise SyncError("inventory_limit", "peer inventory is oversized or repeats identifiers")
            if next_cursor is None:
                break
            if not isinstance(next_cursor, int) or next_cursor != cursor + len(page):
                raise SyncError("inventory_cursor", "peer inventory cursor is not canonical")
            cursor = next_cursor
        else:
            raise SyncError("inventory_page_limit", "peer inventory did not finish within the page limit")

        with self.lock:
            local_before = {item["share_id_sha256"] for item in self._all_records()}
        missing_local = [share_id for share_id in peer_known if share_id not in local_before]
        for offset in range(0, len(missing_local), MAX_SHARES_PER_MESSAGE):
            requested = missing_local[offset : offset + MAX_SHARES_PER_MESSAGE]
            pulled = self._peer_round_trip(peer_id, {"op": "pull", "share_ids": requested})
            totals["operations"] += 1
            if pulled.get("op") != "pull_response":
                raise SyncError("invalid_response", "peer returned the wrong pull response")
            received = pulled.get("shares")
            if (
                not isinstance(received, list)
                or len(received) != len(requested)
                or not all(isinstance(item, dict) for item in received)
                or {item["share_id_sha256"] for item in received} != set(requested)
            ):
                raise SyncError("invalid_response", "peer did not return the exact requested share set")
            import_summary = self.import_shares(received)
            totals["received"] += len(received)
            totals["rejected"] += import_summary["rejected"]

        with self.lock:
            outgoing = [item for item in self._all_records() if item["share_id_sha256"] not in set(peer_known)]
        for offset in range(0, len(outgoing), MAX_SHARES_PER_MESSAGE):
            batch = outgoing[offset : offset + MAX_SHARES_PER_MESSAGE]
            pushed = self._peer_round_trip(peer_id, {"op": "push", "shares": batch})
            totals["operations"] += 1
            if pushed.get("op") != "push_response":
                raise SyncError("invalid_response", "peer returned the wrong push response")
            push_summary = pushed["summary"]
            totals["pushed"] += len(batch)
            totals["rejected"] += push_summary["rejected"]
        if totals["operations"] > MAX_SYNC_OPERATIONS:
            raise SyncError("sync_operation_limit", "peer synchronization exceeded the operation limit")

        final_peer_ids: list[str] = []
        cursor = 0
        for _ in range(MAX_INVENTORY_PAGES):
            response = self._peer_round_trip(peer_id, {"op": "inventory", "cursor": cursor})
            totals["operations"] += 1
            if response.get("op") != "inventory_response":
                raise SyncError("invalid_response", "peer returned the wrong final inventory response")
            page = response["share_ids"]
            final_peer_ids.extend(page)
            next_cursor = response["next_cursor"]
            if next_cursor is None:
                break
            cursor = next_cursor
        with self.lock:
            final_local_ids = [item["share_id_sha256"] for item in self._all_records()]
        totals["converged"] = set(final_local_ids) == set(final_peer_ids)
        if not totals["converged"]:
            raise SyncError("sync_not_converged", "peer inventories differ after bounded synchronization")
        if totals["operations"] > MAX_SYNC_OPERATIONS:
            raise SyncError("sync_operation_limit", "peer synchronization exceeded the operation limit")
        return totals


class BoundedRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(SOCKET_TIMEOUT_SECONDS)
        raw = self.rfile.readline(MAX_MESSAGE_BYTES + 1)
        if not raw or len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
            return
        try:
            envelope = json.loads(raw.decode("ascii"))
            response = self.server.node.handle_envelope(envelope)  # type: ignore[attr-defined]
            encoded = canonical_bytes(response) + b"\n"
            if len(encoded) <= MAX_MESSAGE_BYTES:
                self.wfile.write(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError, OSError, SyncError, reference.ProfileError, independent.Reject):
            return


class BoundedThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], node: ShareSyncNode) -> None:
        self.node = node
        self.connection_slots = threading.BoundedSemaphore(MAX_CONCURRENT_CONNECTIONS)
        super().__init__(address, BoundedRequestHandler)

    def process_request(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        if not self.connection_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.connection_slots.release()
            raise

    def process_request_thread(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connection_slots.release()


def serve(config: dict[str, Any]) -> int:
    node = ShareSyncNode(config)
    with BoundedThreadingTCPServer((config["listen_host"], config["listen_port"]), node) as server:
        node.server = server
        print(json.dumps({"event": "ready", "node_id": node.node_id}, sort_keys=True), flush=True)
        server.serve_forever(poll_interval=0.05)
    return 0


def control(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    sequence = time.time_ns() & ((1 << 63) - 1)
    request = sign_envelope(CONTROL_ID, config["node_id"], sequence, payload, config["control_key_hex"])
    response = send_message(config["listen_host"], config["listen_port"], request)
    checked = verify_envelope(
        response,
        expected_sender=config["node_id"],
        expected_recipient=CONTROL_ID,
        key_hex=config["control_key_hex"],
    )
    return checked["payload"]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("serve", "status", "stop"):
        child = subparsers.add_parser(command)
        child.add_argument("--config", type=Path, required=True)
    importer = subparsers.add_parser("import")
    importer.add_argument("--config", type=Path, required=True)
    importer.add_argument("--shares", type=Path, required=True)
    sync = subparsers.add_parser("sync")
    sync.add_argument("--config", type=Path, required=True)
    sync.add_argument("--peer", required=True)
    tick = subparsers.add_parser("tick")
    tick.add_argument("--config", type=Path, required=True)
    tick.add_argument("--count", type=int, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    config = load_config(args.config)
    if args.command == "serve":
        return serve(config)
    if args.command == "status":
        result = control(config, {"op": "status"})
    elif args.command == "stop":
        result = control(config, {"op": "stop"})
    elif args.command == "import":
        shares = json.loads(args.shares.read_text(encoding="utf-8"))
        result = control(config, {"op": "import", "shares": shares})
    elif args.command == "sync":
        result = control(config, {"op": "sync", "peer_id": args.peer})
    else:
        result = control(config, {"op": "tick", "count": args.count})
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, SyncError, reference.ProfileError, independent.Reject) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
