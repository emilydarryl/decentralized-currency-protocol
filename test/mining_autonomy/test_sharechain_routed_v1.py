#!/usr/bin/env python3
"""Focused tests for the live routed share-sync session boundary."""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "contrib" / "mining_autonomy"
sys.path.insert(0, str(MODULE_DIR))

import sharechain_multihost_v1 as safety  # noqa: E402
import sharechain_routed_v1 as routed  # noqa: E402
import sharechain_sync_v0 as sync  # noqa: E402
import sharechain_v0 as reference  # noqa: E402
import run_share_routed_namespace_lab as namespace_lab  # noqa: E402


SCRIPT = MODULE_DIR / "sharechain_routed_v1.py"
ROWS = {
    "alpha": ("127.31.1.1", "127.31.1.254", "operator-alpha", "loopback-red"),
    "bravo": ("127.32.1.1", "127.32.1.254", "operator-bravo", "loopback-blue"),
    "charlie": ("127.33.1.1", "127.33.1.254", "operator-charlie", "loopback-red"),
    "delta": ("127.34.1.1", "127.34.1.254", "operator-delta", "loopback-blue"),
}


def secret(label: str) -> str:
    return hashlib.sha256(b"soveroot/routed-test/v1\x00" + label.encode("ascii")).hexdigest()


def free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((host, 0))
        return int(listener.getsockname()[1])


def configs(runtime: Path) -> dict[str, dict[str, Any]]:
    ports = {node_id: free_port(row[0]) for node_id, row in ROWS.items()}
    identities = {node_id: secret(f"identity:{node_id}") for node_id in ROWS}
    result = {}
    for node_id, (host, controller, operator, transport) in ROWS.items():
        peers = []
        for peer_id, (peer_host, _, peer_operator, peer_transport) in ROWS.items():
            if peer_id == node_id:
                continue
            peers.append({
                "node_id": peer_id,
                "host": peer_host,
                "port": ports[peer_id],
                "endpoint": f"{peer_host}:{ports[peer_id]}",
                "identity_public_key_hex": safety.identity_public_key(identities[peer_id]),
                "operator_group": peer_operator,
                "transport": peer_transport,
            })
        config = {
            "format": routed.CONFIG_FORMAT,
            "node_id": node_id,
            "listen_host": host,
            "listen_port": ports[node_id],
            "endpoint": f"{host}:{ports[node_id]}",
            "control_host": controller,
            "state_path": str(runtime / f"{node_id}-state.json"),
            "transport_state_path": str(runtime / f"{node_id}-transport.json"),
            "control_key_hex": secret(f"control:{node_id}"),
            "identity_seed_hex": identities[node_id],
            "operator_group": operator,
            "transport": transport,
            "network_id": safety.NETWORK_ID,
            "trusted_rounds": reference.trusted_rounds(),
            "limits": {
                "sync": sync.LIMITS,
                "safety": safety.LIMITS,
                "transport": routed.TRANSPORT_LIMITS,
            },
            "peers": peers,
        }
        path = runtime / f"{node_id}-config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        result[node_id] = {**routed.load_config(path), "_path": str(path)}
    return result


def public(config: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if key != "_path"}


def start(config: dict[str, Any]) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT), "serve", "--config", config["_path"]],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdout is not None
    ready = process.stdout.readline()
    if not ready:
        stderr = "" if process.stderr is None else process.stderr.read()
        raise AssertionError(f"routed node failed to start: {stderr}")
    if json.loads(ready) != {"event": "ready", "node_id": config["node_id"]}:
        raise AssertionError("routed node returned the wrong ready event")
    return process


def stop(config: dict[str, Any], process: subprocess.Popen[str]) -> None:
    try:
        if process.poll() is None:
            try:
                routed._send_control(public(config), {"op": "stop"})
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired, sync.SyncError, routed.RoutedError):
                process.terminate()
                process.wait(timeout=5)
    finally:
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()


class RoutedConfigTests(unittest.TestCase):
    def test_namespace_configs_pin_one_separate_controller_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            built = namespace_lab.build_configs(Path(directory))
            self.assertEqual(
                {config["control_host"] for config in built.values()},
                {namespace_lab.CONTROL_HOST},
            )
            self.assertNotIn(
                safety.source_prefix(namespace_lab.CONTROL_HOST),
                {safety.source_prefix(config["listen_host"]) for config in built.values()},
            )

    def test_config_has_pinned_public_peers_and_no_wire_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            built = configs(Path(directory))
            self.assertEqual(set(built), set(ROWS))
            for config in built.values():
                self.assertEqual(len(config["peers"]), 3)
                self.assertTrue(all("shared_key_hex" not in peer for peer in config["peers"]))
                self.assertEqual(len({safety.source_prefix(peer["host"]) for peer in config["peers"]}), 3)

    def test_config_rejects_same_prefix_and_identity_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            built = configs(Path(directory))
            path = Path(built["alpha"]["_path"])
            value = public(built["alpha"])
            value["peers"][0]["host"] = "127.31.1.2"
            value["peers"][0]["endpoint"] = f"127.31.1.2:{value['peers'][0]['port']}"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises((routed.RoutedError, safety.SafetyError)):
                routed.load_config(path)


class RoutedLiveBoundaryTests(unittest.TestCase):
    def test_live_session_sync_rotates_and_replay_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            built = configs(Path(directory))
            alpha = start(built["alpha"])
            bravo = start(built["bravo"])
            try:
                scenario = next(
                    item for item in reference.build_corpus()["scenarios"]
                    if item["name"] == "valid_linear_chain"
                )
                root = scenario["shares"][0]
                routed._send_control(public(built["alpha"]), {"op": "import", "shares": [root]})
                routed._send_control(public(built["alpha"]), {"op": "sync", "peer_id": "bravo"})
                routed._send_control(public(built["alpha"]), {"op": "sync", "peer_id": "bravo"})
                bravo_status = routed._send_control(public(built["bravo"]), {"op": "status"})["status"]
                self.assertEqual(bravo_status["accepted_share_count"], 1)
                self.assertGreaterEqual(bravo_status["routed_transport"]["accepted_inbound_frames"], 2)
                self.assertGreaterEqual(bravo_status["routed_transport"]["distinct_transcript_count"], 2)

                nonce = secret("persisted-replay")
                self.assertTrue(routed.probe_peer(public(built["alpha"]), "bravo", nonce)["accepted"])
                before = routed._send_control(public(built["bravo"]), {"op": "status"})["status"]
                stop(built["bravo"], bravo)
                bravo = start(built["bravo"])
                after = routed._send_control(public(built["bravo"]), {"op": "status"})["status"]
                self.assertEqual(
                    before["routed_transport"]["remembered_replay_nonce_count"],
                    after["routed_transport"]["remembered_replay_nonce_count"],
                )
                with self.assertRaises((OSError, routed.RoutedError)):
                    routed.probe_peer(public(built["alpha"]), "bravo", nonce)
            finally:
                stop(built["alpha"], alpha)
                stop(built["bravo"], bravo)


if __name__ == "__main__":
    unittest.main()
