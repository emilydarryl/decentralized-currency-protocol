# Soveroot Protocol Specification

Version: 0.1 working draft  
Status: Pre-implementation research specification

## 1. Scope

This document specifies a candidate Bitcoin-like monetary network for people, businesses, devices, and autonomous software. Human use does not require an AI intermediary. The network is designed for:

- permissionless ownership and transfer;
- affordable independent validation;
- proof-of-work settlement;
- post-quantum transaction authorization;
- private-by-default official wallet behavior;
- independent miner block construction;
- decentralized reward accounting; and
- optional bounded, auditable delegation to software agents.

It deliberately separates four rule classes:

1. **Consensus rules** determine whether a block or transaction is valid.
2. **Peer protocol rules** determine how nodes exchange valid objects.
3. **Standard profiles** define safe behavior for official wallets, miners, and nodes.
4. **Research features** are uncommitted proposals that are not safe to deploy.

Confusing these classes creates false guarantees. In particular, consensus cannot determine which real-world organization owns mining hardware or which network route originally carried a transaction.

## 2. Normative language

The terms MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL are normative within the rule class where they appear.

An implementation claiming consensus compatibility MUST implement all active consensus rules. A wallet or miner may be consensus-compatible without satisfying the official standard profile, but it MUST NOT claim profile compliance.

### 2.1 Terminology

- **Principal:** A person or organization that owns funds and delegates limited authority.
- **Agent:** Autonomous or semi-autonomous software that proposes actions on a principal's behalf. An agent is not inherently trusted.
- **Policy engine:** Deterministic software that evaluates a canonical proposal against a signed mandate and local policy.
- **Signer:** An isolated component that holds a capability key and signs only after successful policy evaluation.
- **Capability:** Explicitly bounded authority to spend a limited amount under defined conditions.
- **Privacy broadcaster:** An isolated component that submits transactions through a configured anonymity transport and has no signing authority.
- **Miner:** An operator producing proof of work and, under the standard profile, constructing its own candidate blocks.
- **Accounting coordinator:** A service that validates mining shares and calculates payouts without receiving authority to select transactions.
- **Share:** A proof-of-work result meeting an accounting target but not necessarily the base-chain block target.
- **Post-quantum:** Believed to resist known quantum attacks under stated assumptions. It does not mean permanently quantum-proof.
- **Shielded:** A transaction mode that conceals selected ledger relationships while proving validity and conservation of value.

## 3. System principles

### 3.1 Independent validation

A fully validating node MUST determine validity using only deterministic local computation and authenticated chain data. Validation MUST NOT depend on:

- a developer or foundation server;
- miner or token-holder voting;
- an AI model;
- a price feed;
- a legal identity registry;
- a trusted hardware attestation service; or
- a permanent checkpoint after genesis.

### 3.2 No privileged actors

Consensus MUST NOT contain an administrative key, emergency multisignature, protocol treasury, privileged validator class, privileged mining identity, or upgrade key.

### 3.3 AI exclusion from consensus

Model inference is nondeterministic and version-dependent. A model response, model score, external inference endpoint, or subjective assessment MUST NOT be used to validate a transaction, block, proof-of-work result, dispute, or fork choice.

### 3.4 Resource boundedness

Every consensus-valid object MUST have statically computable upper bounds for serialized size, memory allocation, hashing, signature verification, script execution, and state growth.

### 3.5 Implementation lineage and network isolation

The first reference implementation SHALL be a **code fork** of one pinned Bitcoin Core release. It SHALL NOT inherit Bitcoin mainnet, testnet, signet, or regtest history, UTXOs, proof of work, checkpoints, assumed-valid blocks, minimum chain work, seed lists, or economic state.

The repository SHOULD use the following upstream roles:

- `upstream-core`: the pinned primary implementation lineage;
- `upstream-knots`: a source of individually reviewed candidate patches; and
- `origin`: this project's canonical repository.

