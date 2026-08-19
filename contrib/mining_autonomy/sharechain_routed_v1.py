#!/usr/bin/env python3
"""Live signed-session boundary for the routed Soveroot share-sync laboratory.

The validator and share-selection state remain the independently checked v0
implementation. Peer TCP traffic never carries a v0 pairwise key envelope:
each request uses a pinned Ed25519 identity, fresh X25519 session transcript,
and the bounded v1 admission controller. The v0 envelope built below exists
only in memory as an adapter into the already-tested validator state machine.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import ipaddress
import json
import os
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path
from typing import Any, Sequence

import independent_sharechain_v0 as independent
import sharechain_multihost_v1 as safety
import sharechain_sync_v0 as sync
import sharechain_v0 as reference


CONFIG_FORMAT = "soveroot-share-sync-routed-config-v1"
TRANSPORT_STATE_FORMAT = "soveroot-share-sync-routed-transport-state-v1"
CONTROL_ID = sync.CONTROL_ID
MAX_TRANSCRIPT_COMMITMENTS = 128
SOCKET_TIMEOUT_SECONDS = 30.0
TRANSPORT_LIMITS = {
    "socket_timeout_seconds": 30,
    "max_transcript_commitments": MAX_TRANSCRIPT_COMMITMENTS,
}


class RoutedError(RuntimeError):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


def canonical_bytes(value: Any) -> bytes:
    return safety.canonical_bytes(value)


def _require_text(value: Any, reason: str, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or not value.isascii():
        raise RoutedError(reason, f"{label} must be 1-{limit} ASCII characters")
    return value


def _require_ip(value: Any, reason: str, label: str) -> str:
    if not isinstance(value, str):
        raise RoutedError(reason, f"{label} must be an IP literal")
    try:
        ipaddress.ip_address(value)
    except ValueError as error:
        raise RoutedError(reason, f"{label} must be an IP literal") from error
    return value


def _internal_key(left: str, right: str) -> str:
    pair = "\x00".join(sorted((left, right))).encode("ascii")
    return hashlib.sha256(b"soveroot/share-sync/internal-adapter/v1\x00" + pair).hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    fields = {
        "format", "node_id", "listen_host", "listen_port", "endpoint",
        "control_host", "state_path", "transport_state_path", "control_key_hex",
        "identity_seed_hex", "operator_group", "transport", "network_id",
        "trusted_rounds", "limits", "peers",
    }
    if not isinstance(document, dict) or set(document) != fields:
        raise RoutedError("config_fields", "routed configuration fields are not canonical")
    if document["format"] != CONFIG_FORMAT or document["network_id"] != safety.NETWORK_ID:
        raise RoutedError("config_profile", "configuration uses the wrong routed profile or network")
    node_id = _require_text(document["node_id"], "node_id", "node id", 32)
    listen_host = _require_ip(document["listen_host"], "listen_host", "listener")
    control_host = _require_ip(document["control_host"], "control_host", "controller source")
    port = document["listen_port"]
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise RoutedError("listen_port", "listener port is invalid")
    endpoint = _require_text(document["endpoint"], "endpoint", "signed endpoint", 128)
    if endpoint != f"{listen_host}:{port}":
        raise RoutedError("endpoint", "signed endpoint does not match the listener")
    for field in ("state_path", "transport_state_path"):
        if not isinstance(document[field], str) or not document[field]:
            raise RoutedError("state_path", f"{field} is required")
    safety.require_hex(document["control_key_hex"], 32, "control_key", "control key")
    safety.require_hex(document["identity_seed_hex"], 32, "identity_seed", "identity seed")
    _require_text(document["operator_group"], "operator_group", "operator group", 64)
    _require_text(document["transport"], "transport", "transport", 32)
    reference.validate_rounds(document["trusted_rounds"])
    if document["limits"] != {
        "sync": sync.LIMITS,
        "safety": safety.LIMITS,
        "transport": TRANSPORT_LIMITS,
    }:
        raise RoutedError("config_limits", "configuration changes frozen resource limits")

    peers = document["peers"]
    peer_fields = {
        "node_id", "host", "port", "endpoint", "identity_public_key_hex",
        "operator_group", "transport",
    }
    if not isinstance(peers, list) or not 3 <= len(peers) <= sync.MAX_PEERS:
        raise RoutedError("peer_table", "routed profile requires three to eight pinned peers")
    seen_ids: set[str] = set()
    candidates = []
    for priority, peer in enumerate(peers):
        if not isinstance(peer, dict) or set(peer) != peer_fields:
            raise RoutedError("peer_table", "peer entry fields are not canonical")
        peer_id = _require_text(peer["node_id"], "peer_table", "peer id", 32)
        if peer_id == node_id or peer_id in seen_ids:
            raise RoutedError("peer_table", "peer ids must be unique and exclude the local node")
        seen_ids.add(peer_id)
        host = _require_ip(peer["host"], "peer_table", "peer host")
        if not isinstance(peer["port"], int) or isinstance(peer["port"], bool) or not 1 <= peer["port"] <= 65535:
            raise RoutedError("peer_table", "peer port is invalid")
        if peer["endpoint"] != f"{host}:{peer['port']}":
            raise RoutedError("peer_table", "peer signed endpoint does not match its route")
        safety.require_hex(peer["identity_public_key_hex"], 32, "peer_table", "peer identity key")
        _require_text(peer["operator_group"], "peer_table", "peer operator group", 64)
        _require_text(peer["transport"], "peer_table", "peer transport", 32)
        candidates.append({
            "peer_id": peer_id,
            "address": host,
            "operator_group": peer["operator_group"],
            "transport": peer["transport"],
            "priority": priority,
        })
    safety.select_diverse_peers(candidates)
    if safety.identity_public_key(document["identity_seed_hex"]) in {
        peer["identity_public_key_hex"] for peer in peers
    }:
        raise RoutedError("identity_key", "local identity key is reused by a peer")
    if safety.source_prefix(listen_host) in {safety.source_prefix(peer["host"]) for peer in peers}:
        raise RoutedError("peer_table", "local and peer listeners must use different source prefixes")
    if control_host == listen_host:
        raise RoutedError("control_host", "controller and listener addresses must differ")
    return document


def _legacy_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": sync.PROTOCOL,
        "node_id": config["node_id"],
        "listen_host": config["listen_host"],
        "listen_port": config["listen_port"],
        "state_path": config["state_path"],
        "control_key_hex": config["control_key_hex"],
        "trusted_rounds": config["trusted_rounds"],
        "limits": sync.LIMITS,
        "peers": [
            {**peer, "shared_key_hex": _internal_key(config["node_id"], peer["node_id"])}
            for peer in config["peers"]
        ],
    }


def _read_json_line(reader: Any, limit: int) -> tuple[dict[str, Any], int]:
    raw = reader.readline(limit + 2)
    if not raw or len(raw) > limit + 1 or not raw.endswith(b"\n"):
        raise RoutedError("wire_size", "peer sent no canonical bounded line")
    try:
        value = json.loads(raw[:-1].decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RoutedError("wire_encoding", "peer line is not canonical ASCII JSON") from error
    if not isinstance(value, dict):
        raise RoutedError("wire_fields", "peer line must be an object")
    return value, len(raw) - 1


def _write_json_line(writer: Any, value: dict[str, Any], limit: int) -> None:
    encoded = canonical_bytes(value)
    if len(encoded) > limit:
        raise RoutedError("wire_size", "outgoing peer line exceeds its frozen limit")
    writer.write(encoded + b"\n")
    writer.flush()


class RoutedShareSyncNode(sync.ShareSyncNode):
    def __init__(self, config: dict[str, Any]) -> None:
        self.routed_config = copy.deepcopy(config)
        super().__init__(_legacy_config(config))
        self.config = copy.deepcopy(config)
        self.identity_seed_hex = config["identity_seed_hex"]
        self.transport_state_path = Path(config["transport_state_path"])
        self.transport_lock = threading.RLock()
        self.admission, self.transport_state = self._load_transport_state()

    def _empty_transport_state(self) -> dict[str, Any]:
        return {
            "format": TRANSPORT_STATE_FORMAT,
            "accepted_inbound_sessions": 0,
            "accepted_inbound_frames": 0,
            "transcript_commitments": [],
            "observed_source_prefixes": [],
            "rejected_connections": {},
        }

    def _load_transport_state(self) -> tuple[safety.AdmissionController, dict[str, Any]]:
        if not self.transport_state_path.exists():
            return safety.AdmissionController(), self._empty_transport_state()
        document = json.loads(self.transport_state_path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or set(document) != {"transport", "admission"}:
            raise RoutedError("transport_state", "transport state fields are invalid")
        state = document["transport"]
        empty = self._empty_transport_state()
        if not isinstance(state, dict) or set(state) != set(empty) or state["format"] != TRANSPORT_STATE_FORMAT:
            raise RoutedError("transport_state", "transport counters are invalid")
        for field in ("accepted_inbound_sessions", "accepted_inbound_frames"):
            if not isinstance(state[field], int) or isinstance(state[field], bool) or state[field] < 0:
                raise RoutedError("transport_state", "transport counter is invalid")
        transcripts = state["transcript_commitments"]
        if not isinstance(transcripts, list) or len(transcripts) > MAX_TRANSCRIPT_COMMITMENTS:
            raise RoutedError("transport_state", "transcript history exceeds its bound")
        for value in transcripts:
            safety.require_hex(value, 32, "transport_state", "transcript commitment")
        prefixes = state["observed_source_prefixes"]
        if not isinstance(prefixes, list) or len(prefixes) > sync.MAX_PEERS:
            raise RoutedError("transport_state", "source-prefix history exceeds its bound")
        for value in prefixes:
            if safety.source_prefix(value.split("/")[0]) != value:
                raise RoutedError("transport_state", "source-prefix history is non-canonical")
        rejections = state["rejected_connections"]
        if not isinstance(rejections, dict) or len(rejections) > 64 or any(
            not isinstance(key, str) or not isinstance(value, int) or value < 0
            for key, value in rejections.items()
        ):
            raise RoutedError("transport_state", "transport rejection counters are invalid")
        admission = safety.AdmissionController(document["admission"])
        # TCP sessions cannot survive process restart. Replay, bucket, and
        # quarantine evidence remains; only stale live-connection counts reset.
        admission.active_identity.clear()
        admission.active_prefix.clear()
        return admission, state

    def _save_transport_state(self) -> None:
        self.transport_state_path.parent.mkdir(parents=True, exist_ok=True)
        document = {"transport": self.transport_state, "admission": self.admission.snapshot()}
        temporary = self.transport_state_path.with_suffix(self.transport_state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.transport_state_path)

    def _reject_transport(self, reason: str) -> None:
        with self.transport_lock:
            counts = self.transport_state["rejected_connections"]
            counts[reason] = counts.get(reason, 0) + 1
            self._save_transport_state()

    def _peer(self, peer_id: str) -> dict[str, Any]:
        peer = self.peers.get(peer_id)
        if peer is None:
            raise RoutedError("unknown_peer", "peer is absent from the pinned table")
        return peer

    def _announcement(self) -> dict[str, Any]:
        view = super()._state_view()
        return safety.signed_announcement(
            identity_seed_hex=self.identity_seed_hex,
            peer_id=self.node_id,
            slot=self.state["tick"],
            selected_tip_share_id=(
                sync.ZERO_ID if view["selected_state"] is None
                else view["selected_state"]["selected_tip_share_id"]
            ),
            state_commitment_sha256=view["state_commitment_sha256"],
        )

    def _observe_announcement(self, envelope: dict[str, Any]) -> None:
        announcement = envelope["payload"].get("announcement")
        if announcement is None:
            return
        sender = envelope["sender_id"]
        peer = self._peer(sender)
        checked = safety.verify_announcement(
            announcement, peer["identity_public_key_hex"], sender
        )
        slots = self.state["announcements"].setdefault(sender, {})
        key = str(checked["slot"])
        prior = slots.get(key)
        record = {"signed_announcement": copy.deepcopy(checked)}
        if prior is None:
            if len(slots) >= sync.MAX_ANNOUNCEMENT_SLOTS_PER_PEER:
                oldest = min(slots, key=lambda item: int(item))
                if checked["slot"] <= int(oldest):
                    return
                del slots[oldest]
            slots[key] = record
            return
        first = prior["signed_announcement"]
        if first != checked:
            evidence = safety.equivocation_evidence(
                first, checked, peer["identity_public_key_hex"], sender
            )
            if len(self.state["equivocations"]) >= sync.MAX_EQUIVOCATIONS:
                raise sync.SyncError("equivocation_limit", "equivocation evidence limit is full")
            if evidence["evidence_commitment_sha256"] not in {
                item["evidence_commitment_sha256"] for item in self.state["equivocations"]
            }:
                self.state["equivocations"].append(evidence)

    def transport_status(self) -> dict[str, Any]:
        with self.transport_lock:
            return {
                "accepted_inbound_sessions": self.transport_state["accepted_inbound_sessions"],
                "accepted_inbound_frames": self.transport_state["accepted_inbound_frames"],
                "distinct_transcript_count": len(set(self.transport_state["transcript_commitments"])),
                "observed_source_prefixes": list(self.transport_state["observed_source_prefixes"]),
                "remembered_replay_nonce_count": len(self.admission.replay_nonces),
                "quarantine_count": len(self.admission.quarantines),
                "rejected_connections": copy.deepcopy(self.transport_state["rejected_connections"]),
            }

    def _state_view(self) -> dict[str, Any]:
        return {**super()._state_view(), "routed_transport": self.transport_status()}

    def handle_peer_session(self, reader: Any, writer: Any, hello: dict[str, Any], source_ip: str) -> None:
        peer_id = hello.get("peer_id")
        if not isinstance(peer_id, str):
            raise RoutedError("hello_peer", "hello peer id is missing")
        peer = self._peer(peer_id)
        if source_ip != peer["host"]:
            raise RoutedError("source_identity_mismatch", "source IP does not match the pinned peer route")
        now = int(time.time())
        admitted = False
        try:
            with self.transport_lock:
                prefix = self.admission.admit_handshake(
                    peer_id=peer_id,
                    source_ip=source_ip,
                    nonce_hex=hello.get("nonce_hex"),
                    tick=now,
                )
                admitted = True
                self._save_transport_state()
            safety.verify_hello(
                hello,
                expected_peer_id=peer_id,
                expected_public_key_hex=peer["identity_public_key_hex"],
                expected_role="initiator",
                expected_operator_group=peer["operator_group"],
                expected_transport=peer["transport"],
                expected_endpoint=peer["endpoint"],
                current_tick=now,
            )
            private = os.urandom(32)
            responder = safety.make_hello(
                peer_id=self.node_id,
                identity_seed_hex=self.identity_seed_hex,
                operator_group=self.config["operator_group"],
                transport=self.config["transport"],
                endpoint=self.config["endpoint"],
                role="responder",
                ephemeral_private_key=private,
                nonce_hex=os.urandom(32).hex(),
                issued_tick=now,
            )
            session_key, transcript = safety.derive_session_key(
                local_ephemeral_private=private,
                initiator_hello=hello,
                responder_hello=responder,
            )
            with self.transport_lock:
                self.transport_state["accepted_inbound_sessions"] += 1
                history = self.transport_state["transcript_commitments"]
                history.append(transcript)
                del history[:-MAX_TRANSCRIPT_COMMITMENTS]
                if prefix not in self.transport_state["observed_source_prefixes"]:
                    self.transport_state["observed_source_prefixes"].append(prefix)
                    self.transport_state["observed_source_prefixes"].sort()
                self._save_transport_state()
            _write_json_line(writer, responder, safety.MAX_HELLO_BYTES)
            prior = self.state["inbound_sequences"].get(peer_id, 0)
            while True:
                try:
                    frame, frame_bytes = _read_json_line(reader, safety.MAX_FRAME_BYTES)
                except RoutedError as error:
                    if error.reason == "wire_size":
                        return
                    raise
                current = int(time.time())
                with self.transport_lock:
                    self.admission.admit_message(
                        peer_id=peer_id, frame_bytes=frame_bytes, tick=current
                    )
                    self._save_transport_state()
                checked = safety.verify_session_envelope(
                    frame,
                    session_key_hex=session_key,
                    transcript_sha256=transcript,
                    expected_sender=peer_id,
                    expected_recipient=self.node_id,
                    prior_sequence=prior,
                    session_start_tick=now,
                    current_tick=current,
                )
                synthetic = sync.sign_envelope(
                    peer_id,
                    self.node_id,
                    checked["sequence"],
                    checked["payload"],
                    peer["shared_key_hex"],
                )
                response = super().handle_envelope(synthetic)
                outbound = safety.session_envelope(
                    session_key_hex=session_key,
                    transcript_sha256=transcript,
                    sender_id=self.node_id,
                    recipient_id=peer_id,
                    sequence=response["sequence"],
                    issued_tick=current,
                    payload=response["payload"],
                )
                _write_json_line(writer, outbound, safety.MAX_FRAME_BYTES)
                prior = checked["sequence"]
                with self.transport_lock:
                    self.transport_state["accepted_inbound_frames"] += 1
                    self._save_transport_state()
        except (RoutedError, safety.SafetyError, sync.SyncError) as error:
            self._reject_transport(getattr(error, "reason", "transport_rejected"))
            raise
        finally:
            if admitted:
                with self.transport_lock:
                    self.admission.close_session(peer_id=peer_id, source_ip=source_ip)
                    self._save_transport_state()

    def _peer_round_trip(self, peer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        peer = self._peer(peer_id)
        with self.lock:
            payload = {**payload, "announcement": self._announcement()}
            sequence = self._next_outbound(peer_id)
        started = int(time.time())
        private = os.urandom(32)
        hello = safety.make_hello(
            peer_id=self.node_id,
            identity_seed_hex=self.identity_seed_hex,
            operator_group=self.config["operator_group"],
            transport=self.config["transport"],
            endpoint=self.config["endpoint"],
            role="initiator",
            ephemeral_private_key=private,
            nonce_hex=os.urandom(32).hex(),
            issued_tick=started,
        )
        with socket.create_connection(
            (peer["host"], peer["port"]),
            timeout=SOCKET_TIMEOUT_SECONDS,
            source_address=(self.config["listen_host"], 0),
        ) as connection:
            connection.settimeout(SOCKET_TIMEOUT_SECONDS)
            reader = connection.makefile("rb")
            writer = connection.makefile("wb")
            _write_json_line(writer, hello, safety.MAX_HELLO_BYTES)
            responder, _ = _read_json_line(reader, safety.MAX_HELLO_BYTES)
            current = int(time.time())
            safety.verify_hello(
                responder,
                expected_peer_id=peer_id,
                expected_public_key_hex=peer["identity_public_key_hex"],
                expected_role="responder",
                expected_operator_group=peer["operator_group"],
                expected_transport=peer["transport"],
                expected_endpoint=peer["endpoint"],
                current_tick=current,
            )
            session_key, transcript = safety.derive_session_key(
                local_ephemeral_private=private,
                initiator_hello=hello,
                responder_hello=responder,
            )
            frame = safety.session_envelope(
                session_key_hex=session_key,
                transcript_sha256=transcript,
                sender_id=self.node_id,
                recipient_id=peer_id,
                sequence=sequence,
                issued_tick=current,
                payload=payload,
            )
            _write_json_line(writer, frame, safety.MAX_FRAME_BYTES)
            response, _ = _read_json_line(reader, safety.MAX_FRAME_BYTES)
        with self.lock:
            prior = self.state["inbound_sequences"].get(peer_id, 0)
            checked = safety.verify_session_envelope(
                response,
                session_key_hex=session_key,
                transcript_sha256=transcript,
                expected_sender=peer_id,
                expected_recipient=self.node_id,
                prior_sequence=prior,
                session_start_tick=started,
                current_tick=int(time.time()),
            )
            synthetic = sync.sign_envelope(
                peer_id,
                self.node_id,
                checked["sequence"],
                checked["payload"],
                peer["shared_key_hex"],
            )
            authenticated = self._authenticate_inbound(synthetic)
            self._observe_announcement(authenticated)
            self._save()
            return authenticated["payload"]


class RoutedRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(SOCKET_TIMEOUT_SECONDS)
        try:
            # Laboratory control imports may be as large as a share frame. A
            # peer hello is still rejected by verify_hello above its smaller
            # frozen bound after this single bounded read.
            first, _ = _read_json_line(self.rfile, safety.MAX_FRAME_BYTES)
            node: RoutedShareSyncNode = self.server.node  # type: ignore[attr-defined]
            source_ip = str(self.client_address[0])
            if first.get("format") == sync.PROTOCOL and first.get("sender_id") == CONTROL_ID:
                if source_ip != node.config["control_host"]:
                    raise RoutedError("control_source", "controller source is not pinned")
                response = sync.ShareSyncNode.handle_envelope(node, first)
                _write_json_line(self.wfile, response, sync.MAX_MESSAGE_BYTES)
                return
            node.handle_peer_session(self.rfile, self.wfile, first, source_ip)
        except (
            UnicodeDecodeError, json.JSONDecodeError, OSError, RoutedError,
            safety.SafetyError, sync.SyncError, reference.ProfileError, independent.Reject,
        ):
            return


class RoutedTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], node: RoutedShareSyncNode) -> None:
        self.node = node
        self.connection_slots = threading.BoundedSemaphore(safety.MAX_ACTIVE_SESSIONS)
        super().__init__(address, RoutedRequestHandler)

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
    node = RoutedShareSyncNode(config)
    with RoutedTCPServer((config["listen_host"], config["listen_port"]), node) as server:
        node.server = server
        print(json.dumps({"event": "ready", "node_id": node.node_id}, sort_keys=True), flush=True)
        server.serve_forever(poll_interval=0.05)
    return 0


def _send_control(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    sequence = time.time_ns() & ((1 << 63) - 1)
    request = sync.sign_envelope(CONTROL_ID, config["node_id"], sequence, payload, config["control_key_hex"])
    encoded = canonical_bytes(request) + b"\n"
    with socket.create_connection(
        (config["listen_host"], config["listen_port"]),
        timeout=SOCKET_TIMEOUT_SECONDS,
        source_address=(config["control_host"], 0),
    ) as connection:
        connection.settimeout(SOCKET_TIMEOUT_SECONDS)
        connection.sendall(encoded)
        reader = connection.makefile("rb")
        response, _ = _read_json_line(reader, sync.MAX_MESSAGE_BYTES)
    checked = sync.verify_envelope(
        response,
        expected_sender=config["node_id"],
        expected_recipient=CONTROL_ID,
        key_hex=config["control_key_hex"],
    )
    return checked["payload"]


def probe_peer(config: dict[str, Any], peer_id: str, nonce_hex: str) -> dict[str, Any]:
    peer = next((item for item in config["peers"] if item["node_id"] == peer_id), None)
    if peer is None:
        raise RoutedError("unknown_peer", "probe peer is absent from the pinned table")
    private = safety.ephemeral_private(bytes.fromhex(nonce_hex))
    hello = safety.make_hello(
        peer_id=config["node_id"],
        identity_seed_hex=config["identity_seed_hex"],
        operator_group=config["operator_group"],
        transport=config["transport"],
        endpoint=config["endpoint"],
        role="initiator",
        ephemeral_private_key=private,
        nonce_hex=nonce_hex,
        issued_tick=int(time.time()),
    )
    with socket.create_connection(
        (peer["host"], peer["port"]),
        timeout=SOCKET_TIMEOUT_SECONDS,
        source_address=(config["listen_host"], 0),
    ) as connection:
        connection.settimeout(SOCKET_TIMEOUT_SECONDS)
        writer = connection.makefile("wb")
        reader = connection.makefile("rb")
        _write_json_line(writer, hello, safety.MAX_HELLO_BYTES)
        response, _ = _read_json_line(reader, safety.MAX_HELLO_BYTES)
    safety.verify_hello(
        response,
        expected_peer_id=peer_id,
        expected_public_key_hex=peer["identity_public_key_hex"],
        expected_role="responder",
        expected_operator_group=peer["operator_group"],
        expected_transport=peer["transport"],
        expected_endpoint=peer["endpoint"],
        current_tick=int(time.time()),
    )
    return {"peer_id": peer_id, "accepted": True}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("serve", "status", "stop"):
        child = subparsers.add_parser(command)
        child.add_argument("--config", type=Path, required=True)
    importer = subparsers.add_parser("import")
    importer.add_argument("--config", type=Path, required=True)
    importer.add_argument("--shares", type=Path, required=True)
    synchronizer = subparsers.add_parser("sync")
    synchronizer.add_argument("--config", type=Path, required=True)
    synchronizer.add_argument("--peer", required=True)
    ticker = subparsers.add_parser("tick")
    ticker.add_argument("--config", type=Path, required=True)
    ticker.add_argument("--count", type=int, required=True)
    probe = subparsers.add_parser("probe")
    probe.add_argument("--config", type=Path, required=True)
    probe.add_argument("--peer", required=True)
    probe.add_argument("--nonce", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    config = load_config(args.config)
    if args.command == "serve":
        return serve(config)
    if args.command == "status":
        result = _send_control(config, {"op": "status"})
    elif args.command == "stop":
        result = _send_control(config, {"op": "stop"})
    elif args.command == "import":
        result = _send_control(
            config,
            {"op": "import", "shares": json.loads(args.shares.read_text(encoding="utf-8"))},
        )
    elif args.command == "sync":
        result = _send_control(config, {"op": "sync", "peer_id": args.peer})
    elif args.command == "tick":
        result = _send_control(config, {"op": "tick", "count": args.count})
    else:
        result = probe_peer(config, args.peer, args.nonce)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError, json.JSONDecodeError, UnicodeDecodeError, RoutedError,
        safety.SafetyError, sync.SyncError, reference.ProfileError, independent.Reject,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
