# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Issue and validate artifacts for the non-consensus PoW v1 attack challenge.

This tool never executes a submitted program and never proves that a memory
claim is true. It validates the public artifact contract and independently
checks any claimed canonical output with the ordinary reference evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .powvm import MASK64, Params, evaluate, prepare_epoch


CHALLENGE_FORMAT = "soveroot-pow-v1-external-attack-challenge-v0"
SUBMISSION_FORMAT = "soveroot-pow-v1-external-attack-submission-v0"
CASE_SET_FORMAT = "soveroot-pow-v1-external-attack-case-set-v0"
RESULTS_FORMAT = "soveroot-pow-v1-external-attack-results-v0"
DEFAULT_CHALLENGE = Path(__file__).with_name("external_attack_challenge_v0.json")
SEED_DOMAIN = b"Soveroot/PowResearch/BenchmarkSeed/v1\x00"
EVALUATOR_SALT_DOMAIN = b"Soveroot/PowResearch/ExternalAttackEvaluatorSalt/v0\x00"
FRESH_SEED_DOMAIN = b"Soveroot/PowResearch/ExternalAttackFreshSeeds/v0\x00"
ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{2,63}\Z")
HEX40_RE = re.compile(r"[0-9a-f]{40}\Z")
HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")
HEX96_RE = re.compile(r"[0-9a-f]{96}\Z")
RESULT_KEYS = {
    "digest",
    "registers",
    "schedule_digest",
    "dataset_digest",
    "memory_commitment",
}