Bitcoin Knots is not a second merge base. Every ported change MUST record its upstream commit, rationale, consensus or policy classification, local adaptations, and test evidence. Upstream Core updates MUST be deliberate release-engineering events with consensus-diff review, reproducible builds, and full regression testing.

Before the first public testnet, the implementation MUST replace or isolate at least:

- genesis block and chain identifier;
- peer-message magic and protocol domains;
- default P2P and RPC ports;
- address encodings, human-readable prefixes, and extended-key versions;
- DNS seeds, fixed seeds, checkpoints, assumed-valid data, and minimum chain work;
- data-directory, configuration-file, cookie, IPC, and process names;
- signed-message and transaction-signature domains; and
- network-selection flags and user-visible branding.

Automated negative tests MUST prove that cross-network peers, addresses, signatures, messages, and chain data are rejected. Existing copyright and license notices MUST be preserved, and each imported patch MUST remain attributable.

## 4. Ledger model

### 4.1 UTXO state

The authoritative state is a set of unspent transaction outputs (UTXOs). Each output contains:

- an integer amount in the smallest native unit;
- a versioned spending-program commitment; and
- optional consensus-bounded metadata defined by that program version.

Account-global mutable state and arbitrary contract storage are excluded from version 0.

### 4.2 Transaction validity

A transaction is valid only if all of the following hold:

1. Every referenced input exists and is unspent.
2. Every input satisfies its active spending program.
3. No input is repeated within the transaction.
4. Amount arithmetic does not overflow.
5. The sum of inputs is at least the sum of outputs.
6. The difference between input and output sums is the fee.
7. Absolute and relative timelocks are satisfied.
8. The transaction satisfies active resource limits.
9. All hashes and signatures are computed over the canonical serialization and correct domain.

### 4.3 Canonical serialization

**Mainnet blocker:** A separate serialization specification SHALL define a single canonical binary representation. Parsers MUST reject duplicate fields, non-minimal integers, unknown mandatory fields, trailing data, ambiguous encodings, and arithmetic overflow.

Human-readable JSON MUST NOT be a consensus serialization.

### 4.4 Signature digest

Every signature digest MUST commit to:

- chain identifier;
- transaction format version;
- referenced inputs and their amounts;
- committed outputs;
- applicable spending-program version;
- lock conditions;
- fee-delegation flags; and
- an explicit signature-domain tag.

No signature valid on a testnet, fork, mandate, message, or peer session may be valid as a mainnet transaction signature.

## 5. Cryptographic suite

### 5.1 Hashing

The candidate hash primitive is SHA3-384. Every use MUST apply an unambiguous domain tag and length-delimited input encoding. Separate domains SHALL exist for at least:

- block identifiers;
- transaction identifiers;
- Merkle nodes and leaves;
- UTXO commitments;
- address/program commitments;
- signature digests;
- agent mandates;
- merchant quotes;
- receipts;
- share accounting; and
- peer handshakes.

Changing the hash primitive is a consensus change where the hash affects validity.

### 5.2 Transaction signatures

The candidate default signature is ML-DSA-65. Implementations MUST use a final standardized encoding and MUST incorporate all published corrections applicable at the protocol freeze date.

An output MUST NOT be spendable solely by ECDSA, Schnorr, RSA, EdDSA, or another signature family vulnerable to a sufficiently capable implementation of Shor's algorithm.

SLH-DSA SHALL be available as an independent recovery or high-assurance policy family. Requiring ML-DSA and SLH-DSA on every ordinary payment is not the default because signature size would materially raise validation and storage costs.

Candidate policy forms are:

```text
standard:      ML-DSA-65
high-assurance: ML-DSA-65 AND SLH-DSA
recovery:      ML-DSA-65 OR (relative-time-lock AND SLH-DSA)
```

Exact parameter sets and validation cost weights are mainnet blockers.

### 5.3 Versioned spending programs

Outputs commit to a spending-program version. Unknown versions MUST have explicitly specified behavior that permits future soft-fork restriction without making them accidentally spendable by legacy wallets.

Wallets MUST NOT send to an unknown program version unless the user explicitly imports a complete specification and validation policy.

