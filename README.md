# Soveroot

Status: Working draft v0.1

Protocol name: Soveroot

Ticker: Unassigned

Implementation status: Bitcoin Core v31.0 bootstrap; experimental and not safe for monetary use

This directory turns the design discussion into an auditable protocol project. The objective is universal Bitcoin-like money for people, businesses, devices, and autonomous software. It prioritizes independent validation, post-quantum cryptography, private-by-default wallet behavior, decentralized block construction, and safe optional delegation.

The public node daemon is `sovrd`, and the public RPC command-line client is `sovr-cli`. The name is a provisional engineering identity pending formal legal clearance.

AI agents are users of the currency, not the protocol's identity, governors, or privileged participants. A person can own, receive, spend, mine, and validate without using any AI system.

The project does not claim that decentralization, anonymity, or quantum safety can be guaranteed forever. It defines testable controls, documents residual risks, and refuses guarantees the protocol cannot verify.

## New to the project?

Start with [Mining Decentralization in Plain English](docs/mining-decentralization-in-plain-english.md). It explains the problem, the proposed hardware and pool safeguards, what the latest experiment actually showed, and what remains unfinished without requiring a mining or programming background.

## Documents

- [research-ledger.md](docs/research-ledger.md) is the project-level source of truth for design decisions, rejected claims, preserved evidence, every open gate, and the immediate research roadmap.
- [mining-decentralization-in-plain-english.md](docs/mining-decentralization-in-plain-english.md) is the nontechnical guide to the mining-decentralization strategy and current research status.
- [protocol-specification.md](docs/protocol-specification.md) defines the proposed architecture, consensus boundary, wallet and mining profiles, optional delegated-payment layer, and normative invariants.
- [threat-model.md](docs/threat-model.md) defines protected assets, adversaries, attack surfaces, mitigations, residual risks, and security acceptance criteria.
- [upgrade-activation.md](docs/upgrade-activation.md) defines a conservative, non-miner-exclusive lifecycle for future consensus changes.
- [pow-vm-research.md](docs/pow-vm-research.md) defines the research envelope, benchmark gates, and rejection criteria for the candidate proof-of-work VM.
- [pow-evaluation-gates.md](docs/pow-evaluation-gates.md) freezes quantitative pass, redesign, and rejection thresholds before benchmark evidence is accepted.
- [pow-v1-workload-objectives.md](docs/pow-v1-workload-objectives.md) records the measured v0 imbalance and freezes the minimum workload-balance signals for a v1 research candidate.
- [pow-v1-candidate-spec.md](docs/pow-v1-candidate-spec.md) defines the isolated byte-level v1 research workload for independent implementations and screening.
- [pow-v1-half-memory-attack.md](docs/pow-v1-half-memory-attack.md) defines the exact-output half-scratchpad spill adversary and the reasons its measurements cannot yet decide the time-memory gate.
- [pow-v1-dependency-batch-screen.md](docs/pow-v1-dependency-batch-screen.md) defines exact dependency tracing and the predeclared 4,096-attempt batch-amortization diagnostic.
- [pow-v1-bounded-pebbling-plan.md](docs/pow-v1-bounded-pebbling-plan.md) predeclares the exact byte-accounted, no-spill attack required to assess the half-memory gate.
- [pow-v1-versioned-graph.md](docs/pow-v1-versioned-graph.md) documents the exact read-from graph, deterministic commitments, and byte models completed for bounded-pebbling Stage A.
- [pow-v1-pebbling-lower-bound.md](docs/pow-v1-pebbling-lower-bound.md) documents the optimistic offline cut-set bound completed for bounded-pebbling Stage B.
- [pow-v1-offline-pebbling-schedule.md](docs/pow-v1-offline-pebbling-schedule.md) documents the concrete graph-only replay schedules, their multi-million-node work, and explicit action-stream sizes that complete the offline portion of Stage B.
- [pow-v1-online-bounded-probe.md](docs/pow-v1-online-bounded-probe.md) documents the first Stage C online execution scaffold, its half-scratch logical admission, and its fail-closed reconstruction boundaries.
- [pow-v1-bounded-first-reconstruction.md](docs/pow-v1-bounded-first-reconstruction.md) documents exact recovery of the first missing value and historical machine state inside the same preallocated half-scratch arena.
- [pow-v1-bounded-repeated-reconstruction.md](docs/pow-v1-bounded-repeated-reconstruction.md) documents repeated exact recovery until the arena's sparse replay workspace fills.
- [pow-v1-packed-checkpoint-reconstruction.md](docs/pow-v1-packed-checkpoint-reconstruction.md) documents a denser bitmap-ranked replay checkpoint and its explicitly charged insertion cost.
- [pow-v1-paged-gap-reconstruction.md](docs/pow-v1-paged-gap-reconstruction.md) documents fixed-size replay pages, bounded movement, and the fragmentation limit they expose.
- [pow-v1-indexed-gap-reconstruction.md](docs/pow-v1-indexed-gap-reconstruction.md) documents indexed page lookup and adjacent-gap rebalancing under the same half-scratch arena.
- [pow-v1-time-checkpoint-screen.md](docs/pow-v1-time-checkpoint-screen.md) tests full, snapshot-delta, and optimistic staged checkpoint representations and motivates recursive value regeneration.
- [pow-v1-recursive-regeneration.md](docs/pow-v1-recursive-regeneration.md) documents the first exact recursive scratch-value recovery inside a byte-accounted logical half-scratch arena.
- [pow-v1-repeated-recursive-regeneration.md](docs/pow-v1-repeated-recursive-regeneration.md) documents persistent memo reuse across successive recursive recoveries and a five-point primary-cache allocation screen.
- [pow-v1-checkpoint-recursive-regeneration.md](docs/pow-v1-checkpoint-recursive-regeneration.md) records why compact machine-state checkpoints made the best screened half-memory attack worse and were rejected.
- [pow-v1-target-checkpoint-regeneration.md](docs/pow-v1-target-checkpoint-regeneration.md) tests checkpoints that bind machine state to one exact historical scratch value, improving a weak allocation without extending the global attack record.
- [pow-v1-dependency-bundle-regeneration.md](docs/pow-v1-dependency-bundle-regeneration.md) packs four exact direct-dependency values with each state checkpoint, advancing the seed-zero attack record slightly while exposing mixed holdout behavior and an incomplete operation bound.
- [pow-v1-iterative-work-stack.md](docs/pow-v1-iterative-work-stack.md) replaces native recursive recovery with twenty packed arena-resident frames and records the complete eight-seed fail-closed holdout.
- [research-results](docs/research-results/README.md) preserves raw measurements and explicitly scoped reports, including unfavorable findings.
- [references.md](docs/references.md) lists the primary standards and research that informed the draft. It is non-normative.
- [upstreams.md](docs/implementation/upstreams.md) pins the inherited Bitcoin Core baseline and Knots patch source.
- [inherited-assumptions.md](docs/implementation/inherited-assumptions.md) tracks every inherited network and consensus dependency that must be replaced or reviewed.
- [branding-v1.md](docs/implementation/branding-v1.md) records the Soveroot public names and the identifiers deliberately deferred to a protocol migration.

