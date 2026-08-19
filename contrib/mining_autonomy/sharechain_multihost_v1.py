#!/usr/bin/env python3
"""Frozen multi-host safety primitives for the Soveroot share-sync laboratory.

This module is deliberately independent of block consensus.  It supplies a
small, testable identity/session profile, deterministic admission accounting,
peer-diversity selection, and bounded catch-up planning.  The cryptographic
implementation is a readable laboratory reference, not a production library.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
from dataclasses import dataclass
from typing import Any, Iterable


PROTOCOL = "soveroot-share-sync-multihost-lab-v1"
NETWORK_ID = "soveroot-labnet-v1"
IDENTITY_ALGORITHM = "ed25519-rfc8032-sha512-lab-reference"
EPHEMERAL_ALGORITHM = "x25519-rfc7748-lab-reference"
SESSION_KDF = "hkdf-sha256"
HELLO_DOMAIN = b"soveroot/share-sync/multihost/hello/v1\x00"
SESSION_DOMAIN = b"soveroot/share-sync/multihost/session/v1\x00"
ANNOUNCEMENT_DOMAIN = b"soveroot/share-sync/multihost/announcement/v1\x00"

MAX_HELLO_BYTES = 32_768
MAX_FRAME_BYTES = 131_072
HELLO_LIFETIME_TICKS = 16
SESSION_LIFETIME_TICKS = 128
MAX_ACTIVE_SESSIONS = 16
MAX_SESSIONS_PER_IDENTITY = 2
MAX_SESSIONS_PER_SOURCE_PREFIX = 4
HANDSHAKE_BUCKET_CAPACITY = 8
HANDSHAKE_REFILL_PER_TICK = 1
MESSAGE_BUCKET_CAPACITY = 64
MESSAGE_REFILL_PER_TICK = 4
MAX_REPLAY_NONCES = 256
MAX_QUARANTINES = 128
MAX_ADMISSION_BUCKETS = 512
MAX_PEER_CANDIDATES = 128
QUARANTINE_TICKS = 32
MAX_CATCHUP_SHARES = 1_024
MAX_CATCHUP_PAGES = 16
MAX_CATCHUP_OPERATIONS = 64
CATCHUP_SHARES_PER_PAGE = 64
MIN_DIVERSE_PEERS = 3
MIN_DISTINCT_PREFIXES = 3
MIN_DISTINCT_OPERATOR_GROUPS = 3
MIN_DISTINCT_TRANSPORTS = 2
MAX_PEERS_PER_PREFIX = 1
MAX_PEERS_PER_OPERATOR_GROUP = 1
MAX_PEERS_PER_TRANSPORT = 2

LIMITS = {
    "max_hello_bytes": MAX_HELLO_BYTES,
    "max_frame_bytes": MAX_FRAME_BYTES,
    "hello_lifetime_ticks": HELLO_LIFETIME_TICKS,
    "session_lifetime_ticks": SESSION_LIFETIME_TICKS,
    "max_active_sessions": MAX_ACTIVE_SESSIONS,
    "max_sessions_per_identity": MAX_SESSIONS_PER_IDENTITY,
    "max_sessions_per_source_prefix": MAX_SESSIONS_PER_SOURCE_PREFIX,
    "handshake_bucket_capacity": HANDSHAKE_BUCKET_CAPACITY,
    "handshake_refill_per_tick": HANDSHAKE_REFILL_PER_TICK,
    "message_bucket_capacity": MESSAGE_BUCKET_CAPACITY,
    "message_refill_per_tick": MESSAGE_REFILL_PER_TICK,
    "max_replay_nonces": MAX_REPLAY_NONCES,
    "max_quarantines": MAX_QUARANTINES,
    "max_admission_buckets": MAX_ADMISSION_BUCKETS,
    "max_peer_candidates": MAX_PEER_CANDIDATES,
    "quarantine_ticks": QUARANTINE_TICKS,
    "max_catchup_shares": MAX_CATCHUP_SHARES,
    "max_catchup_pages": MAX_CATCHUP_PAGES,
    "max_catchup_operations": MAX_CATCHUP_OPERATIONS,
    "catchup_shares_per_page": CATCHUP_SHARES_PER_PAGE,
    "min_diverse_peers": MIN_DIVERSE_PEERS,
    "min_distinct_prefixes": MIN_DISTINCT_PREFIXES,
    "min_distinct_operator_groups": MIN_DISTINCT_OPERATOR_GROUPS,
    "min_distinct_transports": MIN_DISTINCT_TRANSPORTS,
    "max_peers_per_prefix": MAX_PEERS_PER_PREFIX,
    "max_peers_per_operator_group": MAX_PEERS_PER_OPERATOR_GROUP,
    "max_peers_per_transport": MAX_PEERS_PER_TRANSPORT,
}


class SafetyError(RuntimeError):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


def canonical_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=True).encode("ascii")
    except (TypeError, UnicodeEncodeError) as error:
        raise SafetyError("canonical_encoding", "value is not canonical ASCII JSON") from error
    return encoded


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require_hex(value: Any, size: int, reason: str, label: str) -> str:
    if not isinstance(value, str) or len(value) != size * 2 or value != value.lower():
        raise SafetyError(reason, f"{label} must be canonical lowercase {size}-byte hex")
    try:
        bytes.fromhex(value)
    except ValueError as error:
        raise SafetyError(reason, f"{label} must be hexadecimal") from error
    return value


def _require_text(value: Any, reason: str, label: str, limit: int = 64) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or not value.isascii():
        raise SafetyError(reason, f"{label} must be 1-{limit} ASCII characters")
    return value


# Minimal RFC 8032 Ed25519 reference.  It is kept here so the laboratory has no
# optional package or platform dependency.  Production use requires a reviewed,
# constant-time library and a separately reviewed post-quantum hybrid profile.
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = x * _I % _Q
    if x & 1:
        x = _Q - x
    return x


_BY = 4 * pow(5, _Q - 2, _Q) % _Q
_BX = _xrecover(_BY)
_B = (_BX, _BY)


def _ed_add(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    common = _D * x1 * x2 * y1 * y2 % _Q
    x3 = (x1 * y2 + x2 * y1) * pow(1 + common, _Q - 2, _Q) % _Q
    y3 = (y1 * y2 + x1 * x2) * pow(1 - common, _Q - 2, _Q) % _Q
    return x3, y3


def _ed_scalar(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    addend = point
    while scalar:
        if scalar & 1:
            result = _ed_add(result, addend)
        addend = _ed_add(addend, addend)
        scalar >>= 1
    return result


def _encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decode_point(encoded: bytes) -> tuple[int, int]:
    if len(encoded) != 32:
        raise SafetyError("identity_point", "Ed25519 point must be 32 bytes")
    value = int.from_bytes(encoded, "little")
    y = value & ((1 << 255) - 1)
    if y >= _Q:
        raise SafetyError("identity_point", "Ed25519 point is non-canonical")
    x = _xrecover(y)
    if (x & 1) != (value >> 255):
        x = _Q - x
    point = (x, y)
    if (y * y - x * x - 1 - _D * x * x * y * y) % _Q != 0:
        raise SafetyError("identity_point", "Ed25519 point is not on the curve")
    return point


def _secret_scalar(seed: bytes) -> tuple[int, bytes]:
    if len(seed) != 32:
        raise SafetyError("identity_seed", "identity seed must be exactly 32 bytes")
    digest = hashlib.sha512(seed).digest()
    scalar_bytes = bytearray(digest[:32])
    scalar_bytes[0] &= 248
    scalar_bytes[31] &= 63
    scalar_bytes[31] |= 64
    return int.from_bytes(scalar_bytes, "little"), digest[32:]


def identity_public_key(seed_hex: str) -> str:
    seed = bytes.fromhex(require_hex(seed_hex, 32, "identity_seed", "identity seed"))
    scalar, _ = _secret_scalar(seed)
    return _encode_point(_ed_scalar(_B, scalar)).hex()


def identity_sign(seed_hex: str, message: bytes) -> str:
    seed = bytes.fromhex(require_hex(seed_hex, 32, "identity_seed", "identity seed"))
    scalar, prefix = _secret_scalar(seed)
    public = bytes.fromhex(identity_public_key(seed_hex))
    nonce = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % _L
    encoded_r = _encode_point(_ed_scalar(_B, nonce))
    challenge = int.from_bytes(hashlib.sha512(encoded_r + public + message).digest(), "little") % _L
    encoded_s = int.to_bytes((nonce + challenge * scalar) % _L, 32, "little")
    return (encoded_r + encoded_s).hex()


def identity_verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    try:
        public = bytes.fromhex(require_hex(public_key_hex, 32, "identity_key", "identity public key"))
        signature = bytes.fromhex(require_hex(signature_hex, 64, "identity_signature", "identity signature"))
        point_a = _decode_point(public)
        if point_a == (0, 1) or _ed_scalar(point_a, _L) != (0, 1):
            return False
        point_r = _decode_point(signature[:32])
        scalar_s = int.from_bytes(signature[32:], "little")
        if scalar_s >= _L:
            return False
        challenge = int.from_bytes(hashlib.sha512(signature[:32] + public + message).digest(), "little") % _L
        return hmac.compare_digest(
            _encode_point(_ed_scalar(_B, scalar_s)),
            _encode_point(_ed_add(point_r, _ed_scalar(point_a, challenge))),
        )
    except (ValueError, SafetyError):
        return False


# Minimal RFC 7748 X25519 reference.  As above, this is for deterministic lab
# evidence rather than a constant-time production endpoint.
def x25519(private_key: bytes, peer_public: bytes = b"\x09" + b"\x00" * 31) -> bytes:
    if len(private_key) != 32 or len(peer_public) != 32:
        raise SafetyError("ephemeral_key", "X25519 keys must be exactly 32 bytes")
    scalar_bytes = bytearray(private_key)
    scalar_bytes[0] &= 248
    scalar_bytes[31] &= 127
    scalar_bytes[31] |= 64
    scalar = int.from_bytes(scalar_bytes, "little")
    u = int.from_bytes(peer_public, "little") & ((1 << 255) - 1)
    x_2, z_2, x_3, z_3, swap = 1, 0, u, 1, 0
    for bit_index in range(254, -1, -1):
        bit = (scalar >> bit_index) & 1
        swap ^= bit
        if swap:
            x_2, x_3 = x_3, x_2
            z_2, z_3 = z_3, z_2
        swap = bit
        a = (x_2 + z_2) % _Q
        aa = a * a % _Q
        b = (x_2 - z_2) % _Q
        bb = b * b % _Q
        e = (aa - bb) % _Q
        c = (x_3 + z_3) % _Q
        d = (x_3 - z_3) % _Q
        da = d * a % _Q
        cb = c * b % _Q
        x_3 = (da + cb) ** 2 % _Q
        z_3 = u * (da - cb) ** 2 % _Q
        x_2 = aa * bb % _Q
        z_2 = e * (aa + 121665 * e) % _Q
    if swap:
        x_2, x_3 = x_3, x_2
        z_2, z_3 = z_3, z_2
    return int.to_bytes(x_2 * pow(z_2, _Q - 2, _Q) % _Q, 32, "little")


def ephemeral_private(seed: bytes) -> bytes:
    return hashlib.sha256(b"soveroot/share-sync/ephemeral/v1\x00" + seed).digest()


def ephemeral_public(private_key: bytes) -> str:
    return x25519(private_key).hex()


def _hkdf(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    pseudorandom_key = hmac.new(salt, ikm, hashlib.sha256).digest()
    output = b""
    previous = b""
    counter = 1
    while len(output) < length:
        previous = hmac.new(pseudorandom_key, previous + info + bytes([counter]), hashlib.sha256).digest()
        output += previous
        counter += 1
    return output[:length]


_HELLO_FIELDS = {
    "format",
    "message_type",
    "network_id",
    "role",
    "peer_id",
    "identity_algorithm",
    "identity_public_key_hex",
    "operator_group",
    "transport",
    "endpoint",
    "ephemeral_algorithm",
    "ephemeral_public_key_hex",
    "nonce_hex",
    "issued_tick",
    "expires_tick",
}


def make_hello(
    *,
    peer_id: str,
    identity_seed_hex: str,
    operator_group: str,
    transport: str,
    endpoint: str,
    role: str,
    ephemeral_private_key: bytes,
    nonce_hex: str,
    issued_tick: int,
    network_id: str = NETWORK_ID,
) -> dict[str, Any]:
    if role not in {"initiator", "responder"}:
        raise SafetyError("hello_role", "hello role is invalid")
    _require_text(peer_id, "hello_peer", "peer id", 32)
    _require_text(operator_group, "hello_operator", "operator group", 64)
    _require_text(transport, "hello_transport", "transport", 32)
    _require_text(endpoint, "hello_endpoint", "endpoint", 128)
    _require_text(network_id, "hello_network", "network id", 64)
    require_hex(nonce_hex, 32, "hello_nonce", "hello nonce")
    if not isinstance(issued_tick, int) or isinstance(issued_tick, bool) or issued_tick < 0:
        raise SafetyError("hello_tick", "issued tick is invalid")
    body = {
        "format": PROTOCOL,
        "message_type": "session_hello",
        "network_id": network_id,
        "role": role,
        "peer_id": peer_id,
        "identity_algorithm": IDENTITY_ALGORITHM,
        "identity_public_key_hex": identity_public_key(identity_seed_hex),
        "operator_group": operator_group,
        "transport": transport,
        "endpoint": endpoint,
        "ephemeral_algorithm": EPHEMERAL_ALGORITHM,
        "ephemeral_public_key_hex": ephemeral_public(ephemeral_private_key),
        "nonce_hex": nonce_hex,
        "issued_tick": issued_tick,
        "expires_tick": issued_tick + HELLO_LIFETIME_TICKS,
    }
    signature = identity_sign(identity_seed_hex, HELLO_DOMAIN + canonical_bytes(body))
    hello = {**body, "signature_hex": signature}
    if len(canonical_bytes(hello)) > MAX_HELLO_BYTES:
        raise SafetyError("hello_size", "hello exceeds its frozen byte limit")
    return hello


def verify_hello(
    hello: Any,
    *,
    expected_peer_id: str,
    expected_public_key_hex: str,
    expected_role: str,
    expected_operator_group: str,
    expected_transport: str,
    expected_endpoint: str,
    current_tick: int,
    expected_network_id: str = NETWORK_ID,
) -> dict[str, Any]:
    if not isinstance(hello, dict) or set(hello) != _HELLO_FIELDS | {"signature_hex"}:
        raise SafetyError("hello_fields", "hello fields are not canonical")
    if len(canonical_bytes(hello)) > MAX_HELLO_BYTES:
        raise SafetyError("hello_size", "hello exceeds its frozen byte limit")
    if hello["format"] != PROTOCOL or hello["message_type"] != "session_hello":
        raise SafetyError("hello_profile", "hello uses the wrong profile")
    if hello["network_id"] != expected_network_id:
        raise SafetyError("wrong_network", "hello is bound to a different network")
    if hello["role"] != expected_role:
        raise SafetyError("hello_role", "hello uses the wrong session role")
    if hello["peer_id"] != expected_peer_id:
        raise SafetyError("wrong_identity", "hello peer id is not pinned")
    if hello["identity_algorithm"] != IDENTITY_ALGORITHM or hello["ephemeral_algorithm"] != EPHEMERAL_ALGORITHM:
        raise SafetyError("algorithm_downgrade", "hello changes a frozen algorithm identifier")
    require_hex(expected_public_key_hex, 32, "identity_key", "pinned identity public key")
    if hello["identity_public_key_hex"] != expected_public_key_hex:
        raise SafetyError("wrong_identity", "hello identity key is not pinned")
    _require_text(hello["operator_group"], "hello_operator", "operator group", 64)
    _require_text(hello["transport"], "hello_transport", "transport", 32)
    _require_text(hello["endpoint"], "hello_endpoint", "endpoint", 128)
    require_hex(hello["ephemeral_public_key_hex"], 32, "ephemeral_key", "ephemeral public key")
    require_hex(hello["nonce_hex"], 32, "hello_nonce", "hello nonce")
    if (
        not isinstance(current_tick, int)
        or isinstance(current_tick, bool)
        or not isinstance(hello["issued_tick"], int)
        or isinstance(hello["issued_tick"], bool)
        or not isinstance(hello["expires_tick"], int)
        or isinstance(hello["expires_tick"], bool)
        or hello["expires_tick"] != hello["issued_tick"] + HELLO_LIFETIME_TICKS
        or not hello["issued_tick"] <= current_tick <= hello["expires_tick"]
    ):
        raise SafetyError("expired_hello", "hello is outside its frozen lifetime")
    signature = hello["signature_hex"]
    require_hex(signature, 64, "identity_signature", "identity signature")
    body = {key: hello[key] for key in _HELLO_FIELDS}
    if not identity_verify(expected_public_key_hex, HELLO_DOMAIN + canonical_bytes(body), signature):
        raise SafetyError("identity_signature", "hello identity signature is invalid")
    if (
        hello["operator_group"] != expected_operator_group
        or hello["transport"] != expected_transport
        or hello["endpoint"] != expected_endpoint
    ):
        raise SafetyError("peer_metadata", "signed peer metadata does not match the pinned configuration")
    return hello


def derive_session_key(
    *,
    local_ephemeral_private: bytes,
    initiator_hello: dict[str, Any],
    responder_hello: dict[str, Any],
) -> tuple[str, str]:
    if initiator_hello.get("role") != "initiator" or responder_hello.get("role") != "responder":
        raise SafetyError("hello_role", "session transcript roles are not canonical")
    if initiator_hello.get("network_id") != responder_hello.get("network_id"):
        raise SafetyError("wrong_network", "session hellos bind different networks")
    local_public = ephemeral_public(local_ephemeral_private)
    if local_public == initiator_hello.get("ephemeral_public_key_hex"):
        remote_public = responder_hello["ephemeral_public_key_hex"]
    elif local_public == responder_hello.get("ephemeral_public_key_hex"):
        remote_public = initiator_hello["ephemeral_public_key_hex"]
    else:
        raise SafetyError("ephemeral_key", "local ephemeral key is absent from the transcript")
    shared = x25519(local_ephemeral_private, bytes.fromhex(remote_public))
    if shared == b"\x00" * 32:
        raise SafetyError("ephemeral_key", "X25519 produced the forbidden all-zero secret")
    transcript = {
        "format": PROTOCOL,
        "initiator_hello": initiator_hello,
        "responder_hello": responder_hello,
    }
    transcript_hash = hashlib.sha256(canonical_bytes(transcript)).digest()
    info = SESSION_DOMAIN + canonical_bytes(
        {
            "network_id": initiator_hello["network_id"],
            "initiator_id": initiator_hello["peer_id"],
            "responder_id": responder_hello["peer_id"],
            "kdf": SESSION_KDF,
        }
    )
    key = _hkdf(shared, transcript_hash, info)
    return key.hex(), transcript_hash.hex()


def session_envelope(
    *,
    session_key_hex: str,
    transcript_sha256: str,
    sender_id: str,
    recipient_id: str,
    sequence: int,
    issued_tick: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    key = bytes.fromhex(require_hex(session_key_hex, 32, "session_key", "session key"))
    require_hex(transcript_sha256, 32, "session_transcript", "session transcript")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or not 0 < sequence < 1 << 63:
        raise SafetyError("session_sequence", "session sequence is invalid")
    if not isinstance(issued_tick, int) or isinstance(issued_tick, bool) or issued_tick < 0:
        raise SafetyError("session_tick", "session tick is invalid")
    body = {
        "format": PROTOCOL,
        "message_type": "session_frame",
        "transcript_sha256": transcript_sha256,
        "sender_id": sender_id,
        "recipient_id": recipient_id,
        "sequence": sequence,
        "issued_tick": issued_tick,
        "payload": payload,
    }
    mac = hmac.new(key, SESSION_DOMAIN + canonical_bytes(body), hashlib.sha256).hexdigest()
    envelope = {**body, "mac_sha256": mac}
    if len(canonical_bytes(envelope)) > MAX_FRAME_BYTES:
        raise SafetyError("frame_size", "session frame exceeds its frozen byte limit")
    return envelope


def verify_session_envelope(
    envelope: Any,
    *,
    session_key_hex: str,
    transcript_sha256: str,
    expected_sender: str,
    expected_recipient: str,
    prior_sequence: int,
    session_start_tick: int,
    current_tick: int,
) -> dict[str, Any]:
    fields = {
        "format", "message_type", "transcript_sha256", "sender_id", "recipient_id",
        "sequence", "issued_tick", "payload", "mac_sha256",
    }
    if not isinstance(envelope, dict) or set(envelope) != fields:
        raise SafetyError("frame_fields", "session frame fields are not canonical")
    if len(canonical_bytes(envelope)) > MAX_FRAME_BYTES:
        raise SafetyError("frame_size", "session frame exceeds its frozen byte limit")
    if envelope["format"] != PROTOCOL or envelope["message_type"] != "session_frame":
        raise SafetyError("frame_profile", "session frame uses the wrong profile")
    if envelope["transcript_sha256"] != transcript_sha256:
        raise SafetyError("altered_transcript", "session frame binds another transcript")
    if envelope["sender_id"] != expected_sender or envelope["recipient_id"] != expected_recipient:
        raise SafetyError("frame_route", "session frame route is not pinned")
    if not isinstance(envelope["payload"], dict):
        raise SafetyError("frame_payload", "session frame payload must be an object")
    if (
        not isinstance(envelope["sequence"], int)
        or isinstance(envelope["sequence"], bool)
        or not 0 < envelope["sequence"] < 1 << 63
    ):
        raise SafetyError("session_sequence", "session sequence is invalid")
    if envelope["sequence"] <= prior_sequence:
        raise SafetyError("frame_replay", "session sequence is not newer than retained state")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (envelope["issued_tick"], session_start_tick, current_tick)
    ):
        raise SafetyError("session_tick", "session tick is invalid")
    if not session_start_tick <= envelope["issued_tick"] <= current_tick <= session_start_tick + SESSION_LIFETIME_TICKS:
        raise SafetyError("expired_session", "session frame is outside the frozen session lifetime")
    require_hex(envelope["mac_sha256"], 32, "frame_authentication", "session frame MAC")
    expected = session_envelope(
        session_key_hex=session_key_hex,
        transcript_sha256=transcript_sha256,
        sender_id=expected_sender,
        recipient_id=expected_recipient,
        sequence=envelope["sequence"],
        issued_tick=envelope["issued_tick"],
        payload=envelope["payload"],
    )["mac_sha256"]
    if not hmac.compare_digest(expected, envelope["mac_sha256"]):
        raise SafetyError("frame_authentication", "session frame MAC is invalid")
    return envelope


def signed_announcement(
    *,
    identity_seed_hex: str,
    peer_id: str,
    slot: int,
    selected_tip_share_id: str,
    state_commitment_sha256: str,
) -> dict[str, Any]:
    require_hex(selected_tip_share_id, 32, "announcement_commitment", "selected tip")
    require_hex(state_commitment_sha256, 32, "announcement_commitment", "state commitment")
    if not isinstance(slot, int) or isinstance(slot, bool) or slot < 0:
        raise SafetyError("announcement_slot", "announcement slot is invalid")
    body = {
        "format": PROTOCOL,
        "message_type": "signed_announcement",
        "peer_id": peer_id,
        "identity_algorithm": IDENTITY_ALGORITHM,
        "identity_public_key_hex": identity_public_key(identity_seed_hex),
        "slot": slot,
        "selected_tip_share_id": selected_tip_share_id,
        "state_commitment_sha256": state_commitment_sha256,
    }
    return {**body, "signature_hex": identity_sign(identity_seed_hex, ANNOUNCEMENT_DOMAIN + canonical_bytes(body))}


def verify_announcement(
    value: Any, expected_public_key_hex: str, expected_peer_id: str
) -> dict[str, Any]:
    fields = {
        "format", "message_type", "peer_id", "identity_algorithm", "identity_public_key_hex",
        "slot", "selected_tip_share_id", "state_commitment_sha256", "signature_hex",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise SafetyError("announcement_fields", "signed announcement fields are not canonical")
    if value["format"] != PROTOCOL or value["message_type"] != "signed_announcement":
        raise SafetyError("announcement_profile", "announcement uses the wrong profile")
    if value["identity_algorithm"] != IDENTITY_ALGORITHM or value["identity_public_key_hex"] != expected_public_key_hex:
        raise SafetyError("wrong_identity", "announcement identity is not pinned")
    if value["peer_id"] != expected_peer_id:
        raise SafetyError("wrong_identity", "announcement peer id is not pinned")
    require_hex(value["selected_tip_share_id"], 32, "announcement_commitment", "selected tip")
    require_hex(value["state_commitment_sha256"], 32, "announcement_commitment", "state commitment")
    if not isinstance(value["slot"], int) or isinstance(value["slot"], bool) or value["slot"] < 0:
        raise SafetyError("announcement_slot", "announcement slot is invalid")
    body = {key: value[key] for key in fields if key != "signature_hex"}
    if not identity_verify(expected_public_key_hex, ANNOUNCEMENT_DOMAIN + canonical_bytes(body), value["signature_hex"]):
        raise SafetyError("identity_signature", "announcement signature is invalid")
    return value


def equivocation_evidence(
    first: dict[str, Any], second: dict[str, Any], public_key_hex: str, expected_peer_id: str
) -> dict[str, Any]:
    verify_announcement(first, public_key_hex, expected_peer_id)
    verify_announcement(second, public_key_hex, expected_peer_id)
    if first["peer_id"] != second["peer_id"] or first["slot"] != second["slot"]:
        raise SafetyError("not_equivocation", "announcements do not share an identity and slot")
    if first["selected_tip_share_id"] == second["selected_tip_share_id"] and first["state_commitment_sha256"] == second["state_commitment_sha256"]:
        raise SafetyError("not_equivocation", "announcements do not conflict")
    evidence = {"format": PROTOCOL, "type": "portable_equivocation_evidence", "first": first, "second": second}
    return {**evidence, "evidence_commitment_sha256": canonical_hash(evidence)}


def source_prefix(address: str) -> str:
    if not isinstance(address, str) or "%" in address:
        raise SafetyError("source_address", "source address must be an unscoped IP literal")
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as error:
        raise SafetyError("source_address", "source address is invalid") from error
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        parsed = parsed.ipv4_mapped
    length = 24 if parsed.version == 4 else 48
    return str(ipaddress.ip_network(f"{parsed}/{length}", strict=False))


@dataclass
class _Bucket:
    tokens: int
    tick: int


class AdmissionController:
    """Deterministic, persistable local admission state; never consensus state."""

    def __init__(self, snapshot: dict[str, Any] | None = None) -> None:
        self.tick = 0
        self.handshake_buckets: dict[str, _Bucket] = {}
        self.message_buckets: dict[str, _Bucket] = {}
        self.replay_nonces: dict[str, int] = {}
        self.quarantines: dict[str, int] = {}
        self.active_identity: dict[str, int] = {}
        self.active_prefix: dict[str, int] = {}
        self.rejections: dict[str, int] = {}
        if snapshot is not None:
            self._restore(snapshot)

    def _reject(self, reason: str, detail: str) -> None:
        self.rejections[reason] = self.rejections.get(reason, 0) + 1
        raise SafetyError(reason, detail)

    @staticmethod
    def _consume(
        table: dict[str, _Bucket], key: str, tick: int, capacity: int, refill: int, cost: int
    ) -> bool | None:
        if key not in table and len(table) >= MAX_ADMISSION_BUCKETS:
            return None
        bucket = table.get(key, _Bucket(capacity, tick))
        bucket.tokens = min(capacity, bucket.tokens + max(0, tick - bucket.tick) * refill)
        bucket.tick = tick
        table[key] = bucket
        if cost > bucket.tokens:
            return False
        bucket.tokens -= cost
        return True

    def _advance(self, tick: int) -> None:
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < self.tick:
            self._reject("admission_tick", "admission tick cannot move backward")
        self.tick = tick
        self.replay_nonces = {key: expiry for key, expiry in self.replay_nonces.items() if expiry >= tick}
        self.quarantines = {key: expiry for key, expiry in self.quarantines.items() if expiry >= tick}
        self.handshake_buckets = {
            key: bucket
            for key, bucket in self.handshake_buckets.items()
            if bucket.tokens + max(0, tick - bucket.tick) * HANDSHAKE_REFILL_PER_TICK
            < HANDSHAKE_BUCKET_CAPACITY
        }
        self.message_buckets = {
            key: bucket
            for key, bucket in self.message_buckets.items()
            if bucket.tokens + max(0, tick - bucket.tick) * MESSAGE_REFILL_PER_TICK
            < MESSAGE_BUCKET_CAPACITY
        }

    def admit_handshake(self, *, peer_id: str, source_ip: str, nonce_hex: str, tick: int) -> str:
        self._advance(tick)
        _require_text(peer_id, "admission_identity", "peer id", 32)
        require_hex(nonce_hex, 32, "hello_nonce", "hello nonce")
        prefix = source_prefix(source_ip)
        if self.quarantines.get(peer_id, -1) >= tick:
            self._reject("quarantined_identity", "identity is locally quarantined")
        if nonce_hex in self.replay_nonces:
            self._reject("replayed_handshake", "handshake nonce was already admitted")
        if len(self.replay_nonces) >= MAX_REPLAY_NONCES:
            self._reject("replay_state_limit", "replay state reached its frozen limit")
        identity_result = self._consume(
            self.handshake_buckets,
            f"identity:{peer_id}",
            tick,
            HANDSHAKE_BUCKET_CAPACITY,
            HANDSHAKE_REFILL_PER_TICK,
            1,
        )
        if identity_result is None:
            self._reject("admission_bucket_limit", "handshake bucket state reached its frozen limit")
        if not identity_result:
            self._reject("identity_handshake_rate", "identity handshake bucket is empty")
        prefix_result = self._consume(
            self.handshake_buckets,
            f"prefix:{prefix}",
            tick,
            HANDSHAKE_BUCKET_CAPACITY,
            HANDSHAKE_REFILL_PER_TICK,
            1,
        )
        if prefix_result is None:
            self._reject("admission_bucket_limit", "handshake bucket state reached its frozen limit")
        if not prefix_result:
            self._reject("prefix_handshake_rate", "source-prefix handshake bucket is empty")
        if sum(self.active_identity.values()) >= MAX_ACTIVE_SESSIONS:
            self._reject("active_session_limit", "active-session limit is full")
        if self.active_identity.get(peer_id, 0) >= MAX_SESSIONS_PER_IDENTITY:
            self._reject("identity_session_limit", "identity session limit is full")
        if self.active_prefix.get(prefix, 0) >= MAX_SESSIONS_PER_SOURCE_PREFIX:
            self._reject("prefix_session_limit", "source-prefix session limit is full")
        self.replay_nonces[nonce_hex] = tick + HELLO_LIFETIME_TICKS
        self.active_identity[peer_id] = self.active_identity.get(peer_id, 0) + 1
        self.active_prefix[prefix] = self.active_prefix.get(prefix, 0) + 1
        return prefix

    def close_session(self, *, peer_id: str, source_ip: str) -> None:
        prefix = source_prefix(source_ip)
        if self.active_identity.get(peer_id, 0) > 0:
            self.active_identity[peer_id] -= 1
            if self.active_identity[peer_id] == 0:
                del self.active_identity[peer_id]
        if self.active_prefix.get(prefix, 0) > 0:
            self.active_prefix[prefix] -= 1
            if self.active_prefix[prefix] == 0:
                del self.active_prefix[prefix]

    def admit_message(self, *, peer_id: str, frame_bytes: int, tick: int) -> int:
        self._advance(tick)
        if not isinstance(frame_bytes, int) or frame_bytes < 1 or frame_bytes > MAX_FRAME_BYTES:
            self._reject("frame_size", "frame length is outside the frozen bound")
        cost = 1 + (frame_bytes - 1) // 4_096
        result = self._consume(
            self.message_buckets,
            peer_id,
            tick,
            MESSAGE_BUCKET_CAPACITY,
            MESSAGE_REFILL_PER_TICK,
            cost,
        )
        if result is None:
            self._reject("admission_bucket_limit", "message bucket state reached its frozen limit")
        if not result:
            self._reject("message_rate", "identity message bucket is empty")
        return cost

    def quarantine(self, peer_id: str, tick: int) -> None:
        self._advance(tick)
        if peer_id not in self.quarantines and len(self.quarantines) >= MAX_QUARANTINES:
            self._reject("quarantine_limit", "quarantine state reached its frozen limit")
        self.quarantines[peer_id] = tick + QUARANTINE_TICKS

    def snapshot(self) -> dict[str, Any]:
        return {
            "format": PROTOCOL,
            "tick": self.tick,
            "handshake_buckets": {key: {"tokens": value.tokens, "tick": value.tick} for key, value in sorted(self.handshake_buckets.items())},
            "message_buckets": {key: {"tokens": value.tokens, "tick": value.tick} for key, value in sorted(self.message_buckets.items())},
            "replay_nonces": dict(sorted(self.replay_nonces.items())),
            "quarantines": dict(sorted(self.quarantines.items())),
            "active_identity": dict(sorted(self.active_identity.items())),
            "active_prefix": dict(sorted(self.active_prefix.items())),
            "rejections": dict(sorted(self.rejections.items())),
        }

    def _restore(self, snapshot: dict[str, Any]) -> None:
        expected = {"format", "tick", "handshake_buckets", "message_buckets", "replay_nonces", "quarantines", "active_identity", "active_prefix", "rejections"}
        if not isinstance(snapshot, dict) or set(snapshot) != expected or snapshot["format"] != PROTOCOL:
            raise SafetyError("admission_state", "admission snapshot fields are invalid")
        if not isinstance(snapshot["tick"], int) or snapshot["tick"] < 0:
            raise SafetyError("admission_state", "admission snapshot tick is invalid")
        self.tick = snapshot["tick"]
        for name, target, capacity in (
            ("handshake_buckets", self.handshake_buckets, HANDSHAKE_BUCKET_CAPACITY),
            ("message_buckets", self.message_buckets, MESSAGE_BUCKET_CAPACITY),
        ):
            rows = snapshot[name]
            if not isinstance(rows, dict) or len(rows) > MAX_ADMISSION_BUCKETS:
                raise SafetyError("admission_state", "bucket snapshot is invalid")
            for key, row in rows.items():
                if not isinstance(key, str) or not isinstance(row, dict) or set(row) != {"tokens", "tick"}:
                    raise SafetyError("admission_state", "bucket row is invalid")
                if not isinstance(row["tokens"], int) or not 0 <= row["tokens"] <= capacity or not isinstance(row["tick"], int) or not 0 <= row["tick"] <= self.tick:
                    raise SafetyError("admission_state", "bucket values are invalid")
                target[key] = _Bucket(row["tokens"], row["tick"])
        for name, target, limit in (
            ("replay_nonces", self.replay_nonces, MAX_REPLAY_NONCES),
            ("quarantines", self.quarantines, MAX_QUARANTINES),
            ("active_identity", self.active_identity, MAX_ACTIVE_SESSIONS),
            ("active_prefix", self.active_prefix, MAX_ACTIVE_SESSIONS),
            ("rejections", self.rejections, 64),
        ):
            rows = snapshot[name]
            if not isinstance(rows, dict) or len(rows) > limit or any(not isinstance(k, str) or not isinstance(v, int) or v < 0 for k, v in rows.items()):
                raise SafetyError("admission_state", f"{name} snapshot is invalid")
            target.update(rows)
        if sum(self.active_identity.values()) > MAX_ACTIVE_SESSIONS or sum(self.active_prefix.values()) > MAX_ACTIVE_SESSIONS:
            raise SafetyError("admission_state", "active-session snapshot exceeds its global limit")
        if any(value > MAX_SESSIONS_PER_IDENTITY for value in self.active_identity.values()):
            raise SafetyError("admission_state", "identity session snapshot exceeds its limit")
        if any(value > MAX_SESSIONS_PER_SOURCE_PREFIX for value in self.active_prefix.values()):
            raise SafetyError("admission_state", "source-prefix session snapshot exceeds its limit")


def select_diverse_peers(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    seen_ids = set()
    for candidate in candidates:
        if len(normalized) >= MAX_PEER_CANDIDATES:
            raise SafetyError("peer_candidate_limit", "peer candidate set exceeds its frozen limit")
        fields = {"peer_id", "address", "operator_group", "transport", "priority"}
        if not isinstance(candidate, dict) or set(candidate) != fields:
            raise SafetyError("peer_candidate", "peer candidate fields are not canonical")
        peer_id = _require_text(candidate["peer_id"], "peer_candidate", "peer id", 32)
        if peer_id in seen_ids:
            raise SafetyError("peer_candidate", "peer candidate id is repeated")
        seen_ids.add(peer_id)
        _require_text(candidate["operator_group"], "peer_candidate", "operator group", 64)
        _require_text(candidate["transport"], "peer_candidate", "transport", 32)
        if not isinstance(candidate["priority"], int) or isinstance(candidate["priority"], bool) or candidate["priority"] < 0:
            raise SafetyError("peer_candidate", "peer priority is invalid")
        normalized.append({**candidate, "prefix": source_prefix(candidate["address"])})
    selected: list[dict[str, Any]] = []
    prefixes: dict[str, int] = {}
    operators: dict[str, int] = {}
    transports: dict[str, int] = {}
    for candidate in sorted(normalized, key=lambda item: (item["priority"], item["peer_id"])):
        if prefixes.get(candidate["prefix"], 0) >= MAX_PEERS_PER_PREFIX:
            continue
        if operators.get(candidate["operator_group"], 0) >= MAX_PEERS_PER_OPERATOR_GROUP:
            continue
        if transports.get(candidate["transport"], 0) >= MAX_PEERS_PER_TRANSPORT:
            continue
        selected.append(candidate)
        prefixes[candidate["prefix"]] = prefixes.get(candidate["prefix"], 0) + 1
        operators[candidate["operator_group"]] = operators.get(candidate["operator_group"], 0) + 1
        transports[candidate["transport"]] = transports.get(candidate["transport"], 0) + 1
    if (
        len(selected) < MIN_DIVERSE_PEERS
        or len(prefixes) < MIN_DISTINCT_PREFIXES
        or len(operators) < MIN_DISTINCT_OPERATOR_GROUPS
        or len(transports) < MIN_DISTINCT_TRANSPORTS
    ):
        raise SafetyError("insufficient_peer_diversity", "candidate set cannot satisfy the frozen diversity floor")
    return selected


def catchup_plan(local_share_count: int, remote_share_count: int) -> dict[str, int]:
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in (local_share_count, remote_share_count)):
        raise SafetyError("catchup_height", "share counts must be non-negative integers")
    gap = max(0, remote_share_count - local_share_count)
    if gap > MAX_CATCHUP_SHARES:
        raise SafetyError("catchup_share_limit", "long-partition gap exceeds the frozen share budget")
    pages = (gap + CATCHUP_SHARES_PER_PAGE - 1) // CATCHUP_SHARES_PER_PAGE
    if pages > MAX_CATCHUP_PAGES:
        raise SafetyError("catchup_page_limit", "long-partition gap exceeds the frozen page budget")
    operations = 2 + pages * 2 if gap else 2
    if operations > MAX_CATCHUP_OPERATIONS:
        raise SafetyError("catchup_operation_limit", "long-partition recovery exceeds its operation budget")
    return {"gap": gap, "pages": pages, "operations": operations, "checkpoint_share_count": local_share_count}


def check_rfc_vectors() -> dict[str, bool]:
    # RFC 8032 section 7.1, test 1 (empty message).
    seed = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
    public = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
    signature = (
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    # RFC 7748 section 6.1 Alice/Bob agreement.
    alice_private = bytes.fromhex("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a")
    bob_private = bytes.fromhex("5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb")
    alice_public = bytes.fromhex("8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a")
    bob_public = bytes.fromhex("de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f")
    shared = bytes.fromhex("4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742")
    return {
        "ed25519_public_key": identity_public_key(seed) == public,
        "ed25519_signature": identity_sign(seed, b"") == signature,
        "ed25519_verification": identity_verify(public, b"", signature),
        "x25519_alice_public": x25519(alice_private) == alice_public,
        "x25519_bob_public": x25519(bob_private) == bob_public,
        "x25519_shared_alice": x25519(alice_private, bob_public) == shared,
        "x25519_shared_bob": x25519(bob_private, alice_public) == shared,
    }
