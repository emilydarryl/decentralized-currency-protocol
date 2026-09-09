# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Build or verify the non-consensus PoW v1 challenge-pack manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence


FORMAT = "soveroot-pow-v1-challenge-pack-v0"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = Path(__file__).with_name("challenge_pack_manifest_v0.json")
PACK_FILES = (
    "docs/pow-v1-candidate-spec.md",
    "docs/pow-v1-external-attack-challenge.md",
    "docs/pow-v1-external-evaluator-runbook.md",
    "docs/pow-v1-independent-research-call.md",
    "docs/pow-v1-challenge-campaign.md",
    "docs/pow-v1-ai-assisted-attack-policy.md",
    "contrib/pow_research_v1/challenge_pack.py",
    "contrib/pow_research_v1/powvm.py",
    "contrib/pow_research_v1/external_attack_challenge.py",
    "contrib/pow_research_v1/external_attack_challenge_v0.json",
    "contrib/pow_research_v1/external_attack_submission_template_v0.json",
    "contrib/pow_research_v1/external_attack_results_template_v0.json",
    "contrib/pow_research_v1/independent_research_call_v0.json",
    "contrib/pow_research_v1/vectors/v1.json",
    "contrib/pow_research_v1/vectors/external_attack_qualification_v0.json",
    ".github/ISSUE_TEMPLATE/pow-attack-submission.md",
    ".github/ISSUE_TEMPLATE/pow-attack-evaluator.md",
    ".github/ISSUE_TEMPLATE/pow-hardware-review.md",
    "test/pow_research/test_challenge_pack_v1.py",
)


class PackError(ValueError):
    """The challenge pack is incomplete or differs from its manifest."""


def _sha3_384(path: Path) -> str:
    digest = hashlib.sha3_384()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_document(root: Path = ROOT) -> dict[str, object]:
    files = []
    for relative in PACK_FILES:
        path = root / relative
        if not path.is_file():
            raise PackError(f"missing challenge-pack file: {relative}")
        files.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha3_384": _sha3_384(path),
            }
        )
    return {
        "format": FORMAT,
        "version": "0.1",
        "status": "PRE-RELEASE; FREEZE REQUIRES AN ATTRIBUTABLE GIT TAG",
        "purpose": "isolated non-consensus PoW v1 external attack and hardware-review campaign",
        "hash_algorithm": "SHA3-384 over exact file bytes",
        "self_included": False,
        "freeze_rule": "The release tag, commit, archive digest, manifest digest, and verification log must be published before a campaign round opens.",
        "files": files,
    }


def write_manifest(path: Path = DEFAULT_MANIFEST, root: Path = ROOT) -> None:
    path.write_text(
        json.dumps(build_document(root), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def verify_manifest(path: Path = DEFAULT_MANIFEST, root: Path = ROOT) -> None:
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PackError(f"cannot read manifest {path}: {error}") from error
    expected = build_document(root)
    if actual != expected:
        raise PackError(
            "challenge-pack manifest does not match the working tree; "
            "review changes and rebuild it explicitly"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    if args.command == "build":
        write_manifest(args.manifest)
    else:
        verify_manifest(args.manifest)
        print(f"verified {len(PACK_FILES)} challenge-pack files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