## Design priorities

In descending order:

1. Anyone can independently validate the monetary rules on affordable hardware.
2. No founder, foundation, miner, pool, custodian, AI system, or software distributor has privileged consensus authority.
3. Compromise of an AI agent does not imply compromise of its owner's master funds.
4. Ordinary payments use post-quantum authorization from genesis.
5. Official wallets never originate transactions over a direct clearnet route.
6. Pool accounting is separated from transaction selection and block publication.
7. Privacy mechanisms do not conceal changes to supply rules or bypass independent validation.
8. Consensus remains deterministic and contains no model inference, external API, price oracle, or subjective judgment.

## Current decisions

- The reference implementation will be a code fork of a pinned Bitcoin Core release, not a fork of Bitcoin's live chain or UTXO set.
- Bitcoin Knots will be maintained as a separate upstream patch source. Knots changes will be ported selectively with provenance, review, and tests; the project will not continuously merge two moving codebases.
- The new network will have its own genesis block, chain identity, message magic, ports, address namespace, seed infrastructure, data directory, and consensus parameters.
- A non-production `labnet` now provides the first isolated development identity; inherited Bitcoin networks, including Bitcoin regtest, remain non-startable.
- CI starts two labnet nodes and verifies explicit peering, mining, CLI access, and a confirmed test-only wallet transfer.
- The protocol's working name is Soveroot. Public builds produce `sovrd` and `sovr-cli`; inherited CMake target names remain temporarily stable to simplify upstream maintenance.
- Nakamoto-style proof-of-work remains the consensus mechanism.
- Proof-of-work uses a permanent, deterministic algorithm family; human-selected periodic algorithm rotation is rejected.
- The final proof-of-work construction is not yet selected and is a mainnet blocker.
- Miner signaling is readiness telemetry, not a binding vote. Deployments expire safely when readiness thresholds are missed; forced activation requires a separate, explicitly consented fork proposal.
- SHA3-384 with explicit domain separation is the candidate general-purpose hash primitive.
- ML-DSA-65 is the candidate default transaction signature.
- SLH-DSA is an independent backup/recovery signature family, not a required second signature on every ordinary payment.
- ML-KEM-768 is the candidate post-quantum component in hybrid encrypted transports.
- Classical ECDSA or Schnorr authorization is never sufficient by itself.
- The ledger uses a bounded-resource UTXO model.
- There is no premine, founder allocation, protocol treasury, development tax, masternode class, validator registry, or administrative key.
- A small deterministic tail emission is preferred over assuming a permanent fee-only security market. Exact issuance constants remain open.
- Consensus does not attempt to identify mining organizations or impose a percentage cap on pool identities.
- The standard mining stack uses miner-created templates, direct block publication, decentralized share accounting, and noncustodial payouts.
- The official wallet uses an isolated, fail-closed anonymity broadcaster. Consensus does not claim to prove that Tor or another route was used.
- When a person delegates spending to software, AI models may propose structured payment intents but never receive master signing authority.

