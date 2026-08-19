#!/usr/bin/env python3
"""Run four live share validators in distinct routed Linux network namespaces."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import sharechain_multihost_v1 as safety
import sharechain_routed_v1 as routed
import sharechain_sync_v0 as sync
import sharechain_v0 as reference


FORMAT = "soveroot-share-sync-routed-namespace-evidence-v1"
SCRIPT = Path(__file__).resolve().parent / "sharechain_routed_v1.py"
PORT = 19444
CONTROL_HOST = "10.200.1.2"
CONTROL_GATEWAY = "10.200.1.1"
CONTROL_NETWORK = "10.200.1.0/30"
NODES = {
    "alpha": {
        "host": "10.201.1.2", "gateway": "10.201.1.1",
        "operator_group": "operator-alpha", "transport": "namespace-tcp-red",
    },
    "bravo": {
        "host": "10.202.1.2", "gateway": "10.202.1.1",
        "operator_group": "operator-bravo", "transport": "namespace-tcp-blue",
    },
    "charlie": {
        "host": "10.203.1.2", "gateway": "10.203.1.1",
        "operator_group": "operator-charlie", "transport": "namespace-tcp-red",
    },
    "delta": {
        "host": "10.204.1.2", "gateway": "10.204.1.1",
        "operator_group": "operator-delta", "transport": "namespace-tcp-blue",
    },
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fixture_secret(label: str) -> str:
    return hashlib.sha256(b"soveroot/routed-namespace/fixture/v1\x00" + label.encode("ascii")).hexdigest()


def build_configs(runtime: Path) -> dict[str, dict[str, Any]]:
    identities = {node_id: fixture_secret(f"identity:{node_id}") for node_id in NODES}
    configs: dict[str, dict[str, Any]] = {}
    for node_id, row in NODES.items():
        peers = []
        for peer_id, peer in NODES.items():
            if peer_id == node_id:
                continue
            peers.append({
                "node_id": peer_id,
                "host": peer["host"],
                "port": PORT,
                "endpoint": f"{peer['host']}:{PORT}",
                "identity_public_key_hex": safety.identity_public_key(identities[peer_id]),
                "operator_group": peer["operator_group"],
                "transport": peer["transport"],
            })
        config = {
            "format": routed.CONFIG_FORMAT,
            "node_id": node_id,
            "listen_host": row["host"],
            "listen_port": PORT,
            "endpoint": f"{row['host']}:{PORT}",
            "control_host": CONTROL_HOST,
            "state_path": str(runtime / f"{node_id}-state.json"),
            "transport_state_path": str(runtime / f"{node_id}-transport.json"),
            "control_key_hex": fixture_secret(f"control:{node_id}"),
            "identity_seed_hex": identities[node_id],
            "operator_group": row["operator_group"],
            "transport": row["transport"],
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
        write_json(path, config)
        loaded = routed.load_config(path)
        configs[node_id] = {**loaded, "_path": str(path)}
    return configs


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if key != "_path"}


class NamespaceTopology:
    def __init__(self, configs: dict[str, dict[str, Any]]) -> None:
        if os.name != "posix" or os.geteuid() != 0:
            raise RuntimeError("routed namespace evidence requires Linux root privileges")
        if shutil.which("ip") is None:
            raise RuntimeError("routed namespace evidence requires iproute2")
        self.configs = configs
        suffix = str(os.getpid() % 10_000).zfill(4)
        self.rows = {
            node_id: {
                "namespace": f"sovr-{suffix}-{index}",
                "router_if": f"sr{suffix}{index}r",
                "node_if": f"sr{suffix}{index}n",
            }
            for index, node_id in enumerate(configs)
        }
        self.router_namespace = f"sovr-{suffix}-router"
        self.control_host_if = f"sr{suffix}mh"
        self.control_router_if = f"sr{suffix}mr"
        self.processes: dict[str, subprocess.Popen[str]] = {}

    @staticmethod
    def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, check=check, text=True, capture_output=True, encoding="utf-8")

    def setup(self) -> None:
        self._run(["ip", "netns", "add", self.router_namespace])
        self._run([
            "ip", "link", "add", self.control_host_if, "type", "veth",
            "peer", "name", self.control_router_if,
        ])
        self._run(["ip", "link", "set", self.control_router_if, "netns", self.router_namespace])
        self._run(["ip", "addr", "add", f"{CONTROL_HOST}/30", "dev", self.control_host_if])
        self._run(["ip", "link", "set", self.control_host_if, "up"])
        self._run([
            "ip", "netns", "exec", self.router_namespace,
            "ip", "link", "set", "lo", "up",
        ])
        self._run([
            "ip", "netns", "exec", self.router_namespace,
            "ip", "addr", "add", f"{CONTROL_GATEWAY}/30", "dev", self.control_router_if,
        ])
        self._run([
            "ip", "netns", "exec", self.router_namespace,
            "ip", "link", "set", self.control_router_if, "up",
        ])
        self._run([
            "ip", "netns", "exec", self.router_namespace,
            "sysctl", "-q", "-w", "net.ipv4.ip_forward=1",
        ])
        for node_id, config in self.configs.items():
            row = self.rows[node_id]
            self._run(["ip", "netns", "add", row["namespace"]])
            self._run([
                "ip", "link", "add", row["router_if"], "type", "veth",
                "peer", "name", row["node_if"],
            ])
            self._run(["ip", "link", "set", row["router_if"], "netns", self.router_namespace])
            self._run(["ip", "link", "set", row["node_if"], "netns", row["namespace"]])
            self._run([
                "ip", "netns", "exec", self.router_namespace, "ip", "addr", "add",
                f"{NODES[node_id]['gateway']}/24", "dev", row["router_if"],
            ])
            self._run([
                "ip", "netns", "exec", self.router_namespace,
                "ip", "link", "set", row["router_if"], "up",
            ])
            self._run(["ip", "netns", "exec", row["namespace"], "ip", "link", "set", "lo", "up"])
            self._run([
                "ip", "netns", "exec", row["namespace"], "ip", "addr", "add",
                f"{config['listen_host']}/24", "dev", row["node_if"],
            ])
            self._run(["ip", "netns", "exec", row["namespace"], "ip", "link", "set", row["node_if"], "up"])
            self._run([
                "ip", "netns", "exec", row["namespace"], "ip", "route", "add", "default",
                "via", NODES[node_id]["gateway"],
            ])
            network = f"{config['listen_host'].rsplit('.', 1)[0]}.0/24"
            self._run([
                "ip", "route", "add", network, "via", CONTROL_GATEWAY,
                "dev", self.control_host_if,
            ])

    def start_node(self, node_id: str) -> subprocess.Popen[str]:
        config = self.configs[node_id]
        row = self.rows[node_id]
        process = subprocess.Popen(
            [
                "ip", "netns", "exec", row["namespace"], sys.executable, str(SCRIPT),
                "serve", "--config", config["_path"],
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        assert process.stdout is not None
        ready = process.stdout.readline()
        if process.poll() is not None or not ready:
            stderr = "" if process.stderr is None else process.stderr.read()
            raise RuntimeError(f"node {node_id} failed to start: {stderr}")
        if json.loads(ready) != {"event": "ready", "node_id": node_id}:
            raise RuntimeError(f"node {node_id} returned an unexpected ready event")
        self.processes[node_id] = process
        return process

    def stop_node(self, node_id: str) -> None:
        process = self.processes.get(node_id)
        if process is None:
            return
        try:
            if process.poll() is None:
                try:
                    control(self.configs[node_id], {"op": "stop"})
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired, sync.SyncError, routed.RoutedError):
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
            del self.processes[node_id]

    def probe(self, source_id: str, target_id: str, nonce_hex: str) -> subprocess.CompletedProcess[str]:
        row = self.rows[source_id]
        return self._run([
            "ip", "netns", "exec", row["namespace"], sys.executable, str(SCRIPT),
            "probe", "--config", self.configs[source_id]["_path"],
            "--peer", target_id, "--nonce", nonce_hex,
        ], check=False)

    def cleanup(self) -> None:
        for node_id in list(self.processes):
            self.stop_node(node_id)
        for row in reversed(list(self.rows.values())):
            self._run(["ip", "netns", "del", row["namespace"]], check=False)
        for config in self.configs.values():
            network = f"{config['listen_host'].rsplit('.', 1)[0]}.0/24"
            self._run([
                "ip", "route", "del", network, "via", CONTROL_GATEWAY,
                "dev", self.control_host_if,
            ], check=False)
        self._run(["ip", "link", "del", self.control_host_if], check=False)
        self._run(["ip", "netns", "del", self.router_namespace], check=False)


def control(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return routed._send_control(public_config(config), payload)


def status(config: dict[str, Any]) -> dict[str, Any]:
    response = control(config, {"op": "status"})
    if response.get("op") != "status_response":
        raise RuntimeError("node returned an invalid status response")
    return response["status"]


def run_lab(runtime: Path) -> dict[str, Any]:
    configs = build_configs(runtime)
    topology = NamespaceTopology(configs)
    checks: dict[str, bool] = {}
    observations: dict[str, Any] = {}
    phase = "topology setup"
    try:
        topology.setup()
        for node_id in configs:
            phase = f"start node {node_id}"
            topology.start_node(node_id)

        phase = "validate topology configuration"
        prefixes = {safety.source_prefix(row["listen_host"]) for row in configs.values()}
        checks["four_non_loopback_routed_prefixes"] = (
            len(prefixes) == 4
            and all(not ipaddress_is_loopback(row["listen_host"]) for row in configs.values())
        )
        checks["peer_configs_contain_no_pairwise_wire_secret"] = all(
            "shared_key_hex" not in peer
            for config in configs.values()
            for peer in config["peers"]
        )
        checks["each_node_has_three_operator_and_two_transport_labels"] = all(
            len({peer["operator_group"] for peer in config["peers"]}) == 3
            and len({peer["transport"] for peer in config["peers"]}) >= 2
            for config in configs.values()
        )

        scenario = next(
            item for item in reference.build_corpus()["scenarios"] if item["name"] == "valid_linear_chain"
        )
        root, one, two, three, four = copy.deepcopy(scenario["shares"])
        phase = "seed delayed-delivery fixtures"
        control(configs["alpha"], {"op": "import", "shares": [root]})
        control(configs["bravo"], {"op": "import", "shares": [two]})
        control(configs["charlie"], {"op": "import", "shares": [four, three]})
        control(configs["delta"], {"op": "import", "shares": [root]})

        phase = "capture initial node status"
        initial = {node_id: status(config) for node_id, config in configs.items()}
        checks["delayed_delivery_crosses_live_process_boundaries"] = (
            initial["alpha"]["accepted_share_count"] == initial["delta"]["accepted_share_count"] == 1
            and initial["bravo"]["orphan_count"] == 1
            and initial["charlie"]["orphan_count"] == 2
        )
        phase = "synchronize alpha with bravo"
        control(configs["alpha"], {"op": "sync", "peer_id": "bravo"})
        control(configs["alpha"], {"op": "import", "shares": [one]})
        control(configs["alpha"], {"op": "sync", "peer_id": "bravo"})

        phase = "exercise replay protection across charlie restart"
        replay_nonce = fixture_secret("replay:bravo-charlie")
        first_probe = topology.probe("bravo", "charlie", replay_nonce)
        before_restart = status(configs["charlie"])
        topology.stop_node("charlie")
        topology.start_node("charlie")
        after_restart = status(configs["charlie"])
        replay_probe = topology.probe("bravo", "charlie", replay_nonce)
        checks["live_handshake_is_accepted_before_replay"] = first_probe.returncode == 0
        checks["replay_nonce_state_survives_restart"] = (
            before_restart["routed_transport"]["remembered_replay_nonce_count"]
            == after_restart["routed_transport"]["remembered_replay_nonce_count"]
            and after_restart["routed_transport"]["remembered_replay_nonce_count"] > 0
        )
        checks["replayed_live_handshake_is_rejected_after_restart"] = replay_probe.returncode != 0

        phase = "converge all four routed nodes"
        control(configs["bravo"], {"op": "sync", "peer_id": "charlie"})
        control(configs["charlie"], {"op": "sync", "peer_id": "alpha"})
        control(configs["delta"], {"op": "sync", "peer_id": "alpha"})
        final = {node_id: status(config) for node_id, config in configs.items()}
        commitments = {view["state_commitment_sha256"] for view in final.values()}
        tips = {view["selected_state"]["selected_tip_share_id"] for view in final.values()}
        checks["four_routed_processes_converge"] = (
            len(commitments) == len(tips) == 1
            and all(view["accepted_share_count"] == 5 for view in final.values())
        )
        checks["reference_and_independent_validators_match"] = all(
            view["selected_state"] == reference.evaluate_graph(
                scenario["shares"], scenario["trusted_rounds"]
            )
            for view in final.values()
        )
        checks["fresh_live_sessions_rotate_transcripts"] = (
            final["bravo"]["routed_transport"]["distinct_transcript_count"] >= 2
        )
        checks["live_session_frames_cross_routed_namespaces"] = sum(
            view["routed_transport"]["accepted_inbound_frames"] for view in final.values()
        ) >= 8
        observed = {
            prefix
            for view in final.values()
            for prefix in view["routed_transport"]["observed_source_prefixes"]
        }
        checks["pinned_source_prefixes_are_observed_on_wire"] = prefixes.issubset(observed)

        phase = "validate persisted signed announcements"
        signed_records = []
        for config in configs.values():
            state = json.loads(Path(config["state_path"]).read_text(encoding="utf-8"))
            signed_records.extend(
                record
                for slots in state["announcements"].values()
                for record in slots.values()
            )
        checks["all_live_announcements_are_portably_signed"] = bool(signed_records) and all(
            set(record) == {"signed_announcement"} for record in signed_records
        )

        phase = "assemble routed namespace evidence"
        observations = {
            "final_state_commitment_sha256": final["alpha"]["state_commitment_sha256"],
            "final_selected_tip_share_id": final["alpha"]["selected_state"]["selected_tip_share_id"],
            "accepted_inbound_sessions": {
                node_id: view["routed_transport"]["accepted_inbound_sessions"]
                for node_id, view in final.items()
            },
            "accepted_inbound_frames": {
                node_id: view["routed_transport"]["accepted_inbound_frames"]
                for node_id, view in final.items()
            },
            "observed_source_prefixes": sorted(observed),
            "replay_rejection_recorded": (
                status(configs["charlie"])["routed_transport"]["rejected_connections"].get(
                    "replayed_handshake", 0
                )
                >= 1
            ),
        }
        evidence = {
            "format": FORMAT,
            "profile": safety.PROTOCOL,
            "topology": {
                "kind": "linux-network-namespaces-with-isolated-router",
                "process_count": 4,
                "namespace_count": 5,
                "node_namespace_count": 4,
                "router_namespace_count": 1,
                "control_network": CONTROL_NETWORK,
                "listener_prefixes": sorted(prefixes),
                "operator_group_count": 4,
                "configured_transport_label_count": 2,
            },
            "limits": {
                "sync": sync.LIMITS,
                "safety": safety.LIMITS,
                "transport": routed.TRANSPORT_LIMITS,
            },
            "checks": checks,
            "observations": observations,
            "all_checks_pass": all(checks.values()),
            "limitations": [
                "one_physical_github_runner",
                "one_administrator_and_kernel",
                "configured_transport_labels_share_one_tcp_stack",
                "fixture_keys_not_deployment_keys",
                "classical_reference_crypto_not_constant_time_or_post_quantum",
                "no_peer_discovery_or_sybil_resistance",
                "no_hostile_internet_route_or_anonymity_evidence",
                "no_production_settlement_or_base_consensus_change",
            ],
        }
        evidence["evidence_commitment_sha256"] = safety.canonical_hash(evidence)
        if not evidence["all_checks_pass"]:
            failed = [name for name, passed in checks.items() if not passed]
            raise RuntimeError(f"routed namespace lab failed checks: {failed}")
        return evidence
    except Exception as error:
        raise RuntimeError(f"{phase}: {error}") from error
    finally:
        topology.cleanup()


def ipaddress_is_loopback(value: str) -> bool:
    import ipaddress

    return ipaddress.ip_address(value).is_loopback


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.runtime is not None:
        args.runtime.mkdir(parents=True, exist_ok=True)
        evidence = run_lab(args.runtime)
    else:
        with tempfile.TemporaryDirectory(prefix="soveroot-routed-share-sync-") as directory:
            evidence = run_lab(Path(directory))
    write_json(args.output, evidence)
    print(f"Four routed share-sync namespaces passed {len(evidence['checks'])} checks")
    print(f"Evidence: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError, json.JSONDecodeError, UnicodeDecodeError, RuntimeError,
        routed.RoutedError, safety.SafetyError, sync.SyncError, reference.ProfileError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
