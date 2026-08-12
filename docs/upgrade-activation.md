# Soveroot Upgrade and Activation Specification

Version: 0.1 working draft

Status: Pre-mainnet governance constraint

## 1. Purpose

This document defines how changes to Soveroot consensus may be proposed, tested, deployed, activated, rejected, and superseded. Its purpose is to prevent developers, miners, pools, custodians, exchanges, foundations, or node-count measurements from becoming a privileged legislature.

Consensus remains whatever rules an operator deliberately chooses to validate. This process cannot manufacture agreement. It is a conservative procedure for detecting agreement before activation and avoiding preventable chain splits.

## 2. Non-goals

This process does not:

- identify a single "community" preference;
- turn hash rate, coins, node counts, social-media polls, or developer signatures into binding votes;
- guarantee that a contentious fork will retain value or sufficient proof of work;
- provide an emergency administrator, rollback key, or checkpoint authority; or
- allow a software release to silently change consensus.

## 3. Change classes

Every release note MUST classify each change as one of:

1. **Consensus change:** changes which blocks or transactions are valid.
2. **Peer protocol change:** changes network interoperability without changing ledger validity.
3. **Node policy change:** changes local relay, mempool, mining-template, fee, or resource preferences.
4. **Standard-profile change:** changes behavior required for official wallet, node, or miner labeling.
5. **Implementation change:** changes performance or internals without intentionally changing observable rules.

A policy disagreement MUST NOT be described as a consensus mandate. Moving behavior from policy into consensus requires the complete consensus-change process.

## 4. Proposal artifacts

A consensus proposal MUST include:

- a stable identifier and exact normative specification;
- motivation, alternatives, explicit non-goals, and reversibility analysis;
- byte-level serialization and domain separation;
- valid, invalid, boundary, and cross-version test vectors;
- resource and denial-of-service bounds;
- effects on existing outputs, presigned transactions, wallets, miners, and recovery paths;
- reorganization, partition, and partial-deployment analysis;
- activation and expiry parameters;
- a threat-model amendment;
- at least two independent interoperable implementations before mainnet activation; and
- reproducible builds for deployment software.

Unresolved security assumptions MUST be labeled as blockers rather than hidden in implementation notes.

## 5. Lifecycle

A proposal moves through the following public states:

1. **Draft:** discussion and specification changes are expected.
2. **Candidate:** normative text is frozen for testing; incompatible edits require a new candidate version.
3. **Testnet:** multiple implementations and adversarial tests exercise the candidate.
4. **Deployment proposed:** exact mainnet parameters are published in a separate deployment document.
5. **Ready:** the deployment has passed all mandatory gates and software is broadly available.
6. **Locked in:** objective on-chain readiness conditions have been met.
7. **Active:** upgraded rules are enforced.
8. **Expired, withdrawn, or superseded:** the proposal did not activate or was replaced before activation.

"Candidate" and "Ready" are technical labels, not declarations of political legitimacy.

## 6. Mandatory review gates

Before a mainnet deployment is proposed:

- the candidate specification SHOULD remain stable for at least twelve months;
- public testnet operation SHOULD cover at least two release cycles and six months;
- two independently maintained validator implementations MUST agree on the conformance corpus;
- the candidate MUST NOT have a known bug permitting inflation, unauthorized spending, deterministic divergence, or unbounded validation cost;
- low-cost reference hardware MUST remain able to validate worst-case blocks within the published budget;
- affected wallet and mining software MUST have migration guidance; and
- credible objections and residual risks MUST be summarized without requiring consensus among reviewers.

Shortening a SHOULD requires a written rationale in the deployment document. Requirements stated as MUST cannot be waived by a release manager or maintainer vote.

## 7. Readiness signals are not votes

Miners MAY signal deployment readiness in block headers. Wallets, exchanges, merchants, custodians, and node operators MAY publish signed readiness statements. Implementations MAY report opt-in telemetry.

These observations:

- are advisory and Sybilable;
- MUST be reported by category rather than combined into a fake universal percentage;
- MUST NOT grant authority to a pool or custodian;
- MUST NOT be inferred from unreachable nodes or user-agent strings; and
- MUST NOT override locally configured validation rules.

Pool signaling measures a coordinator's current block production, not the preferences of every machine contributing work to that pool.

## 8. Default deployment mechanism

The default mainnet mechanism for a backward-compatible consensus restriction is a miner-readiness window with all of the following properties:

- a threshold of at least 90% of blocks in each of two consecutive difficulty periods;
- activation no sooner than one full difficulty period after lock-in;
- an expiry height at which an unmet deployment returns to the pre-deployment rules;
- at least twelve months between the first widely available release and the earliest activation height; and
- no mandatory signaling or automatic lock-in at expiry.

The threshold measures operational readiness. Miners do not acquire authority to define the rules, and failure to reach the threshold does not prove rejection. It means this deployment attempt expires safely.

Exact period lengths and heights are chain-parameter decisions and MUST be fixed in the deployment document.

## 9. No bundled forced activation

The reference client MUST NOT bundle a hidden or automatic transition from an expired readiness deployment into forced activation.

If some users later want a user-activated fork, it requires a new proposal, a new risk analysis, separately named software, and a clearly disclosed fork height. Its proponents MUST demonstrate a credible path to:

- sufficient sustained proof of work;
- exchange and merchant continuity;
- wallet replay safety when applicable;
- difficulty and liveness under a minority-hash scenario; and
- unambiguous user consent.

Running validating nodes alone does not provide chain liveness. A forced fork without sufficient work can stall even when its nodes faithfully reject the other chain.

## 10. Incompatible changes

A change that makes previously invalid blocks valid requires explicit network migration and replay analysis. It MUST NOT use the ordinary restrictive-change deployment path.

Mainnet hard forks are presumed rejected unless they repair a demonstrated existential flaw that cannot be repaired compatibly or form part of a deliberately launched successor network. Convenience, throughput, developer preference, or miner preference is insufficient.

## 11. Emergency handling

Soveroot has no emergency consensus key. For an implementation vulnerability, maintainers MAY publish a patched release, disable vulnerable optional behavior, and coordinate responsible disclosure.

For a consensus vulnerability, nodes may need rapid social coordination, but no maintainer action can make a new rule legitimate by itself. Any temporary restriction MUST be narrowly specified, auditable, time-bounded where technically safe, and followed by the full proposal process. Permanent checkpoints and developer-selected chain tips remain prohibited.

## 12. Release and user-interface requirements

Software that contains a pending consensus deployment MUST display:

- proposal identifier and version;
- earliest activation and expiry;
- current state and observed miner readiness;
- known compatibility and fund-safety risks;
- whether the operator explicitly enabled the deployment; and
- how to return to software enforcing the prior rules before lock-in.

Official update mechanisms MUST NOT install a release containing a newly enabled consensus deployment without explicit operator acknowledgement of that deployment. Until lock-in, maintainers SHOULD provide security fixes for the prior-rule release line whenever technically safe. Consent to an ordinary security update is not consent to new monetary rules.

## 13. Mainnet launch

Genesis rules are adopted by choosing to join a new network, so they do not use an in-chain activation mechanism. Nevertheless, Soveroot mainnet MUST NOT launch until the Phase 5 readiness requirements, fair-launch profile, independent implementations, and conformance tests are satisfied.

After genesis, this specification governs every intentional consensus change.
