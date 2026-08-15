---
name: PoW v1 external attack submission
about: Freeze and submit an independently reviewable bounded-memory attack
title: "PoW v1 attack submission: [submission-id]"
labels: research
assignees: ""
---

This issue is for the isolated, non-consensus [PoW v1 external attack challenge](https://github.com/emilydarryl/decentralized-currency-protocol/blob/main/docs/pow-v1-external-attack-challenge.md). Do not include credentials, private keys, personal data, or mutable download links.

## Submission identity

- Submission ID:
- Author or pseudonym:
- Public contact or `none`:
- Entered track: `screening`, `completion`, or both

## Frozen source

- Evaluator-salt commitment published before source freeze:
- Public source repository URL:
- Full 40-character source revision:
- Source license:
- Manifest URL pinned to that revision:
- 32-byte submitter salt from the manifest:

## Strategy

Explain the strategy, expected advantage, and how it differs from the repository's checkpoint-ladder and cost-aware frontier attacks.

## Prior relationship

Disclose copied code, shared authorship, prior collaboration, and conceptual dependence on earlier attacks.

## Accounting

- Declared peak mutable per-attempt attack bytes:
- Worker threads:
- External storage bytes (must be zero):
- Operation-counter mapping reviewed: yes/no
- Known limitations:

## Reproduction

- Qualification case-set commitment:
- Qualification result URL:
- Build environment and toolchain:
- Reproducible command source:

## Attestation

- [ ] The source revision, manifest, build instructions, and submitter salt are frozen before fresh cases are assigned.
- [ ] The evaluator published its salt commitment before the source freeze and revealed the matching salt only afterward.
- [ ] All mutable per-attempt attack allocations, stacks, allocator reserves, transcripts, and worker communication are disclosed.
- [ ] The runner does not use spill files, databases, memory-mapped backing, network helpers, hidden workers, or future-aware retained traces.
- [ ] I understand that artifact validation does not prove physical-memory eligibility and that reviewers will run untrusted code only in a disposable, network-disabled environment.
- [ ] I agree that complete, partial, refused, invalid, and unfavorable evaluation rows may be published.