### 5.4 Encrypted transport

The standard peer profile uses a hybrid key establishment containing:

- an ephemeral classical component for defense diversity; and
- ML-KEM-768 as the post-quantum component.

The session-key combiner MUST remain secure when either component remains secure, subject to the combiner's stated assumptions. Transport cryptography is not a consensus rule.

### 5.5 Cryptographic agility

Agility SHALL be achieved through versioned programs and transports, not an administrator selecting a new primitive. New primitives require public specifications, test vectors, independent implementations, and explicit node adoption.

## 6. Blocks and fork choice

### 6.1 Block contents

A block contains at minimum:

- format version;
- previous block identifier;
- transaction commitment;
- UTXO/state commitment;
- timestamp field;
- difficulty target encoding;
- proof-of-work data; and
- an ordered transaction body beginning with a subsidy transaction.

The final header layout is a mainnet blocker.

### 6.2 Target interval

The candidate target block interval is 600 seconds. The interval is a consensus constant after mainnet launch.

### 6.3 Fork choice

Nodes select the valid chain with the greatest accumulated proof-of-work, using deterministic tie handling. Peer count, claimed identity, pool label, coin ownership, and model judgment MUST NOT affect fork choice.

### 6.4 Difficulty adjustment

The difficulty algorithm SHALL:

- adjust deterministically without an oracle;
- tolerate abrupt loss or gain of hash rate;
- place bounds on timestamp influence;
- avoid an emergency administrator;
- resist oscillation and time-warp incentives; and
- be validated through adversarial simulation.

The exact formula is not selected. An ASERT-like or similarly analyzable continuous adjustment is a candidate. This is a mainnet blocker.

## 7. Proof of work

The candidate construction and its rejection gates are developed in [pow-vm-research.md](pow-vm-research.md). That research document does not activate or approve a consensus algorithm.

### 7.1 Requirements

The proof-of-work construction MUST be:

- deterministic and inexpensive to verify;
- specified permanently rather than chosen by periodic human governance;
- domain-separated to this chain;
- resistant to trivial reuse of another chain's dominant hardware;
- analyzable under classical and quantum attack models;
- bounded in verifier time and memory; and
- free of trusted setup or vendor attestation.

### 7.2 Candidate direction

The current candidate is a fixed virtual machine executing a memory-bandwidth-heavy workload whose program is deterministically derived from prior finalized chain data. Program variation does not constitute algorithm rotation: the virtual machine and derivation rules remain fixed.

The seed MUST be known far enough in advance to avoid giving the latest block producer a material private advantage, while not enabling permanent precomputation.

### 7.3 Explicit non-guarantees

The protocol does not claim to be ASIC-proof or quantum-proof. Specialized hardware and a quantum first-mover advantage remain possible. The objective is to reduce abrupt proprietary advantage and preserve cheap verification, not to prohibit capital investment.

### 7.4 Open work

No mainnet implementation may proceed until the algorithm has:

- a complete mathematical and byte-level specification;
- reproducible CPU, GPU, FPGA, and candidate ASIC benchmarks;
- a reversible-circuit and quantum-memory cost analysis;
- grinding and seed-manipulation analysis;
- denial-of-service bounds; and
- multiple independent implementations.

## 8. Monetary policy and launch

### 8.1 Issuance principles

Consensus SHALL define a deterministic block subsidy with:

- no premine;
- no founder or investor allocation;
- no protocol treasury or development percentage;
- a declining initial subsidy; and
- a small fixed tail subsidy after the decline schedule.

The fixed tail subsidy implies unbounded nominal supply with percentage inflation tending toward zero. Exact units, decline schedule, maturity, and tail amount remain open and require economic simulation.

### 8.2 Subsidy transaction

The subsidy transaction MUST NOT create more than the active subsidy plus valid transaction fees. Newly issued outputs SHALL have a maturity delay to reduce short-reorganization risk.

### 8.3 Fair launch profile

Before mainnet:

