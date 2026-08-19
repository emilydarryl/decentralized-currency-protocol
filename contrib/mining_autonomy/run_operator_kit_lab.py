#!/usr/bin/env python3
"""Build and verify four deterministic portable operator packages."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import operator_kit_v1 as kit
import sharechain_multihost_v1 as safety
import sharechain_routed_v1 as routed


FORMAT = "soveroot-share-sync-operator-kit-lab-evidence-v1"
ROWS = {
    "alpha": ("10.221.1.2", "operator-alpha", "overlay-red"),
    "bravo": ("10.222.1.2", "operator-bravo", "overlay-blue"),
    "charlie": ("10.223.1.2", "operator-charlie", "overlay-red"),
    "delta": ("10.224.1.2", "operator-delta", "overlay-blue"),
}


def secret(label: str) -> str:
    return hashlib.sha256(b"soveroot/operator-kit-lab/v1\x00" + label.encode("ascii")).hexdigest()


def status_fixture() -> dict[str, Any]:
    return {
        "state_commitment_sha256": secret("converged-state"),
        "selected_state": {"selected_tip_share_id": secret("selected-tip")},
        "accepted_share_count": 5,
        "orphan_count": 0,
        "routed_transport": {
            "accepted_inbound_sessions": 3,
            "accepted_inbound_frames": 8,
            "observed_source_prefixes": [
                "10.221.1.0/24", "10.222.1.0/24", "10.223.1.0/24",
            ],
        },
    }


def run_lab(runtime: Path) -> dict[str, Any]:
    directories: dict[str, Path] = {}
    manifests: dict[str, dict[str, Any]] = {}
    for node_id, (host, operator_group, transport) in ROWS.items():
        directory = runtime / node_id
        manifests[node_id] = kit.initialize_operator(
            directory,
            node_id=node_id,
            host=host,
            port=19444,
            operator_group=operator_group,
            transport=transport,
            identity_seed_hex=secret(f"identity:{node_id}"),
            control_key_hex=secret(f"control:{node_id}"),
        )
        directories[node_id] = directory

    checks: dict[str, bool] = {}
    validated = kit.validate_manifest_set(list(manifests.values()))
    checks["four_self_signed_public_manifests_validate"] = len(validated) == 4
    checks["four_distinct_routes_operators_and_identities"] = all(
        len({manifest[field] for manifest in validated}) == 4
        for field in ("endpoint", "operator_group", "identity_public_key_hex")
    ) and len({safety.source_prefix(manifest["host"]) for manifest in validated}) == 4
    checks["two_transport_labels_survive_each_three_peer_view"] = all(
        len({peer["transport"] for peer in validated if peer["node_id"] != local["node_id"]}) >= 2
        for local in validated
    )

    configs = {}
    for node_id, directory in directories.items():
        peer_paths = [
            kit.manifest_path(peer_directory)
            for peer_id, peer_directory in directories.items()
            if peer_id != node_id
        ]
        configs[node_id] = kit.assemble_config(directory, peer_paths)
    checks["four_configs_pass_frozen_routed_profile"] = all(
        routed.load_config(kit.config_path(directories[node_id])) == config
        for node_id, config in configs.items()
    )
    checks["each_config_pins_exactly_three_diverse_peers"] = all(
        len(config["peers"]) == 3 for config in configs.values()
    )
    checks["public_packages_contain_no_private_seed_or_control_key"] = all(
        private[secret_field] not in kit.manifest_path(directory).read_text(encoding="utf-8")
        for directory in directories.values()
        for private in [kit.load_private(kit.private_path(directory))]
        for secret_field in ("identity_seed_hex", "control_key_hex")
    )
    checks["private_files_are_owner_only_on_posix"] = os.name != "posix" or all(
        stat.S_IMODE(path.stat().st_mode) == 0o600
        for directory in directories.values()
        for path in (kit.private_path(directory), kit.config_path(directory))
    )
    campaign_directory = runtime / "campaign"
    campaign = kit.write_campaign(campaign_directory)
    checks["public_campaign_files_match_frozen_commitments"] = all(
        safety.canonical_hash(json.loads((campaign_directory / name).read_text(encoding="utf-8")))
        == commitment
        for name, commitment in campaign["files"].items()
    ) and len(campaign["ordered_steps"]) == 7

    try:
        kit.validate_manifest_set(list(manifests.values())[:3])
    except kit.OperatorKitError:
        checks["three_operator_downgrade_is_rejected"] = True
    else:
        checks["three_operator_downgrade_is_rejected"] = False

    tampered_manifest = copy.deepcopy(manifests["alpha"])
    tampered_manifest["host"] = "10.250.1.2"
    try:
        kit.verify_manifest(tampered_manifest)
    except kit.OperatorKitError:
        checks["tampered_public_manifest_is_rejected"] = True
    else:
        checks["tampered_public_manifest_is_rejected"] = False

    reports = []
    for index, (node_id, directory) in enumerate(directories.items()):
        reports.append(kit.build_evidence(
            kit.load_private(kit.private_path(directory)),
            manifests[node_id],
            status_fixture(),
            run_id="operator-kit-lab-v1",
            campaign_commitment_sha256=campaign["campaign_commitment_sha256"],
            source_revision="ab" * 20,
            observed_tick=1_000 + index,
        ))
    summary = kit.verify_evidence_set(reports)
    checks["four_signed_reports_verify_and_converge"] = (
        summary["all_signatures_valid"] and summary["all_operators_converged"]
    )

    divergent = list(reports)
    bad_status = status_fixture()
    bad_status["state_commitment_sha256"] = secret("divergent-state")
    directory = directories["delta"]
    divergent[-1] = kit.build_evidence(
        kit.load_private(kit.private_path(directory)),
        manifests["delta"],
        bad_status,
        run_id="operator-kit-lab-v1",
        campaign_commitment_sha256=campaign["campaign_commitment_sha256"],
        source_revision="ab" * 20,
        observed_tick=1_003,
    )
    try:
        kit.verify_evidence_set(divergent)
    except kit.OperatorKitError:
        checks["signed_divergent_state_is_rejected"] = True
    else:
        checks["signed_divergent_state_is_rejected"] = False

    evidence = {
        "format": FORMAT,
        "network_id": safety.NETWORK_ID,
        "operator_count": 4,
        "peer_count_per_operator": 3,
        "checks": checks,
        "converged_summary": summary,
        "all_checks_pass": all(checks.values()),
        "limitations": [
            "one_process_generated_all_ci_fixture_keys",
            "no_live_interhost_packets_in_packaging_test",
            "no_independent_operator_or_route_evidence",
            "classical_reference_crypto_not_constant_time_or_post_quantum",
            "pinned_manifests_are_not_permissionless_discovery",
            "no_sybil_or_hostile_internet_claim",
            "no_production_settlement_or_consensus_change",
        ],
    }
    evidence["evidence_commitment_sha256"] = safety.canonical_hash(evidence)
    if not evidence["all_checks_pass"]:
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"operator-kit lab failed checks: {failed}")
    return evidence


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.runtime is not None:
        args.runtime.mkdir(parents=True, exist_ok=True)
        evidence = run_lab(args.runtime)
    else:
        with tempfile.TemporaryDirectory(prefix="soveroot-operator-kit-") as temporary:
            evidence = run_lab(Path(temporary))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Four operator packages passed {len(evidence['checks'])} checks")
    print(f"Evidence: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, kit.OperatorKitError, routed.RoutedError, safety.SafetyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