class ChallengeError(ValueError):
    """An artifact violates the frozen challenge contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ChallengeError(message)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ChallengeError(f"cannot read JSON from {path}: {error}") from error
    _require(isinstance(document, dict), f"{path} must contain one JSON object")
    return document


def _write_json(path: Path | None, document: dict[str, Any]) -> None:
    rendered = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(rendered, end="")
    else:
        path.write_text(rendered, encoding="utf-8", newline="\n")


def _canonical_bytes(document: object) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _commit(document: object) -> str:
    return hashlib.sha3_384(_canonical_bytes(document)).hexdigest()


def _nonnegative_integer(value: object, label: str) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool), f"{label} must be an integer")
    _require(value >= 0, f"{label} must be nonnegative")
    return value


def seed_for(index: int) -> bytes:
    _require(
        isinstance(index, int) and not isinstance(index, bool),
        "seed index must be an integer",
    )
    _require(0 <= index <= 0xFFFFFFFF, "seed index must fit uint32")
    return hashlib.sha3_384(SEED_DOMAIN + index.to_bytes(4, "little")).digest()


def evaluator_salt_commitment(evaluator_salt: bytes) -> str:
    _require(len(evaluator_salt) == 32, "evaluator salt must be exactly 32 bytes")
    return hashlib.sha3_384(EVALUATOR_SALT_DOMAIN + evaluator_salt).hexdigest()


def derive_fresh_seed_indices(
    *,
    evaluator_salt: bytes,
    submitter_salt: bytes,
    source_revision: str,
    excluded_indices: list[int],
    count: int,
) -> list[int]:
    _require(len(evaluator_salt) == 32, "evaluator salt must be exactly 32 bytes")
    _require(len(submitter_salt) == 32, "submitter salt must be exactly 32 bytes")
    _require(
        isinstance(source_revision, str) and HEX40_RE.fullmatch(source_revision) is not None,
        "source revision must be 40 lowercase hexadecimal characters",
    )
    _require(
        isinstance(count, int) and not isinstance(count, bool) and 1 <= count <= 32,
        "fresh case count must be in [1, 32]",
    )
    _require(isinstance(excluded_indices, list), "excluded seed indices must be a list")
    excluded = set(excluded_indices)
    _require(
        len(excluded) == len(excluded_indices)
        and all(isinstance(index, int) and not isinstance(index, bool) and 0 <= index <= 0xFFFFFFFF for index in excluded),
        "excluded seed indices must be unique uint32 values",
    )
    material = hashlib.shake_256(
        FRESH_SEED_DOMAIN
        + evaluator_salt
        + submitter_salt
        + bytes.fromhex(source_revision)
    ).digest(4096)
    selected: list[int] = []
    for offset in range(0, len(material), 4):
        candidate = int.from_bytes(material[offset : offset + 4], "little")
        if candidate in excluded or candidate in selected:
            continue
        selected.append(candidate)
        if len(selected) == count:
            return selected
    raise ChallengeError("fresh seed derivation exhausted its fixed draw buffer")


def load_challenge(path: Path = DEFAULT_CHALLENGE) -> dict[str, Any]:
    challenge = _read_json(path)
    _require(challenge.get("format") == CHALLENGE_FORMAT, "unsupported challenge format")
    _require(challenge.get("version") == "0.1", "unsupported challenge version")
    memory = challenge.get("memory_policy")
    _require(isinstance(memory, dict), "challenge memory_policy must be an object")
    _require(memory.get("total_attack_budget_bytes") == 131072, "unexpected attack budget")
    counters = challenge.get("operation_policy", {}).get("screening_counter_fields")
    _require(isinstance(counters, list) and len(counters) == len(set(counters)), "invalid counter fields")
    return challenge


def validate_submission(
    submission: dict[str, Any],
    challenge: dict[str, Any],
    *,
    allow_template: bool = False,
) -> dict[str, Any]:
    _require(submission.get("format") == SUBMISSION_FORMAT, "unsupported submission format")
    _require(
        submission.get("challenge_version") == challenge["version"],
        "submission challenge_version does not match",
    )
    status = submission.get("status")
    if allow_template and status == "TEMPLATE_NOT_A_SUBMISSION":
        return {"valid_template": True, "valid_submission": False}
    _require(status == "SUBMISSION", "submission status must be SUBMISSION")
    submission_id = submission.get("submission_id")
    _require(isinstance(submission_id, str) and ID_RE.fullmatch(submission_id), "invalid submission_id")
    authors = submission.get("authors")
    _require(
        isinstance(authors, list)
        and authors
        and all(isinstance(author, str) and author.strip() for author in authors),
        "authors must be a nonempty string list",
    )
    for field in ("contact", "source_url", "license", "strategy_summary", "relationship_to_prior_work"):
        _require(isinstance(submission.get(field), str) and submission[field].strip(), f"{field} is required")
    _require(
        isinstance(submission.get("source_revision"), str)
        and HEX40_RE.fullmatch(submission["source_revision"]),
        "source_revision must be 40 lowercase hexadecimal characters",
    )
    tracks = submission.get("tracks")
    known_tracks = set(challenge["tracks"])
    _require(
        isinstance(tracks, list)
        and tracks
        and len(tracks) == len(set(tracks))
        and set(tracks) <= known_tracks,
        "tracks must be a unique nonempty subset of challenge tracks",
    )
    entrypoint = submission.get("entrypoint_argv")
    _require(
        isinstance(entrypoint, list)
        and entrypoint
        and all(isinstance(part, str) and part for part in entrypoint),
        "entrypoint_argv must be a nonempty argv string list",
    )
    _require("{request}" in entrypoint and "{output}" in entrypoint, "entrypoint_argv needs request and output placeholders")

    memory = submission.get("memory_model")
    _require(isinstance(memory, dict), "memory_model must be an object")
    declared = _nonnegative_integer(memory.get("declared_peak_attack_bytes"), "declared_peak_attack_bytes")
    budget = challenge["memory_policy"]["total_attack_budget_bytes"]
    _require(0 < declared <= budget, "declared peak attack memory exceeds the challenge budget")
    _require(memory.get("external_storage_bytes") == 0, "external storage must be zero")
    _require(memory.get("dynamic_allocation_after_start") is False, "dynamic allocation after start is forbidden")
    _require(_nonnegative_integer(memory.get("worker_threads"), "worker_threads") >= 1, "worker_threads must be positive")
    allocations = memory.get("allocations")
    _require(isinstance(allocations, list) and allocations, "allocations must be nonempty")
    allocation_names: set[str] = set()
    allocation_total = 0
    for index, allocation in enumerate(allocations):
        _require(isinstance(allocation, dict), f"allocation {index} must be an object")
        name = allocation.get("name")
        _require(isinstance(name, str) and name and name not in allocation_names, f"invalid allocation name at {index}")
        allocation_names.add(name)
        allocation_total += _nonnegative_integer(allocation.get("bytes"), f"allocation {name} bytes")
        _require(isinstance(allocation.get("purpose"), str) and allocation["purpose"].strip(), f"allocation {name} needs purpose")
    _require(allocation_total == declared, "allocation bytes must equal declared_peak_attack_bytes")

    operation = submission.get("operation_model")
    _require(isinstance(operation, dict), "operation_model must be an object")
    required_counters = challenge["operation_policy"]["screening_counter_fields"]
    _require(operation.get("counter_fields") == required_counters, "counter_fields must preserve frozen order")
    _require(
        isinstance(operation.get("other_charged_operations_mapping"), str)
        and operation["other_charged_operations_mapping"].strip(),
        "other charged operation mapping is required",
    )
    build = submission.get("build_argv")
    _require(
        isinstance(build, list)
        and build
        and all(
            isinstance(command, list)
            and command
            and all(isinstance(part, str) and part for part in command)
            for command in build
        ),
        "build_argv must contain nonempty argv lists",
    )
    limitations = submission.get("limitations")
    _require(
        isinstance(limitations, list)
        and limitations
        and all(isinstance(item, str) and item.strip() for item in limitations),
        "limitations must be a nonempty string list",
    )
    _require(
        isinstance(submission.get("submitter_salt_hex"), str)
        and HEX64_RE.fullmatch(submission["submitter_salt_hex"]),
        "submitter_salt_hex must be 32 bytes of lowercase hexadecimal",
    )
    return {
        "valid_template": False,
        "valid_submission": True,
        "submission_id": submission_id,
        "declared_peak_attack_bytes": declared,
        "tracks": tracks,
    }


def build_case_set(
    challenge: dict[str, Any],
    track: str,
    seed_indices: list[int],
    *,
    selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require(seed_indices and len(seed_indices) <= 32, "one to 32 seed indices are required")
    _require(len(seed_indices) == len(set(seed_indices)), "seed indices must be unique")
    if track == "qualification":
        profile_name = "qualification"
        operation_limit = None
        attack_budget = None
    else:
        _require(track in challenge["tracks"], "unsupported challenge track")
        track_policy = challenge["tracks"][track]
        profile_name = track_policy["profile"]
        operation_limit = track_policy["operation_limit"]
        attack_budget = challenge["memory_policy"]["total_attack_budget_bytes"]
    profile = challenge["profiles"][profile_name]
    params = {
        "dataset_bytes": profile["dataset_bytes"],
        "scratchpad_bytes": profile["scratchpad_bytes"],
        "passes": profile["passes"],
    }
    header = challenge["candidate"]["header_utf8"].encode("utf-8")
    nonce = challenge["candidate"]["nonce"]
    canonical_iterations = params["scratchpad_bytes"] // 8 * params["passes"]
    cases = []
    for seed_index in seed_indices:
        seed = seed_for(seed_index)
        case: dict[str, Any] = {
            "case_id": f"{profile_name}-seed-{seed_index}",
            "seed_index": seed_index,
            "seed": seed.hex(),
            "seed_commitment": hashlib.sha3_384(seed).hexdigest(),
            "header": header.hex(),
            "header_digest": hashlib.sha3_384(header).hexdigest(),
            "nonce": nonce,
            "params": params,
            "canonical_iterations": canonical_iterations,
            "operation_limit": operation_limit,
            "attack_budget_bytes": attack_budget,
        }
        if track == "qualification":
            case["expected_result"] = evaluate(
                prepare_epoch(seed, Params(**params)), header, nonce
            ).to_dict()
        cases.append(case)
    document: dict[str, Any] = {
        "format": CASE_SET_FORMAT,
        "challenge_version": challenge["version"],
        "track": track,
        "profile": profile_name,
        "cases": cases,
    }
    if selection is not None:
        document["selection"] = selection
    document["case_set_commitment"] = _commit(document)
    return document


def build_fresh_case_set(
    challenge: dict[str, Any],
    track: str,
    submission: dict[str, Any],
    evaluator_salt: bytes,
) -> dict[str, Any]:
    validate_submission(submission, challenge)
    _require(track in {"screening", "completion"}, "fresh cases require screening or completion track")
    _require(track in submission["tracks"], "submission did not enter the selected track")
    exclusions = challenge["case_policy"]["previously_used_standard_seed_indices"]
    count = challenge["case_policy"]["fresh_case_count"]
    submitter_salt = bytes.fromhex(submission["submitter_salt_hex"])
    selected = derive_fresh_seed_indices(
        evaluator_salt=evaluator_salt,
        submitter_salt=submitter_salt,
        source_revision=submission["source_revision"],
        excluded_indices=exclusions,
        count=count,
    )
    selection = {
        "method": "commit-reveal-shake256-v0",
        "submission_id": submission["submission_id"],
        "evaluator_salt_commitment": evaluator_salt_commitment(evaluator_salt),
        "evaluator_salt_hex": evaluator_salt.hex(),
        "submitter_salt_hex": submission["submitter_salt_hex"],
        "source_revision": submission["source_revision"],
        "excluded_seed_indices": exclusions,
        "fresh_case_count": count,
    }
    return build_case_set(challenge, track, selected, selection=selection)


def validate_case_set(case_set: dict[str, Any], challenge: dict[str, Any]) -> dict[str, Any]:
    _require(case_set.get("format") == CASE_SET_FORMAT, "unsupported case-set format")
    commitment = case_set.get("case_set_commitment")
    _require(isinstance(commitment, str) and HEX96_RE.fullmatch(commitment), "invalid case-set commitment")
    unsigned = dict(case_set)
    unsigned.pop("case_set_commitment", None)
    _require(_commit(unsigned) == commitment, "case-set commitment mismatch")
    cases = case_set.get("cases")
    _require(isinstance(cases, list) and cases, "case set must contain cases")
    _require(all(isinstance(case, dict) for case in cases), "every case must be an object")
    selection = case_set.get("selection")
    if selection is not None:
        _require(isinstance(selection, dict), "case selection must be an object")
        _require(case_set.get("track") in {"screening", "completion"}, "qualification cases cannot use fresh selection")
        _require(selection.get("method") == "commit-reveal-shake256-v0", "unsupported fresh selection method")
        _require(
            isinstance(selection.get("submission_id"), str)
            and ID_RE.fullmatch(selection["submission_id"]),
            "invalid selection submission_id",
        )
        _require(
            selection.get("excluded_seed_indices")
            == challenge["case_policy"]["previously_used_standard_seed_indices"],
            "fresh selection exclusions do not match the challenge",
        )
        _require(
            selection.get("fresh_case_count") == challenge["case_policy"]["fresh_case_count"],
            "fresh case count does not match the challenge",
        )
        evaluator_hex = selection.get("evaluator_salt_hex")
        submitter_hex = selection.get("submitter_salt_hex")
        _require(isinstance(evaluator_hex, str) and HEX64_RE.fullmatch(evaluator_hex), "invalid evaluator salt")
        _require(isinstance(submitter_hex, str) and HEX64_RE.fullmatch(submitter_hex), "invalid submitter salt")
        _require(
            selection.get("evaluator_salt_commitment")
            == evaluator_salt_commitment(bytes.fromhex(evaluator_hex)),
            "evaluator salt commitment mismatch",
        )
        expected_indices = derive_fresh_seed_indices(
            evaluator_salt=bytes.fromhex(evaluator_hex),
            submitter_salt=bytes.fromhex(submitter_hex),
            source_revision=selection.get("source_revision"),
            excluded_indices=selection.get("excluded_seed_indices"),
            count=selection.get("fresh_case_count"),
        )
        _require(
            expected_indices == [case.get("seed_index") for case in cases],
            "fresh seed selection mismatch",
        )
    rebuilt = build_case_set(
        challenge,
        case_set.get("track"),
        [case.get("seed_index") for case in cases],
        selection=selection,
    )
    _require(rebuilt == case_set, "case set does not match deterministic challenge construction")
    return {"valid_case_set": True, "track": case_set["track"], "case_count": len(cases), "case_set_commitment": commitment}


def _validate_execution_result(result: object, label: str) -> dict[str, Any]:
    _require(isinstance(result, dict) and set(result) == RESULT_KEYS, f"{label} has invalid execution_result fields")
    for field in ("digest", "schedule_digest", "dataset_digest", "memory_commitment"):
        _require(isinstance(result[field], str) and HEX96_RE.fullmatch(result[field]), f"{label} {field} must be 48-byte hex")
    registers = result["registers"]
    _require(
        isinstance(registers, list)
        and len(registers) == 8
        and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{16}", value) for value in registers),
        f"{label} registers must be eight 64-bit lowercase hex values",
    )
    return result


def verify_results(
    results: dict[str, Any],
    submission: dict[str, Any],
    case_set: dict[str, Any],
    challenge: dict[str, Any],
) -> dict[str, Any]:
    submission_summary = validate_submission(submission, challenge)
    case_summary = validate_case_set(case_set, challenge)
    _require(results.get("format") == RESULTS_FORMAT, "unsupported results format")
    _require(results.get("challenge_version") == challenge["version"], "results challenge version mismatch")
    _require(results.get("submission_id") == submission["submission_id"], "results submission_id mismatch")
    _require(results.get("source_revision") == submission["source_revision"], "results source revision mismatch")
    _require(results.get("track") == case_set["track"], "results track mismatch")
    if case_set["track"] != "qualification":
        _require(case_set["track"] in submission["tracks"], "submission did not enter this track")
    _require(results.get("case_set_commitment") == case_set["case_set_commitment"], "results case-set commitment mismatch")
    selection = case_set.get("selection")
    if case_set["track"] != "qualification":
        _require(isinstance(selection, dict), "screening and completion results require fresh commit-reveal cases")
        _require(selection.get("submission_id") == submission["submission_id"], "case selection submission_id mismatch")
        _require(selection.get("source_revision") == submission["source_revision"], "case selection source revision mismatch")
        _require(selection.get("submitter_salt_hex") == submission["submitter_salt_hex"], "case selection submitter salt mismatch")
    result_cases = results.get("cases")
    _require(isinstance(result_cases, list), "results cases must be a list")
    _require(len(result_cases) == len(case_set["cases"]), "results must contain every case exactly once")
    by_id = {case.get("case_id"): case for case in result_cases if isinstance(case, dict)}
    _require(len(by_id) == len(result_cases), "result case ids must be unique strings")

    counter_fields = challenge["operation_policy"]["screening_counter_fields"]
    declared_peak = submission_summary["declared_peak_attack_bytes"]
    complete_proofs = 0
    maximum_prefix = 0
    for request in case_set["cases"]:
        case_id = request["case_id"]
        _require(case_id in by_id, f"missing result for {case_id}")
        result_case = by_id[case_id]
        status = result_case.get("status")
        _require(status in {"COMPLETE", "EXHAUSTED", "REFUSED", "INVALID"}, f"invalid status for {case_id}")
        completed = _nonnegative_integer(result_case.get("completed_iterations"), f"{case_id} completed_iterations")
        _require(completed <= request["canonical_iterations"], f"{case_id} completed too many iterations")
        maximum_prefix = max(maximum_prefix, completed)
        _require(result_case.get("external_storage_bytes") == 0, f"{case_id} uses external storage")
        accounted = _nonnegative_integer(result_case.get("accounted_peak_attack_bytes"), f"{case_id} accounted memory")
        if case_set["track"] != "qualification":
            _require(0 < accounted <= declared_peak, f"{case_id} exceeds declared attack memory")
        counts = result_case.get("operation_counts")
        _require(
            isinstance(counts, dict) and set(counts) == set(counter_fields),
            f"{case_id} operation counter fields mismatch",
        )
        charged = sum(_nonnegative_integer(counts[field], f"{case_id} {field}") for field in counter_fields)
        _require(result_case.get("total_operations") == charged, f"{case_id} total operation invariant failed")
        limit = request["operation_limit"]
        if limit is not None:
            _require(charged <= limit, f"{case_id} exceeds operation limit")
            if status == "EXHAUSTED":
                _require(charged == limit, f"{case_id} exhausted status must consume the operation limit")
        transcript = result_case.get("transcript_commitment")
        _require(isinstance(transcript, str) and HEX96_RE.fullmatch(transcript), f"{case_id} transcript must be 48-byte hex")

        execution_result = result_case.get("execution_result")
        if status == "COMPLETE":
            _require(completed == request["canonical_iterations"], f"{case_id} complete status has partial prefix")
            claimed = _validate_execution_result(execution_result, case_id)
            params = Params(**request["params"])
            expected = evaluate(
                prepare_epoch(bytes.fromhex(request["seed"]), params),
                bytes.fromhex(request["header"]),
                request["nonce"],
            ).to_dict()
            _require(claimed == expected, f"{case_id} canonical proof mismatch")
            complete_proofs += 1
        else:
            _require(execution_result is None, f"{case_id} non-complete status must not emit a proof")
    return {
        "valid_results": True,
        "submission_id": submission["submission_id"],
        "track": case_summary["track"],
        "case_count": case_summary["case_count"],
        "complete_proofs": complete_proofs,
        "maximum_completed_iterations": maximum_prefix,
        "memory_claim_audited": False,
        "warning": "Artifact validation and exact-output checking do not prove physical-memory eligibility or independent strategy development.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--challenge", type=Path, default=DEFAULT_CHALLENGE)
    subparsers = parser.add_subparsers(dest="command", required=True)

    submission_parser = subparsers.add_parser("validate-submission")
    submission_parser.add_argument("--submission", required=True, type=Path)
    submission_parser.add_argument("--allow-template", action="store_true")

    cases_parser = subparsers.add_parser("make-cases")
    cases_parser.add_argument("--track", choices=("qualification",), required=True)
    cases_parser.add_argument("--seed-index", type=int, action="append", required=True)
    cases_parser.add_argument("--output", type=Path)

    fresh_parser = subparsers.add_parser("make-fresh-cases")
    fresh_parser.add_argument("--track", choices=("screening", "completion"), required=True)
    fresh_parser.add_argument("--submission", required=True, type=Path)
    fresh_parser.add_argument("--evaluator-salt-hex", required=True)
    fresh_parser.add_argument("--output", type=Path)

    validate_cases_parser = subparsers.add_parser("validate-cases")
    validate_cases_parser.add_argument("--cases", required=True, type=Path)

    results_parser = subparsers.add_parser("verify-results")
    results_parser.add_argument("--submission", required=True, type=Path)
    results_parser.add_argument("--cases", required=True, type=Path)
    results_parser.add_argument("--results", required=True, type=Path)

    args = parser.parse_args()
    try:
        challenge = load_challenge(args.challenge)
        if args.command == "validate-submission":
            output = validate_submission(_read_json(args.submission), challenge, allow_template=args.allow_template)
        elif args.command == "make-cases":
            output = build_case_set(challenge, args.track, args.seed_index)
            _write_json(args.output, output)
            return 0
        elif args.command == "make-fresh-cases":
            _require(HEX64_RE.fullmatch(args.evaluator_salt_hex) is not None, "evaluator salt must be 32-byte lowercase hex")
            output = build_fresh_case_set(
                challenge,
                args.track,
                _read_json(args.submission),
                bytes.fromhex(args.evaluator_salt_hex),
            )
            _write_json(args.output, output)
            return 0
        elif args.command == "validate-cases":
            output = validate_case_set(_read_json(args.cases), challenge)
        else:
            output = verify_results(
                _read_json(args.results),
                _read_json(args.submission),
                _read_json(args.cases),
                challenge,
            )
    except ChallengeError as error:
        parser.error(str(error))
    _write_json(None, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