- the specification and source SHOULD be public for at least one year;
- a public testnet SHOULD run through multiple release cycles;
- at least two independently maintained validators MUST interoperate;
- builds MUST be reproducible;
- genesis randomness MUST be derived from a future public event using a committed procedure; and
- no official exchange, custodian, pool, or privileged bootstrap miner SHALL be operated by the protocol project.

## 9. Node resource policy

### 9.1 Reference hardware target

Consensus limits SHALL be chosen so a fully validating pruned node remains practical on low-cost consumer hardware and a residential connection. The candidate worst-case historical growth budget is 30–50 GB per year, subject to benchmark validation.

### 9.2 Multidimensional resource accounting

A block MUST satisfy limits for:

- serialized bytes;
- post-quantum signature verification;
- hashing and proof verification;
- script operations;
- UTXO creation and destruction;
- temporary memory; and
- worst-case state access.

A byte-only limit is insufficient because post-quantum and zero-knowledge operations have different computational costs.

### 9.3 UTXO commitment

Every block SHALL commit to the resulting UTXO state. A Utreexo-like accumulator and stateless proof mode are candidates, but remain **Research** until proof update, data availability, reorganization, and wallet recovery behavior are fully specified.

## 10. Script and contract policy

Version 0 SHOULD provide only bounded primitives needed for:

- post-quantum signature policies;
- multisignature;
- hash locks;
- absolute and relative time locks;
- payment channels;
- vault recovery;
- constrained successor-output covenants; and
- fee sponsorship that cannot alter the authorized payment intent.

Consensus MUST NOT execute a general-purpose unmetered virtual machine. Every script path MUST have a static resource ceiling.

Price oracles, identity registries, AI inference, subjective service quality, and legal judgments remain outside consensus.

## 11. Mining decentralization profile

### 11.1 No pool identity cap

Consensus MUST NOT attempt to enforce a maximum percentage for a pool identity. A real-world organization can create unlimited keys, addresses, servers, and labels. Identity caps would be Sybil-vulnerable or require a permissioned identity authority.

### 11.2 Independent block construction

The standard miner-to-coordinator interface MUST use an encrypted and authenticated Stratum V2 profile, including custom job declaration or a successor mechanism with equivalent miner control. Official mining software MUST NOT enable or advertise legacy Stratum V1. A coordinator connection that cannot provide the required authenticated transport and miner-declared jobs MUST fail closed or fall back to solo/decentralized operation.

This is a mining-software profile, not a block-consensus rule. A valid block cannot be rejected based on an unverifiable claim about which transport produced its proof of work.

The standard mining profile MUST allow each miner to:

- obtain candidate transactions from its chosen full node;
- construct its own block template;
- declare custom work to an accounting service;
- reject templates imposed by that service;
- publish a discovered block directly; and
- switch accounting services without changing hardware firmware.

The pool or accounting coordinator SHOULD be limited to validating shares and calculating payouts.

### 11.3 Decentralized share accounting

A P2Pool-like sharechain or share DAG is a required testnet workstream. Its goals are:

- direct noncustodial payouts;
- no central template authority;
- tolerable variance for small miners;
- resistance to share withholding and history rewriting;
- bounded bandwidth and storage; and
- one-time or shielded payout identifiers.

The share system is not part of base consensus in v0.1. Making it consensus-native requires a separate proposal and threat model.

### 11.4 Automatic fallback

Standard miner software SHOULD switch to another accounting service or decentralized sharechain when a valid custom job is rejected. Observed concentration warnings MAY influence defaults, but MUST NOT be represented as proof of real-world ownership.

## 12. Privacy architecture

### 12.1 Privacy properties

The design seeks to reduce disclosure of:

- reusable payment identifiers;
- transaction graph relationships;
- amounts and balances where a future shielded mode permits;
- transaction-origin IP metadata;
- wallet implementation fingerprints;
- miner payout history; and
- AI prompts, service descriptions, and commercial intent.

It does not promise anonymity against endpoint compromise, voluntary identity disclosure, KYC records, physical surveillance, or a sufficiently capable global correlation adversary.

