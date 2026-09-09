# PoW v1 Challenge Campaign

Status: **PROPOSED CAMPAIGN PROCEDURE; CHALLENGE REMAINS OPEN / NOT ASSESSED**

This document defines how the existing [external attack challenge](pow-v1-external-attack-challenge.md) can be run as a time-bounded public campaign without turning silence into a security claim. The challenge contract, memory ceiling, case derivation, and decision thresholds remain unchanged.

## Frozen challenge pack

Campaign round 1 uses the files listed in [`challenge_pack_manifest_v0.json`](../contrib/pow_research_v1/challenge_pack_manifest_v0.json). Before opening the round, a maintainer SHALL:

1. run the complete PoW research unit-test suite;
2. run `python3 -m contrib.pow_research_v1.challenge_pack verify`;
3. create a signed or publicly attributable Git tag for the exact release commit;
4. publish the tag, commit, archive digest, manifest digest, and test log; and
5. state the opening and closing timestamps in UTC.

The manifest hashes the normative specification, machine-readable contract, reference implementations, qualification cases, templates, evaluator procedure, and campaign policies. The manifest does not hash itself. Any change to a listed file after the release tag starts a new pack version and a new campaign round.

## Predeclared round-one closure criteria

The public participation window SHOULD remain open for at least 90 days. At its close, the campaign report SHALL classify the round using one of these outcomes:

- **reviewable evidence obtained:** at least two conflict-disclosed evaluators reproduced the qualification artifacts, at least three qualified attack implementations were reviewed, and at least one public FPGA or ASIC cost review was completed;
- **attack evidence obtained, participation target missed:** useful attack or review artifacts exist, but the minimum breadth above was not reached;
- **insufficient independent participation:** the minimum breadth was not reached and no qualifying independent attack was evaluated; or
- **contract defect:** ambiguity, incompatible implementations, unsafe procedure, or an accounting defect requires a new challenge version.

None of these outcomes passes the PoW time-memory gate automatically. In particular, an expired window with no successful attack is not evidence of memory hardness.

## Required public records

The campaign index SHALL retain:

- release tag, commit, archive digest, manifest, and verification log;
- opening and closing timestamps;
- evaluator interests and conflict disclosures;
- every submitted source revision and manifest;
- evaluator commitments and revealed salts;
- assigned cases, raw outputs, build logs, and eligibility decisions;
- partial, failed, invalid, refused, and unfavorable rows;
- hardware-review reports and declared assumptions;
- AI-use disclosures; and
- the final campaign classification and unresolved evidence gaps.

Counts in `independent_research_call_v0.json` change only when the corresponding public artifacts exist.

## Independence rule

AI-assisted work is welcome under the [AI-assisted attack policy](pow-v1-ai-assisted-attack-policy.md), but a model is not an independent evaluator, accountable reviewer, or hardware expert. A human author remains responsible for source, accounting, claims, and reproducibility. Multiple agents using the same model, prompts, repository context, or operator do not constitute multiple independent attacks.

## Hardware-review path

Hardware reviewers use the PoW v1 hardware-review issue template and publish a reproducible report covering at minimum SRAM area, memory bandwidth, parallel lanes, nonce-level reuse, FPGA mapping, ASIC efficiency, and the likely CPU/GPU/FPGA/ASIC efficiency ratios. Estimates must identify process node, memory technology, toolchain or model, assumptions, uncertainty, and conflicts.

A hardware review may identify a fatal economic or architectural weakness even when no half-memory software attack completes. Conversely, a favorable paper model cannot establish production decentralization.
