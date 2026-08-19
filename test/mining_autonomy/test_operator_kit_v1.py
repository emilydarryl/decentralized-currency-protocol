#!/usr/bin/env python3
"""Tests for the portable four-operator share-sync kit."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "contrib" / "mining_autonomy"
sys.path.insert(0, str(MODULE_DIR))

import operator_kit_v1 as kit  # noqa: E402
import sharechain_multihost_v1 as safety  # noqa: E402
import sharechain_routed_v1 as routed  # noqa: E402


ROWS = {
    "alpha": ("10.211.1.2", "operator-alpha", "overlay-red"),
    "bravo": ("10.212.1.2", "operator-bravo", "overlay-blue"),
    "charlie": ("10.213.1.2", "operator-charlie", "overlay-red"),
    "delta": ("10.214.1.2", "operator-delta", "overlay-blue"),
}
CAMPAIGN_COMMITMENT = kit.build_campaign()["manifest"]["campaign_commitment_sha256"]
SOURCE_REVISION = "ab" * 20


def secret(label: str) -> str:
    return hashlib.sha256(b"soveroot/operator-kit-test/v1\x00" + label.encode("ascii")).hexdigest()


def initialize_all(root: Path, *, transports: dict[str, str] | None = None) -> dict[str, Path]:
    directories = {}
    for node_id, (host, operator_group, default_transport) in ROWS.items():
        directory = root / node_id
        kit.initialize_operator(
            directory,
            node_id=node_id,
            host=host,
            port=19444,
            operator_group=operator_group,
            transport=default_transport if transports is None else transports[node_id],
            identity_seed_hex=secret(f"identity:{node_id}"),
            control_key_hex=secret(f"control:{node_id}"),
        )
        directories[node_id] = directory
    return directories


def converged_status() -> dict[str, Any]:
    return {
        "state_commitment_sha256": secret("state"),
        "selected_state": {"selected_tip_share_id": secret("tip")},
        "accepted_share_count": 5,
        "orphan_count": 0,
        "routed_transport": {
            "accepted_inbound_sessions": 3,
            "accepted_inbound_frames": 6,
            "observed_source_prefixes": [
                "10.211.1.0/24", "10.212.1.0/24", "10.213.1.0/24",
            ],
        },
    }


class OperatorInitializationTests(unittest.TestCase):
    def test_private_secrets_never_enter_public_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "alpha"
            seed = secret("identity:alpha")
            control = secret("control:alpha")
            manifest = kit.initialize_operator(
                directory,
                node_id="alpha",
                host="10.211.1.2",
                port=19444,
                operator_group="operator-alpha",
                transport="overlay-red",
                identity_seed_hex=seed,
                control_key_hex=control,
            )
            public_text = kit.manifest_path(directory).read_text(encoding="utf-8")
            self.assertNotIn(seed, public_text)
            self.assertNotIn(control, public_text)
            self.assertEqual(kit.verify_manifest(manifest)["node_id"], "alpha")
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(kit.private_path(directory).stat().st_mode), 0o600)

    def test_initialization_refuses_to_overwrite_private_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_all(root)
            with self.assertRaises(FileExistsError):
                kit.initialize_operator(
                    root / "alpha",
                    node_id="alpha",
                    host="10.211.1.2",
                    port=19444,
                    operator_group="operator-alpha",
                    transport="overlay-red",
                    identity_seed_hex=secret("replacement"),
                    control_key_hex=secret("replacement-control"),
                )


class OperatorAssemblyTests(unittest.TestCase):
    def test_campaign_is_deterministic_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "campaign"
            expected = kit.build_campaign()["manifest"]
            written = kit.write_campaign(directory)
            self.assertEqual(written, expected)
            self.assertEqual(
                json.loads((directory / "campaign.json").read_text(encoding="utf-8")),
                expected,
            )
            tampered = dict(expected)
            tampered["scenario"] = "different_scenario"
            with self.assertRaises(kit.OperatorKitError):
                kit.verify_campaign(tampered)
            with self.assertRaises(FileExistsError):
                kit.write_campaign(directory)

    def test_four_independent_manifests_build_four_frozen_configs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directories = initialize_all(Path(temporary))
            manifests = {
                node_id: kit.manifest_path(directory)
                for node_id, directory in directories.items()
            }
            validated = kit.validate_manifest_set([
                kit.load_manifest(path) for path in manifests.values()
            ])
            self.assertEqual(len(validated), kit.REQUIRED_OPERATOR_COUNT)
            for node_id, directory in directories.items():
                config = kit.assemble_config(
                    directory,
                    [path for peer_id, path in manifests.items() if peer_id != node_id],
                )
                self.assertEqual(len(config["peers"]), 3)
                self.assertEqual(routed.load_config(kit.config_path(directory)), config)
                public_text = kit.manifest_path(directory).read_text(encoding="utf-8")
                private = kit.load_private(kit.private_path(directory))
                self.assertNotIn(private["identity_seed_hex"], public_text)
                self.assertNotIn(private["control_key_hex"], public_text)

    def test_tampered_manifest_and_three_operator_set_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directories = initialize_all(Path(temporary))
            manifests = [
                kit.load_manifest(kit.manifest_path(directory))
                for directory in directories.values()
            ]
            tampered = dict(manifests[0])
            tampered["host"] = "10.250.1.2"
            with self.assertRaises(kit.OperatorKitError):
                kit.verify_manifest(tampered)
            with self.assertRaises(kit.OperatorKitError):
                kit.validate_manifest_set(manifests[:3])

    def test_transport_monoculture_fails_diversity_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directories = initialize_all(
                Path(temporary), transports={node_id: "overlay-only" for node_id in ROWS}
            )
            with self.assertRaises(safety.SafetyError):
                kit.validate_manifest_set([
                    kit.load_manifest(kit.manifest_path(directory))
                    for directory in directories.values()
                ])


class OperatorEvidenceTests(unittest.TestCase):
    def test_four_signed_reports_prove_one_converged_nonempty_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directories = initialize_all(Path(temporary))
            evidence = []
            for node_id, directory in directories.items():
                evidence.append(kit.build_evidence(
                    kit.load_private(kit.private_path(directory)),
                    kit.load_manifest(kit.manifest_path(directory)),
                    converged_status(),
                    run_id="independent-run-001",
                    campaign_commitment_sha256=CAMPAIGN_COMMITMENT,
                    source_revision=SOURCE_REVISION,
                    observed_tick=100 + len(evidence),
                ))
            summary = kit.verify_evidence_set(evidence)
            self.assertTrue(summary["all_signatures_valid"])
            self.assertTrue(summary["all_operators_converged"])
            self.assertEqual(summary["operator_count"], 4)

    def test_tampered_or_divergent_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directories = initialize_all(Path(temporary))
            reports = []
            for directory in directories.values():
                reports.append(kit.build_evidence(
                    kit.load_private(kit.private_path(directory)),
                    kit.load_manifest(kit.manifest_path(directory)),
                    converged_status(),
                    run_id="independent-run-002",
                    campaign_commitment_sha256=CAMPAIGN_COMMITMENT,
                    source_revision=SOURCE_REVISION,
                    observed_tick=200,
                ))
            tampered = [dict(report) for report in reports]
            tampered[0]["accepted_share_count"] = 6
            with self.assertRaises(kit.OperatorKitError):
                kit.verify_evidence_set(tampered)

            orphaned_status = converged_status()
            orphaned_status["orphan_count"] = 1
            directory = directories["delta"]
            reports[-1] = kit.build_evidence(
                kit.load_private(kit.private_path(directory)),
                kit.load_manifest(kit.manifest_path(directory)),
                orphaned_status,
                run_id="independent-run-002",
                campaign_commitment_sha256=CAMPAIGN_COMMITMENT,
                source_revision=SOURCE_REVISION,
                observed_tick=200,
            )
            with self.assertRaises(kit.OperatorKitError):
                kit.verify_evidence_set(reports)

            divergent_status = converged_status()
            divergent_status["state_commitment_sha256"] = secret("divergent-state")
            reports[-1] = kit.build_evidence(
                kit.load_private(kit.private_path(directory)),
                kit.load_manifest(kit.manifest_path(directory)),
                divergent_status,
                run_id="independent-run-002",
                campaign_commitment_sha256=CAMPAIGN_COMMITMENT,
                source_revision=SOURCE_REVISION,
                observed_tick=200,
            )
            with self.assertRaises(kit.OperatorKitError):
                kit.verify_evidence_set(reports)


if __name__ == "__main__":
    unittest.main()