### 12.2 Receiving identifiers

Wallets MUST avoid address reuse. A post-quantum noninteractive one-time receiving construction is desired but not yet specified because ML-DSA does not directly provide Bitcoin-style public key tweaking.

Until a reviewed construction exists, the standard wallet SHALL use one or more of:

- interactive fresh-address negotiation;
- pre-generated one-time receive keys with authenticated replenishment; or
- another separately specified post-quantum construction.

### 12.3 Collaborative transactions

The wallet profile SHOULD support Payjoin-like input collaboration, CoinJoin-style batching, indistinguishable change handling, canonical ordering, and wallet-fingerprint resistance. These are wallet protocols, not consensus claims.

### 12.4 Shielded UTXOs

A transparent, hash-based, post-quantum zero-knowledge shielded pool is **Research**. It MUST NOT activate until it provides:

- no trusted setup;
- practical proof generation on consumer devices;
- bounded verification on reference node hardware;
- publicly auditable conservation of value through proof validity;
- multiple independent implementations;
- formal and empirical soundness review;
- upgrade and failure procedures; and
- a clear response to a discovered hidden-inflation flaw.

Pairing-based or discrete-log proof systems MUST NOT be described as post-quantum.

### 12.5 Selective disclosure

Wallets SHOULD support user-controlled incoming, outgoing, account, and auditor viewing capabilities, plus transaction-specific receipts. No universal viewing key is permitted.

## 13. Fail-closed wallet networking profile

### 13.1 Privacy broadcast invariant

The official wallet MUST never broadcast a transaction directly and MUST fail closed unless a locally enabled, audited anonymity transport is operational.

“Audited” does not mean authorized by a foundation or government. It means the local user has enabled a transport implementation with a public protocol and security review.

### 13.2 Component isolation

The compliant architecture is:

```text
wallet signer -> loopback-only interface -> privacy broadcaster
privacy broadcaster -> Tor, I2P, or reviewed mixnet -> remote peer
```

The wallet process MUST NOT have general outbound network capability. Operating-system sandboxing SHOULD enforce this restriction.

### 13.3 Failure behavior

If all configured anonymity transports fail:

- the transaction MUST remain queued and encrypted at rest locally;
- the wallet MUST display that it has not broadcast;
- no DNS or clearnet fallback may occur; and
- repeated retries MUST preserve the same payment-intent identifier without creating duplicate payments.

The wallet SHALL distinguish at least these states:

```text
SIGNED_LOCAL       transaction exists only on the device
PRIVATE_SUBMITTED  an anonymity-routed peer accepted the submission
NETWORK_OBSERVED   the transaction was independently observed from the network
CONFIRMED          the transaction is included in the selected valid chain
```

The user interface MUST NOT label `SIGNED_LOCAL` as broadcast or `PRIVATE_SUBMITTED` as confirmed.

### 13.4 Origin-aware relay

A local full node MUST NOT immediately announce a locally originated transaction over an identifying route. The isolated broadcaster sends it first through the anonymity network. The local node MAY relay it normally after observing it return from the wider network, subject to correlation analysis and randomized timing.

### 13.5 Transport diversity

The standard profile SHOULD support more than one anonymity network. Tor-only consensus would create a liveness dependency outside the chain. Consensus cannot prove which route carried a transaction and MUST NOT require a Tor certificate.

### 13.6 Other wallet traffic

Updates, fee estimates, peer discovery, remote scanning, exchange-rate queries, crash reporting, and time synchronization MUST NOT bypass the configured privacy policy. Telemetry is disabled by default and MUST never contain wallet identifiers or transaction material.

## 14. Optional delegated software payment layer

### 14.1 Trust boundary

This entire section is optional application behavior. It grants no special status to AI agents, and ordinary human-controlled wallets do not need to implement autonomous spending.

An AI model is an untrusted planner. It MAY propose a structured payment intent. It MUST NOT:

