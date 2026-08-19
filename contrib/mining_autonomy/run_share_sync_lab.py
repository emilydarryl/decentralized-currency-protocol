#!/usr/bin/env python3
"""Run and retain the three-process Soveroot share-sync private-lab experiment."""

from __future__ import annotations

import argparse
import copy
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

import sharechain_sync_v0 as sync
import sharechain_v0 as reference


FORMAT = "soveroot-share-sync-evidence-v0"
SCRIPT = Path(__file__).resolve().parent / "sharechain_sync_v0.py"


def free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((host, 0))
        return int(listener.getsockname()[1])


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_configs(
    runtime: Path,
    *,
    hosts: dict[str, str] | None = None,
    pair_keys: dict[frozenset[str], str] | None = None,
) -> dict[str, dict[str, Any]]:
    hosts = hosts or {node_id: "127.0.0.1" for node_id in ("alpha", "bravo", "charlie")}
    if set(hosts) != {"alpha", "bravo", "charlie"}:
        raise RuntimeError("share-sync lab requires exact alpha, bravo, and charlie hosts")
    ports = {node_id: free_port(hosts[node_id]) for node_id in ("alpha", "bravo", "charlie")}
    pair_keys = pair_keys or {
        frozenset(("alpha", "bravo")): "ab" * 32,
        frozenset(("alpha", "charlie")): "ac" * 32,
        frozenset(("bravo", "charlie")): "bc" * 32,
    }
    controls = {"alpha": "a1" * 32, "bravo": "b2" * 32, "charlie": "c3" * 32}
    configs = {}
    for node_id in ports:
        peers = []
        for peer_id in ports:
            if peer_id == node_id:
                continue
            peers.append(
                {
                    "node_id": peer_id,
                    "host": hosts[peer_id],
                    "port": ports[peer_id],
                    "shared_key_hex": pair_keys[frozenset((node_id, peer_id))],
                }
            )
        config = {
            "format": sync.PROTOCOL,
            "node_id": node_id,
            "listen_host": hosts[node_id],
            "listen_port": ports[node_id],
            "state_path": str(runtime / f"{node_id}-state.json"),
            "control_key_hex": controls[node_id],
            "trusted_rounds": reference.trusted_rounds(),
            "limits": sync.LIMITS,
            "peers": peers,
        }
        path = runtime / f"{node_id}-config.json"
        write_json(path, config)
        configs[node_id] = {**config, "_path": str(path)}
    return configs


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if key != "_path"}


def start_node(config: dict[str, Any]) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT), "serve", "--config", config["_path"]],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdout is not None
    ready = process.stdout.readline()
    if process.poll() is not None or not ready:
        stderr = "" if process.stderr is None else process.stderr.read()
        raise RuntimeError(f"node {config['node_id']} failed to start: {stderr}")
    event = json.loads(ready)
    if event != {"event": "ready", "node_id": config["node_id"]}:
        raise RuntimeError(f"node {config['node_id']} returned an unexpected ready event")
    return process


def control(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return sync.control(public_config(config), payload)


def status(config: dict[str, Any]) -> dict[str, Any]:
    response = control(config, {"op": "status"})
    if response.get("op") != "status_response":
        raise RuntimeError("node returned an invalid status response")
    return response["status"]


def stop_node(config: dict[str, Any], process: subprocess.Popen[str]) -> None:
    try:
        if process.poll() is None:
            try:
                control(config, {"op": "stop"})
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired, sync.SyncError):
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