## Discussed-feature register

The Bitcoin Core foundation does not remove the improvements developed in this design. The intended project scope includes all of the following:

| Area | Project requirement | Status |
| --- | --- | --- |
| Chain ancestry | Fork Bitcoin Core code, but launch an entirely new genesis and network | Committed architecture |
| Knots | Review and port selected Bitcoin Knots policy, privacy, and node-control improvements with provenance | Committed workflow |
| Proof of work | Use a permanent, chain-specific, memory-oriented algorithm family with deterministic workload variation instead of governance-selected six-month swaps | Research blocker |
| Mining concentration | Do not use a Sybil-vulnerable 10% identity cap; reduce coordinator power through miner-created templates, direct publication, easy switching, and decentralized share accounting | Committed profile; share system is a research blocker |
| Mining protocol | Require the standard mining stack to use an encrypted, authenticated Stratum V2 profile with custom job declaration; disable legacy Stratum V1 | Committed standard profile |
| Pool custody | Prefer direct, noncustodial payouts and publicly verifiable shares | Committed goal; construction unresolved |
| Post-quantum ownership | Use ML-DSA-65 authorization from genesis, with an independent SLH-DSA recovery/high-assurance path | Candidate suite; benchmark and review blocker |
| Hashing | Use SHA3-384 with domain separation for general protocol hashing; analyze the separate PoW construction under classical and quantum models | Candidate suite; review blocker |
| Encrypted transport | Use hybrid classical plus ML-KEM-768 transport where the peer protocol requires confidentiality | Candidate suite |
| Wallet network privacy | Official wallets never broadcast directly and fail closed unless an approved local anonymity route is operating | Committed standard profile |
| Privacy-route diversity | Support Tor first, plus I2P or reviewed mixnets, with no DNS or clearnet fallback | Committed standard profile |
| Ledger privacy | Avoid address reuse; support collaborative transactions and selective disclosure; research a transparent post-quantum shielded UTXO mode | Mixed: wallet features committed, shielded mode research-only |
| Monetary launch | No premine, founder allocation, treasury, development tax, privileged pool, or administrative key; use a public fair-launch process | Committed architecture |
| Security budget | Use declining issuance followed by a small deterministic tail subsidy | Preferred policy; constants unresolved |
| Independent validation | Keep full validation affordable, scripts bounded, and consensus free of AI, identity, price, and administrator oracles | Committed architecture |
| People and software | Give people, businesses, devices, and autonomous agents equal access; AI receives no protocol privilege | Committed architecture |
| Delegated payments | Isolate master keys; use finite capability wallets, deterministic policy checks, mandates, replay protection, receipts, and safe failure | Optional application profile |

“Committed profile” means required behavior for software distributed under the project's official wallet or miner label. It is not misrepresented as a consensus rule when nodes cannot objectively verify it.

## Mainnet blockers

The following must be resolved before an implementation can be considered a mainnet candidate:

1. Select and cryptanalyze the proof-of-work construction, including classical and quantum cost models.
2. Set resource limits from reproducible benchmarks on low-cost reference hardware.
3. Specify canonical binary serialization and complete consensus test vectors.
4. Specify the exact difficulty adjustment formula and simulate adversarial timestamp and hash-rate shocks.
5. Finalize issuance constants and analyze the long-term security budget.
6. Benchmark ML-DSA validation, transaction sizes, hardware-wallet operation, and denial-of-service limits.
7. Design and test decentralized share accounting without creating a second centralized consensus system.
8. Produce a post-quantum receiving-address design or define a safe interactive/pre-generated-key profile.
9. Determine whether a practical transparent post-quantum shielded UTXO system exists within the node-resource budget.
10. Build at least two independent consensus implementations and a shared conformance corpus.
11. Pin the initial Bitcoin Core tag and commit, inventory candidate Knots patches, and document every inherited consensus and policy assumption.
12. Demonstrate through automated tests that addresses, signatures, messages, data directories, peer discovery, and chain data cannot be confused with any Bitcoin network.
13. Validate the upgrade and activation process through simulated miner veto, minority-fork, stalled-chain, and partial-economic-adoption scenarios.

## Project rule

Features marked **Research** are not promises and must not silently become consensus requirements. They require a separate specification, security analysis, testnet deployment, and explicit user adoption.