- possess a master spending key;
- call an unrestricted signing interface;
- alter its own authorization policy;
- interpret ambiguous merchant data inside the signer;
- decide whether a consensus rule is satisfied; or
- bypass privacy-broadcast requirements.

### 14.2 Deterministic authorization path

The required logical path is:

```text
model proposal
  -> canonical intent parser
  -> deterministic policy engine
  -> isolated capability signer
  -> fail-closed privacy broadcaster
  -> channel or base settlement
```

Only deterministic code may approve the transition from proposal to signature.

### 14.3 Capability vaults

An owner SHOULD delegate a bounded UTXO or channel balance rather than a master wallet. Candidate enforceable constraints include:

- total delegated amount;
- maximum amount per payment;
- rolling or epoch spending limit;
- maximum fee;
- activation and expiration heights;
- large-payment delay;
- required co-signers above thresholds;
- permitted successor program templates; and
- owner recovery path.

Constraints that depend on real-world merchant categories or subjective service descriptions cannot be enforced by base consensus without an oracle. They remain signer policy.

### 14.4 Mandate format

Every autonomous payment MUST be authorized by a canonical mandate containing at least:

```text
schema_version
chain_id
mandate_id
principal_key_commitment
agent_capability_key
settlement_asset
maximum_total_amount
maximum_single_payment
maximum_fee
valid_from
valid_until
maximum_uses
service_schema_hash or explicit wildcard policy
refund_program
privacy_profile
policy_version_hash
```

The principal signs the mandate with a post-quantum signature. Open-ended mandates MUST still contain finite amount, duration, and use bounds.

### 14.5 Merchant quote

Before payment, the merchant MUST provide a signed canonical quote containing:

- quote and mandate identifiers;
- merchant payment key;
- exact amount or bounded pricing formula;
- service or item commitment;
- delivery conditions;
- refund conditions;
- expiration;
- accepted settlement method; and
- fee responsibility.

The policy engine MUST compare the quote with the mandate. Natural-language text MUST NOT override canonical fields.

### 14.6 Replay and duplication protection

Mandate IDs, quote IDs, execution counters, and settlement identifiers MUST be domain-separated and durable across restarts. A repeated request with an already consumed single-use intent MUST return the existing result or fail; it MUST NOT create another payment.

Cloning an AI process MUST NOT clone its spending allowance. Allowance state resides in the isolated signer, channel state, or covenant UTXO.

### 14.7 Receipts

A successful merchant response SHOULD contain a post-quantum signed receipt committing to:

- mandate and quote identifiers;
- settlement reference;
- amount and fee;
- service and delivery commitments;
- completion status;
- refund state; and
- block height or channel sequence.

Receipts are encrypted at rest and disclosed selectively by the owner. Private prompts and service contents MUST NOT be placed on-chain.

### 14.8 Micropayments

High-frequency AI services SHOULD use channels, streaming balances, batched settlement, or hash-chain tickets. Base-layer settlement per API call is noncompliant with the scalability objective.

An HTTP 402-style negotiation MAY be supported, but local verification MUST be possible. No protocol facilitator is mandatory or privileged.

### 14.9 Conditional digital delivery

Hash-locked delivery MAY exchange payment for revelation of a committed decryption key. This proves delivery of committed bytes, not correctness, truth, usefulness, or legal performance. Subjective disputes require optional external arrangements and do not change consensus.

### 14.10 Safe failure

The signer MUST refuse payment when policy state, chain state, privacy transport, quote validity, fee bounds, or replay state cannot be verified. “Unable to verify” MUST NOT be delegated back to the AI model.

## 15. Peer-to-peer network

The standard node profile SHOULD provide:

- encrypted, pseudorandom transport;
- Tor and I2P reachability;
- ASN- and network-diverse peer selection where IP peers are used;
- eclipse-resistant outbound rotation;
- transaction reconciliation to support more peers at bounded bandwidth;
- compact block relay;
- local compact-filter scanning for lightweight wallets; and
- multiple independent bootstrap mechanisms.