def peer_message(
    sender: dict[str, Any],
    recipient_id: str,
    sequence: int,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    peer = next(item for item in sender["peers"] if item["node_id"] == recipient_id)
    envelope = sync.sign_envelope(sender["node_id"], recipient_id, sequence, payload, peer["shared_key_hex"])
    response = sync.send_message(peer["host"], peer["port"], envelope)
    sync.verify_envelope(
        response,
        expected_sender=recipient_id,
        expected_recipient=sender["node_id"],
        key_hex=peer["shared_key_hex"],
    )
    return envelope, response


def expect_no_response(host: str, port: int, encoded: bytes) -> bool:
    try:
        with socket.create_connection((host, port), timeout=sync.SOCKET_TIMEOUT_SECONDS) as connection:
            connection.settimeout(1.0)
            connection.sendall(encoded)
            response = connection.recv(1)
        return response == b""
    except (ConnectionResetError, socket.timeout, OSError):
        return True


def hostile_orphans(count: int) -> list[dict[str, Any]]:
    shares = []
    for index in range(count):
        share = reference.make_share(None, 0, "51", 60 + index)
        share["sequence"] = 1
        share["previous_share_id"] = f"{index + 1:064x}"
        reference.refresh_share_id(share)
        shares.append(share)
    return shares


def run_lab(
    runtime: Path,
    *,
    configs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    configs = build_configs(runtime) if configs is None else configs
    processes = {node_id: start_node(config) for node_id, config in configs.items()}
    checks: dict[str, bool] = {}
    observations: dict[str, Any] = {}
    try:
        scenario = next(
            item for item in reference.build_corpus()["scenarios"] if item["name"] == "valid_linear_chain"
        )
        root, one, two, three, four = copy.deepcopy(scenario["shares"])

        control(configs["alpha"], {"op": "import", "shares": [root]})
        control(configs["bravo"], {"op": "import", "shares": [two]})
        control(configs["charlie"], {"op": "import", "shares": [four, three]})
        initial = {node_id: status(config) for node_id, config in configs.items()}
        checks["delayed_shares_enter_bounded_orphan_sets"] = (
            initial["alpha"]["accepted_share_count"] == 1
            and initial["bravo"]["orphan_count"] == 1
            and initial["charlie"]["orphan_count"] == 2
        )

        control(configs["alpha"], {"op": "sync", "peer_id": "bravo"})
        control(configs["alpha"], {"op": "import", "shares": [one]})
        control(configs["alpha"], {"op": "sync", "peer_id": "bravo"})
        partitioned = {node_id: status(config) for node_id, config in configs.items()}
        checks["partition_is_observable"] = (
            partitioned["alpha"]["state_commitment_sha256"]
            == partitioned["bravo"]["state_commitment_sha256"]
            != partitioned["charlie"]["state_commitment_sha256"]
        )
        observations["partitioned_accepted_counts"] = {
            node_id: view["accepted_share_count"] for node_id, view in partitioned.items()
        }

        before_restart = status(configs["charlie"])
        stop_node(configs["charlie"], processes["charlie"])
        processes["charlie"] = start_node(configs["charlie"])
        after_restart = status(configs["charlie"])
        checks["restart_preserves_pending_state"] = (
            before_restart["orphan_count"] == after_restart["orphan_count"] == 2
            and before_restart["state_commitment_sha256"] == after_restart["state_commitment_sha256"]
        )

        control(configs["bravo"], {"op": "sync", "peer_id": "charlie"})
        selective = {node_id: status(config) for node_id, config in configs.items()}
        checks["selective_relay_is_observable"] = (
            selective["bravo"]["accepted_share_count"]
            == selective["charlie"]["accepted_share_count"]
            == 5
            and selective["alpha"]["accepted_share_count"] == 3
        )
        control(configs["charlie"], {"op": "sync", "peer_id": "alpha"})
        converged = {node_id: status(config) for node_id, config in configs.items()}
        commitments = {view["state_commitment_sha256"] for view in converged.values()}
        tips = {view["selected_state"]["selected_tip_share_id"] for view in converged.values()}
        checks["three_processes_converge"] = (
            len(commitments) == len(tips) == 1
            and all(view["accepted_share_count"] == 5 for view in converged.values())
        )
        checks["reference_and_independent_state_match"] = all(
            view["selected_state"] == reference.evaluate_graph(scenario["shares"], scenario["trusted_rounds"])
            for view in converged.values()
        )

        announcement_one = {
            "slot": 777,
            "state_commitment_sha256": "11" * 32,
            "selected_tip_share_id": "33" * 32,
        }
        announcement_two = {
            "slot": 777,
            "state_commitment_sha256": "22" * 32,
            "selected_tip_share_id": "44" * 32,
        }
        first_envelope, _ = peer_message(
            configs["bravo"],
            "alpha",
            1_000_000,
            {"op": "inventory", "cursor": 0, "announcement": announcement_one},
        )
        peer_message(
            configs["bravo"],
            "alpha",
            1_000_001,
            {"op": "inventory", "cursor": 0, "announcement": announcement_two},
        )
        equivocation_status = status(configs["alpha"])
        checks["authenticated_equivocation_is_preserved"] = equivocation_status["equivocation_count"] == 1
        alpha_state = json.loads(Path(configs["alpha"]["state_path"]).read_text(encoding="utf-8"))
        observations["equivocation_evidence"] = alpha_state["equivocations"]

        peer = next(item for item in configs["bravo"]["peers"] if item["node_id"] == "alpha")
        replay_bytes = sync.canonical_bytes(first_envelope) + b"\n"
        checks["replayed_message_is_rejected"] = expect_no_response(peer["host"], peer["port"], replay_bytes)

        tampered = copy.deepcopy(first_envelope)
        tampered["sequence"] = 1_000_002
        tampered["mac_sha256"] = "00" * 32
        checks["unauthenticated_message_is_rejected"] = expect_no_response(
            peer["host"], peer["port"], sync.canonical_bytes(tampered) + b"\n"
        )

        flood = hostile_orphans(sync.MAX_ORPHANS + 1)
        flood_result = control(configs["alpha"], {"op": "import", "shares": flood})["summary"]
        bounded = status(configs["alpha"])
        checks["orphan_flood_fails_closed_at_limit"] = (
            bounded["orphan_count"] == sync.MAX_ORPHANS
            and flood_result["reasons"].get("orphan_limit") == 1
        )
        expired = control(
            configs["alpha"],
            {"op": "tick", "count": sync.MAX_ORPHAN_AGE_TICKS + 1},
        )
        checks["orphan_age_is_bounded"] = expired["expired"] == sync.MAX_ORPHANS and status(
            configs["alpha"]
        )["orphan_count"] == 0

        oversize = b"{" + b"x" * sync.MAX_MESSAGE_BYTES + b"}\n"
        checks["oversize_message_is_rejected"] = expect_no_response(
            configs["alpha"]["listen_host"], configs["alpha"]["listen_port"], oversize
        )

        final = {node_id: status(config) for node_id, config in configs.items()}
        checks["hostile_inputs_do_not_change_canonical_tip"] = len(
            {view["state_commitment_sha256"] for view in final.values()}
        ) == 1
        observations["final_state_commitment_sha256"] = final["alpha"]["state_commitment_sha256"]
        observations["final_selected_tip_share_id"] = final["alpha"]["selected_state"][
            "selected_tip_share_id"
        ]
        observations["equivocation_count"] = final["alpha"]["equivocation_count"]
        observations["alpha_rejection_counts"] = final["alpha"]["rejection_counts"]

        evidence = {
            "format": FORMAT,
            "profile": sync.PROTOCOL,
            "process_count": 3,
            "limits": sync.LIMITS,
            "checks": checks,
            "observations": observations,
            "all_checks_pass": all(checks.values()),
            "limitations": [
                "loopback_private_lab_only",
                "pairwise_hmac_authentication_not_public_identity",
                "no_peer_discovery",
                "no_sybil_or_eclipse_resistance",
                "no_production_settlement",
                "not_base_consensus",
                "not_final_soveroot_pow",
            ],
        }
        evidence["evidence_commitment_sha256"] = sync.canonical_hash(evidence)
        if not evidence["all_checks_pass"]:
            failed = [name for name, passed in checks.items() if not passed]
            raise RuntimeError(f"share-sync lab failed checks: {failed}")
        return evidence
    finally:
        for node_id, process in processes.items():
            stop_node(configs[node_id], process)


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
        with tempfile.TemporaryDirectory(prefix="soveroot-share-sync-") as directory:
            evidence = run_lab(Path(directory))
    write_json(args.output, evidence)
    print(f"Three authenticated share-sync processes passed {len(evidence['checks'])} checks")
    print(f"Evidence: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, RuntimeError, sync.SyncError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
