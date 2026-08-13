# Soveroot Decision and Research Ledger

Status: **WORKING DESIGN; NO PRODUCTION NETWORK; NO PROOF-OF-WORK GATE PASSED**

Evidence cutoff: 2026-08-12, source revision `584cc5f8b94534827f88b8fa7d689189fa25d2c0`

This is the project-level index for decisions made, evidence collected, claims rejected, and work still required. Detailed specifications remain authoritative within their stated scope. This ledger exists so that a reader does not need private conversations to understand the project.

## Purpose and boundary

Soveroot is intended as sovereign, Bitcoin-like money for people, businesses, devices, and autonomous software. It is not an "AI currency." AI agents receive no special consensus role, identity, issuance, governance power, or access to owner funds.

The implementation is derived from a pinned Bitcoin Core codebase, with selected Bitcoin Knots changes reviewed and ported separately. It is a new chain with its own genesis and network identity, not a fork of Bitcoin's live chain, balances, or social consensus.

No document or benchmark in this repository establishes production safety, anonymity, quantum proofness, fair mining, or mainnet readiness.

## Decision register

| Question | Current decision | Reason and limit | Authority |
| --- | --- | --- | --- |
| Who is the protocol for? | People and software agents participate under identical monetary rules. | AI may propose payments but has no privileged protocol role or master signing authority. | [Protocol sections 3.3 and 14](protocol-specification.md#33-ai-exclusion-from-consensus) |
| Bitcoin ancestry | Fork pinned Bitcoin Core code; selectively port reviewed Knots patches; launch a new chain. | Preserves mature validation engineering without inheriting Bitcoin balances or confusing the networks. | [Implementation lineage](protocol-specification.md#35-implementation-lineage-and-network-isolation) |
| Miner versus node authority | Miners order valid transactions and extend a valid chain; every node independently enforces consensus. Miner signaling is telemetry, not a binding vote. | Hash power cannot make an invalid block valid. Economic adoption still matters during incompatible forks, so software cannot eliminate social coordination risk. | [Upgrade lifecycle](upgrade-activation.md#7-readiness-signals-are-not-votes) |
| Pool-size cap | Do not impose a consensus cap such as 10% per pool. | A pool can split identities, miners can hide affiliations, and nodes cannot objectively attribute hashes. Such a cap would reward Sybil behavior or require a centralized identity oracle. | [Mining profile](protocol-specification.md#111-no-pool-identity-cap) |
| Pool concentration controls | Require the standard mining profile to support miner-created templates, encrypted authenticated Stratum V2-style transport, direct block publication, noncustodial payout, coordinator switching, and fallback. Legacy Stratum V1 is outside the official profile. | These controls reduce template and custody power but cannot guarantee a hash-rate distribution. Consensus only enforces facts visible in blocks. | [Mining profile](protocol-specification.md#112-independent-block-construction) |
| Six-month PoW changes | Reject governance-selected periodic algorithm replacement. Use one deterministic, versioned algorithm family and vary its workload from chain data. | Scheduled replacements favor implementers with advance hardware knowledge, add recurring consensus emergencies, and can centralize development. A broken algorithm still needs the conservative upgrade process. | [PoW research section 2](pow-vm-research.md#2-fixed-algorithm-variable-program) |
| Mining decentralization claim | Treat memory-oriented, variable-workload PoW as a research hypothesis, not a guarantee. | Capital, energy, fabrication, firmware, geography, pools, and economies of scale remain concentration forces even if ASIC advantage is reduced. | [Evaluation gates](pow-evaluation-gates.md) |
| "Quantum-proof SHA" | Do not use that phrase. SHA3-384 is the candidate general hash primitive; the PoW and signatures require separate quantum analyses. | Grover-style search changes the security margin of hashes; it does not make SHA intrinsically quantum-proof. Signature theft is addressed through post-quantum authorization and cryptographic agility. | [Cryptographic suite](protocol-specification.md#5-cryptographic-suite) |
| Transaction authorization | Candidate ML-DSA-65 from genesis, with independent SLH-DSA recovery or high-assurance paths; classical signatures are never sufficient alone. | These remain candidates until performance, denial-of-service, implementation, and external-review blockers close. | [Transaction signatures](protocol-specification.md#52-transaction-signatures) |
| Wallet IP privacy | Official wallets never originate a transaction over direct clearnet and fail closed unless an approved local anonymity route is operating. Tor is first; reviewed I2P or mixnet routes may be supported. | This is an enforceable software profile, not consensus. It cannot prove that third-party wallets used Tor or guarantee that a global observer cannot correlate traffic. | [Wallet networking profile](protocol-specification.md#13-fail-closed-wallet-networking-profile) |
| Ledger pseudonymity | Avoid address reuse, use recipient-specific identifiers, support collaborative transactions and selective disclosure, and research post-quantum shielded UTXOs. | Network privacy does not erase transaction-graph leakage. Shielded transfers remain research-only until supply auditability and node-resource requirements are met. | [Privacy architecture](protocol-specification.md#12-privacy-architecture) |
| Monetary privilege | No premine, founder allocation, protocol treasury, development tax, validator registry, privileged pool, or administrative key. | A fair launch reduces explicit privilege but cannot prevent later wealth, custody, or ETF concentration. | [Monetary policy](protocol-specification.md#8-monetary-policy-and-launch) |

"Official profile" means required behavior for software distributed under the Soveroot wallet or miner label. It is not described as consensus when a validating node cannot observe and verify it.

## What the PoW evidence says

The v0 candidate was dominated by initialization and finalization, so the workload was redesigned as v1. The v1 software screens advanced the candidate to adversarial testing, not to consensus integration.

| Milestone | Preserved result | What it establishes | What it does not establish |
| --- | --- | --- | --- |
| v1 CPU screen ([PR #16](https://github.com/emilydarryl/decentralized-currency-protocol/pull/16)) | Eight-seed shared-runner screen met the predeclared workload-balance advance bounds. | The candidate was worth attacking further. | Controlled-host performance, hardware equality, or any mandatory gate pass. |
| Half-memory spill ([PR #18](https://github.com/emilydarryl/decentralized-currency-protocol/pull/18)) | Exact outputs; 3.91% of normal throughput. | A simple external-store adversary can reproduce proofs and is slow on this host. | The half-memory gate: external storage, OS caching, and resident memory were not bounded. |
| Dependency and batch screen ([PR #20](https://github.com/emilydarryl/decentralized-currency-protocol/pull/20)) | Median maximum live set 56.96%; optimistic half-capacity LRU miss share 45.81%; evaluation-only batch advantage 1.04x and inclusive advantage 12.52x at 4,096 attempts. | Reuse is substantial; epoch setup amortizes strongly; exact bounded recomputation is necessary. | Exact proofs after cache misses or facility advantage after hardware occupancy. |
| No-spill recomputation pilot ([PR #22](https://github.com/emilydarryl/decentralized-currency-protocol/pull/22)) | Exact outputs; 0.06% of normal throughput; 8.40 million replay iterations. | A deliberately naive recomputation attack is exact and expensive. | The half-memory gate: its simultaneous retained and replay arrays used 150% peak scratch allocation. |
| Metadata-aware cache bound ([PR #24](https://github.com/emilydarryl/decentralized-currency-protocol/pull/24)) | At the 131,072-byte half-scratch budget, a 16-byte-entry LRU missed 72.15%; an unattainable offline oracle missed 22.36%. With conservative 24-byte entries, LRU missed 81.32% and the oracle missed 33.64%. | Even an optimistic cache must confront many missing values; metadata materially reduces capacity. | The work needed to regenerate a miss or a valid half-memory proof. |

Raw matrices, report hashes, runner identifiers, and limitations are in the [research-results index](research-results/README.md). Unfavorable results are retained rather than discarded.

## Mandatory PoW gate dashboard

The machine-readable state is [`contrib/pow_research/research_status_v0.json`](../contrib/pow_research/research_status_v0.json). `OPEN` means the predeclared minimum evidence is incomplete; it does not mean pass or failure.

| Gate | State | Evidence gap |
| --- | --- | --- |
| Determinism | **OPEN** | Fewer than one million vectors and fewer than three CPU architectures. |
| Seed variance | **OPEN** | Eight shared-runner seeds, not 1,024 unbiased seeds per device. |
| Verifier budget | **OPEN** | No complete controlled measurements on three declared low-cost systems. |
| Time-memory tradeoff | **OPEN** | No exact attack whose total measured attack memory stays within half the declared scratch memory; second independent model also absent. |
| Facility amortization | **OPEN** | Batches through 4,096 measured, but ordinary hardware occupancy and controlled-host effects are unmeasured. |
| GPU over CPU | **OPEN** | No optimized two-ecosystem GPU comparison across three CPU classes. |
| FPGA over GPU | **OPEN** | No reviewed FPGA implementation or estimate. |
| ASIC over GPU | **OPEN** | No two independently reviewed ASIC cost models. |
| Quantum concentration | **OPEN** | No two independent reversible-circuit estimates or approved economic first-mover model. |
| Template autonomy | **OPEN** | Specified behavior, but no two interoperable mining implementations. |

Every gate must pass independently. A favorable cache statistic, slow naive attack, or shared-runner benchmark cannot substitute for missing evidence.

## Immediate next experiment

Stage A of the [v1 bounded-pebbling plan](pow-v1-bounded-pebbling-plan.md) has an exact, independently implemented [versioned scratch-dependency graph](pow-v1-versioned-graph.md), fixed smoke and standard commitments, and packed and conservative byte models. The graph is an offline diagnostic approximately 61 times larger than the standard half-scratch budget even under its optimistic layout, so it cannot be retained by an eligible attacker.

The first Stage B result now supplies an [optimistic offline cut-set lower bound](pow-v1-pebbling-lower-bound.md). At the strongest standard-profile cuts, the median lower bound is 6,984 additional producer executions for compact 16-byte entries and 9,715 for conservative 24-byte entries. This is deliberately weaker than a real attack: it grants perfect future knowledge, zero-byte control state, and free dependency and machine-state reconstruction.

The remaining Stage B [offline schedule search](pow-v1-offline-pebbling-schedule.md) is now complete. Across eight standard seeds, its compact layout needs a median 3,424,646 abstract producer replays and a 13,989,059-byte direct action stream; its conservative layout needs 6,419,925 replays and 26,101,215 bytes. These are results for one optimistic graph-only policy, not lower bounds, executable proofs, or claims that no compressed schedule exists.

Stage C now has a fail-closed online probe, first and repeated reconstruction results, packed and paged layouts, and an [indexed-gap pilot](pow-v1-indexed-gap-reconstruction.md). The indexed layout raises standard seed-zero page utilization from 59.2% to 90.8% and extends the exact prefix from iteration 3,599 to 5,759. It performs 5.13 million attempted replay iterations and still refuses without a proof, showing that value-layout optimization alone is insufficient. The immediate milestone is a byte-accounted time-checkpoint or hierarchical replay construction that reduces genesis replay while retaining exact state. A later exact attacker must account for retained values, identities, versions, checkpoints, register state, work queues, stack, allocator overhead, and peak resident memory within the ceiling.

An offline trace, graph, planner, or oracle may guide the research, but results obtained with future knowledge or unbounded planning memory are lower-bound diagnostics, not executable mining attacks. The time-memory gate stays open until an independently reviewed implementation and controlled physical-host measurements satisfy the frozen policy.

## Change discipline

- Consensus candidates, official software profiles, research hypotheses, and rejected claims must remain labeled separately.
- New evidence must include the source revision, method version, raw data, environment, limitations, and integrity hash.
- Thresholds may not be changed after seeing results without a new policy version and complete retesting.
- A passed research gate would not itself activate consensus. Activation follows the separately documented review and adoption process.
- This ledger must be updated whenever a decision changes, an experiment closes or reopens a gate, or a new mainnet blocker is discovered.