DNS seeds MAY assist discovery but MUST NOT be trusted for consensus or chain state.

## 16. Governance and upgrades

### 16.1 No on-chain government

There is no token vote, miner legislature, foundation veto, or committee capable of changing validity rules.

### 16.2 Change process

A consensus change SHOULD include:

- a standalone specification;
- security rationale and threat-model update;
- test vectors;
- at least two implementations;
- reproducible testnet evidence;
- a long public review period; and
- explicit node-operator adoption.

Miner signaling may communicate readiness but MUST NOT be represented as authority over users' validation rules.

### 16.3 Software distribution

Releases SHOULD be reproducible and signed by multiple independent maintainers. Nodes MUST NOT auto-install consensus changes. Compromise of a website, repository, or signing key MUST NOT alter already-running consensus behavior.

## 17. Validation outline

For each candidate block, a validator performs at least:

1. Parse canonical block encoding with all bounds enforced.
2. Verify linkage to a known parent or store as an orphan within resource limits.
3. Verify difficulty encoding and proof of work.
4. Verify timestamp constraints and accumulated-work calculation.
5. Verify the subsidy transaction and issuance ceiling.
6. Verify transaction and state commitments.
7. Validate each transaction against the parent UTXO state.
8. Apply resource accounting before expensive operations can cause unbounded work.
9. Compute and compare the resulting UTXO commitment.
10. Update fork choice only after complete validation.

No unvalidated header, proof, checkpoint, peer reputation score, or AI assessment may bypass these steps.

## 18. Required test programs

Before mainnet, the project MUST maintain:

- canonical serialization vectors;
- valid and invalid block/transaction corpora;
- differential tests across implementations;
- property tests and coverage-guided fuzzing;
- cryptographic known-answer tests;
- reorganization and difficulty simulations;
- resource-exhaustion tests;
- wallet network-leak tests that observe operating-system packets;
- mandate replay and prompt-injection tests;
- sharechain withholding and partition simulations; and
- reproducible initial-sync benchmarks on declared reference hardware.

## 19. Phased implementation

Every post-genesis consensus change MUST follow [upgrade-activation.md](upgrade-activation.md). Miner signals measure readiness and never replace deliberate validation-rule adoption by users.

### Phase 0: Research freeze

Pin the Bitcoin Core base release and commit; inventory candidate Knots patches; then resolve proof of work, serialization, difficulty, issuance, resource weights, and cryptographic parameter sets. Produce an inherited-assumptions register before changing consensus code.

### Phase 1: Consensus laboratory

Create the new genesis and chain parameters, enforce complete network isolation, retain the applicable Bitcoin Core regression suite, and build two minimal validators, deterministic block generation, a transaction generator, and a differential conformance suite. No wallets with real value.

### Phase 2: Public testnet

Add P2P networking, post-quantum wallets, fail-closed broadcasting, miner-created templates, and adversarial testing.

### Phase 3: Mining and agent testnet

Add decentralized share accounting, capability vaults, channels, mandates, receipts, and automated attack simulations.

### Phase 4: Privacy research network

Test post-quantum receiving schemes and any shielded construction separately. Privacy research does not delay validation of the transparent consensus core, but unreviewed privacy code does not enter mainnet.

### Phase 5: Mainnet readiness review

Mainnet requires closure of every blocker in the project README, independent audits, multiple interoperable clients, reproducible builds, and an explicitly documented set of remaining risks.

## 20. Non-goals and rejected claims

This protocol does not claim to:

- prevent wealthy entities from buying hardware or coins;
- identify or cap real-world mining organizations;
- guarantee anonymity;
- guarantee permanent quantum security;
- prove that a transaction used Tor;
- determine whether an AI output is true or useful;
- maintain a fiat exchange rate without external assumptions;
- reverse authorized payments through an administrator;
- eliminate all custodians or ETFs; or
- make unsafe key management safe through consensus.

Its objective is narrower and testable: preserve independent verification, remove privileged control paths, bound delegated authority, and make private decentralized operation the standard software behavior.

