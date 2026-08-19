# Soveroot Threat Model

Version: 0.1 working draft  
Applies to: protocol specification v0.1

## 1. Purpose

This document identifies what the protocol protects, which adversaries it considers, where trust remains, and what failures cannot be prevented.

The threat model is intentionally stricter than a feature list. A control is not accepted merely because it sounds decentralized, private, post-quantum, or AI-safe. It must have a stated enforcement boundary and a testable security property.

## 2. Protected assets

### 2.1 Consensus assets

- Uniqueness and ownership of unspent outputs.
- Conservation of value except for deterministic issuance.
- Correct accumulated-work fork choice.
- Deterministic validation across implementations.
- Availability of the transaction and state data needed for validation.
- Ability of users to reject rule changes independently.

### 2.2 User assets

- Master and delegated private keys.
- Wallet seed and recovery material.
- Transaction intent and payment authorization.
- Transaction-origin network metadata.
- Transaction graph, balance, and commercial activity.
- AI prompts, purchased services, receipts, and audit records.

### 2.3 Mining assets

- Miner control over transaction selection.
- Correct attribution and payout of contributed work.
- Ability to leave a coordinator without replacing hardware.
- Privacy of miner identity, location, and payout history.

### 2.4 Ecosystem assets

- Reproducible software distribution.
- Independence of implementations and maintainers.
- Absence of privileged emergency control.
- Long-term cryptographic migration capacity.

## 3. Trust boundaries

The design assumes:

- users can obtain at least one honest implementation or verify source/builds;
- cryptographic primitives meet their stated assumptions;
- a user device that signs is not fully compromised;
- honest proof-of-work exceeds adversarial work for probabilistic finality;
- necessary block data remains obtainable from at least one peer; and
- owners protect recovery keys and understand that external identity disclosure cannot be undone by protocol privacy.

The design does not trust:

- individual peers;
- a mining pool or share coordinator;
- a software website;
- an AI model;
- merchant-provided natural language;
- a remote fee or price API;
- a Tor relay;
- a single maintainer;
- a custodian; or
- a claimed real-world mining identity.

## 4. Adversary classes

### A1. Opportunistic remote attacker

Attempts theft, malformed-object denial of service, wallet exploitation, replay, or merchant fraud using commodity resources.

### A2. Malicious peer or Sybil network

Creates many peers to eclipse nodes, delay blocks, correlate broadcasts, feed false fee information, or exhaust resources.

### A3. Global or regional network observer

Observes packet timing, volume, ISP links, Tor entry traffic, public relays, and service endpoints. May block anonymity networks or correlate both sides of a connection.

### A4. Mining coordinator

Attempts to impose templates, censor transactions, withhold blocks, misreport shares, seize rewards, identify miners, or prevent switching.

### A5. Large miner or mining cartel

Performs censorship, selfish mining, reorganizations, timestamp manipulation, sharechain attacks, or coercive fork signaling. May split activity across unlimited identities.

### A6. Malicious merchant or service

Changes a quote, creates ambiguous terms, triggers repeated payment, delivers incorrect bytes, manipulates an AI prompt, or falsely claims nonpayment.

### A7. Compromised or adversarial AI agent

Acts outside user intent because of prompt injection, poisoned context, model error, malicious tool output, copied runtime state, or deliberate behavior.

### A8. Software supply-chain attacker

Compromises a repository, dependency, build system, update channel, website, maintainer key, package registry, or binary distributor.

### A9. Cryptographically relevant quantum attacker

Applies quantum algorithms to signatures, hashes, proof of work, encrypted recordings, or proof systems. May obtain a temporary private mining advantage.

### A10. State-level or coercive actor

Combines regulation, ISP observation, mining pressure, custodial seizure, exchange surveillance, hardware supply control, and software censorship.

### A11. Insider or device attacker

Obtains wallet process access, signing-service access, seed backups, logs, clipboard data, screen contents, or hardware-wallet approval.

## 5. Critical security invariants

The following invariants are release-blocking:

1. **No unauthorized inflation:** No valid transition creates value beyond deterministic issuance and fees already present in inputs.
2. **Independent validity:** No remote service, checkpoint, model, miner signal, or identity assertion can make an invalid block valid.
3. **No AI master key:** An AI runtime cannot access a master signing secret or unrestricted signing API.
4. **Deterministic authorization:** Every agent payment is approved by canonical parsing and deterministic policy checks.
5. **Bounded delegation:** Compromise of an agent capability cannot spend outside its enforceable amount and time bounds.
6. **Replay safety:** The same single-use mandate cannot cause two valid authorized payments.
7. **Fail-closed origin privacy:** A compliant official wallet emits no transaction bytes over a direct external route when anonymity transport is unavailable.
8. **No silent privacy downgrade:** Failure of Tor, I2P, a mixnet, scanning, or shielded proving produces a visible failure, not clearnet fallback.
9. **Miner template autonomy:** A compliant miner can construct, hash, and publish its own valid template without coordinator permission.
10. **No privileged upgrade:** Possession of a project, maintainer, treasury, or emergency key cannot change active consensus rules.
11. **Bounded validation:** Every accepted object has enforceable worst-case resource bounds.
12. **Domain separation:** A signature or hash proof from one protocol context cannot authorize another context.
13. **Network isolation:** No Bitcoin-network address, message, signature, peer session, or chain artifact is accepted merely because the implementation shares Bitcoin Core ancestry.

## 6. Threat matrix

### T1. Invalid spend or inflation

**Attack:** Exploit parsing ambiguity, arithmetic overflow, signature confusion, UTXO inconsistency, proof-system flaw, or implementation divergence.

**Controls:**

- canonical encoding and minimality rules;
- checked integer arithmetic;
- domain-separated signature digests;
- complete UTXO validation;
- state commitments;
- two independent validators;
- differential testing and fuzzing;
- no shielded system without soundness review.

**Residual risk:** A shared specification error or cryptographic break can affect all implementations. Shielded inflation may be difficult to detect after the fact.

### T2. Consensus implementation split

**Attack:** Craft an object interpreted differently by implementations.

**Controls:**

- canonical parser requirements;
- exhaustive edge-case vectors;
- cross-client differential fuzzing;
- fixed-width or explicitly bounded fields;
- rejection of unknown mandatory fields;
- slow deployment of consensus changes.

**Residual risk:** Independent implementations improve diversity but increase the chance of accidental divergence. Conformance evidence is mandatory.

### T2A. Upstream inheritance or cross-network confusion

**Attack:** An overlooked Bitcoin Core constant, seed, checkpoint, signature domain, address prefix, data path, or chain assumption connects the new implementation to a Bitcoin network, reuses an artifact across chains, or silently preserves an unwanted rule.

**Controls:**

- a pinned Core base and inherited-assumptions register;
- a new genesis and chain identifier;
- unique message magic, ports, address encodings, data paths, and signature domains;
- removal of inherited seeds, checkpoints, assumed-valid blocks, and minimum chain work;
- negative cross-network test vectors;
- provenance and classification for each Knots patch; and
- consensus-diff review for every upstream update.

**Residual risk:** Shared ancestry is valuable but creates a large inherited attack surface. Isolation must be continually tested, not assumed after the initial fork.

### T3. Majority-work reorganization

**Attack:** A miner or cartel outworks the honest chain, reverses payments, or censors transactions.

**Controls:**

- accumulated-work fork choice;
- broad mining accessibility;
- miner-created templates;
- decentralized share accounting;
- confirmation policies proportional to value;
- no minority-chain reuse of a dominant external PoW fleet.

**Residual risk:** Proof of work cannot stop an adversary with sustained majority work. The protocol cannot cap a real-world organization at 10% because identities are Sybilable.

### T4. Early-chain and low-hash attack

**Attack:** At launch or during a collapse, a modest attacker reorganizes the chain.

**Controls:**

- long public test phase;
- gradual economic launch;
- difficulty response to hash shocks;
- conservative confirmation requirements;
- no trusted bridge or high-value official market at launch.

**Residual risk:** A permissionless new chain cannot manufacture an honest security budget. Permanent checkpoints would trade this risk for administrator control and are rejected.

### T5. Pool template control

**Attack:** A coordinator uses pooled hash rate to censor, select a fork, or impose transaction policy.

**Controls:**

- miner-side template construction;
- custom-job declaration;
- direct miner block publication;
- automatic coordinator fallback;
- decentralized share accounting.

**Residual risk:** A coordinator may reject shares or offer economic incentives for compliance. Miners that do not run the standard profile remain exposed.

### T6. Share accounting fraud

**Attack:** Withhold shares, rewrite share history, create payout dust, eclipse small miners, or steal custody balances.

**Controls:**

- publicly verifiable proof-of-work shares;
- direct coinbase or trust-minimized payouts;
- fork-resistant share DAG design;
- bounded share propagation;
- no coordinator custody by default;
- adversarial simulation.

The [sharechain private-lab profile v0](sharechain-v0.md) exercises canonical
encoding, a fixed share target, trusted-round binding, proof-reassignment
prevention, accumulated-work fork choice, finality, and payout grouping through
15 vectors checked by two independently written validators.

The [three-process synchronization profile](sharechain-sync-v0.md) adds pinned
pairwise message authentication, monotonic replay protection, fixed message and
orphan limits, restart persistence, and adversarial partition, selective-relay,
equivocation, flood, and oversized-frame tests over loopback.

**Residual risk:** All three peers run on one machine and trust prearranged
symmetric keys and fixture round context. Pairwise HMAC evidence is not portable
proof of authorship. There is no public discovery, independently operated host,
Sybil or eclipse defense, or production settlement. Decentralized pooling also
has variance, bandwidth, payout-size, reorganization, and temporary-majority
problems. The final design is unresolved.

Worker block withholding is distinct from ordinary share withholding. A worker may submit payable shares while discarding the rare shares that would form blocks. The [XOR-key study](xor-key-block-withholding-study.md) evaluates hiding the final block condition from a worker, but the construction is not an approved control. A coordinator-held reveal key can itself prevent direct publication during coordinator failure or refusal, and it does not prevent a coordinator from withholding blocks.

### T7. Proof-of-work specialization

**Attack:** Secret ASIC, FPGA, firmware, memory, or quantum implementation gains a dominant efficiency advantage.

**Controls:**

- public fixed algorithm;
- memory-bandwidth-heavy candidate design;
- independent optimized implementations;
- advance program-seed schedule;
- hardware and reversible-circuit analysis;
- predeclared specialization targets and rejection gates from the PoW VM research specification.

**Residual risk:** ASIC resistance cannot be guaranteed. Facilities, energy contracts, fabrication access, and capital remain sources of concentration.

### T8. Quantum signature theft

**Attack:** Recover a private key from a classical public key or forge a transaction authorization.

**Controls:**

- ML-DSA authorization from genesis;
- no classical-only spend path;
- SLH-DSA recovery/high-assurance option;
- versioned cryptographic programs;
- address reuse prohibition.

**Residual risk:** ML-DSA or SLH-DSA may receive new cryptanalysis or implementation attacks. “Post-quantum” is an assumption, not a permanent guarantee.

### T9. Quantum mining advantage

**Attack:** A first mover uses quantum search or memory technology to obtain concentrated block production.

**Controls:**

- larger hash-output margin;
- memory-heavy proof-of-work research;
- difficulty adjustment;
- explicit quantum cost modeling.

**Residual risk:** Difficulty adjusts network rate, not political concentration. No known design guarantees equal classical and quantum mining economics.

### T10. Cryptographic downgrade

**Attack:** Wallet, merchant, peer, or update channel negotiates a weaker algorithm or legacy output.

**Controls:**

- no classical-only consensus program;
- exact version matching;
- downgrade-bound transcript hashes;
- wallet refusal of unknown output versions;
- fail-closed negotiation.

**Residual risk:** Users can run modified software or voluntarily send to unsafe programs if consensus permits them. Version policy must be conservative.

### T11. Transaction-origin correlation

**Attack:** First peer or observer links a transaction to a residential IP through timing or packet observation.

**Controls:**

- isolated broadcaster;
- Tor/I2P/mixnet routes;
- onion peer endpoints;
- origin-aware local relay;
- randomized timing and transport diversity;
- no DNS or clearnet fallback;
- packet-level leak tests.

**Residual risk:** A global observer may correlate entry and exit timing. Tor guards see a client connection. Endpoint compromise, KYC records, and direct merchant identification remain outside protocol control.

### T12. Anonymity-network outage or censorship

**Attack:** Block Tor, poison discovery, deny circuits, or exploit dependency on one anonymity network.

**Controls:**

- multiple transport plugins;
- bridges and pluggable transports where available;
- encrypted local queue;
- visible fail-closed state;
- no Tor requirement in consensus.

**Residual risk:** Privacy-preserving liveness may be unavailable in a hostile region. The wallet intentionally chooses safety over immediate broadcast.

### T13. Transaction graph analysis

**Attack:** Link inputs, outputs, amounts, timing, change, wallet fingerprint, or repeated payment identifiers.

**Controls:**

- fresh receive keys;
- collaborative transactions;
- canonical transaction construction;
- private wallet scanning;
- shielded system research;
- separate reputation and payment identities.

**Residual risk:** Transparent transactions leak substantial graph information. Optional privacy creates smaller anonymity sets. A mature post-quantum shielded design is not yet available.

### T14. Wallet fingerprinting

**Attack:** Identify software or user through fee selection, ordering, script policy, retry behavior, or unusual recovery paths.

**Controls:**

- standardized construction profiles;
- canonical ordering where privacy analysis supports it;
- committed/hidden policy branches;
- common fee algorithms with randomized safe ranges;
- no unique telemetry identifiers.

**Residual risk:** Rare policies, behavior, and timing may still fingerprint users.

### T15. Prompt-injection payment

**Attack:** Merchant text, webpage, email, tool result, or retrieved document tells an AI to pay an attacker or expand its budget.

**Controls:**

- AI cannot call raw signer;
- canonical intent schema;
- deterministic policy engine;
- merchant quote must match signed mandate;
- natural language cannot override fields;
- finite capability wallet;
- human or independent co-signature thresholds.

**Residual risk:** A mandate that is itself too broad may authorize an undesirable but formally compliant payment. Policy design and user comprehension remain critical.

### T16. Agent cloning and budget multiplication

**Attack:** Copy agent runtime or roll back its local state to reuse an allowance.

**Controls:**

- allowance state outside the model;
- durable signer counters;
- on-chain capability UTXOs or channel state;
- unique execution identifiers;
- atomic state update before returning success.

**Residual risk:** Multiple independently funded capability wallets legitimately multiply exposure. Owners must inventory delegated authority.

### T17. Duplicate payment after retry

**Attack:** Network timeout causes an agent to resubmit and pay twice.

**Controls:**

- idempotent mandate and quote IDs;
- consumed-intent database;
- merchant returns prior receipt for repeats;
- settlement lookup before retry;
- atomic payment/receipt state machine.

**Residual risk:** A malicious merchant may issue distinct quote IDs for the same semantic order. Maximum-use and amount limits bound loss.

### T18. Quote substitution or fee manipulation

**Attack:** Change destination, amount, service, refund terms, or fee after user authorization.

**Controls:**

- signed merchant quote;
- mandate binds limits and service commitment;
- signature digest binds outputs and fee rules;
- multiple local fee observations;
- maximum-fee enforcement;
- canonical display for human approvals.

**Residual risk:** The merchant may honestly quote a bad price. Cryptography proves terms, not economic fairness.

### T19. False or low-quality AI service delivery

**Attack:** Merchant delivers garbage while satisfying byte-level delivery.

**Controls:**

- ciphertext and content commitments;
- hash-locked key delivery;
- optional escrow, bond, reputation, or human dispute process;
- signed receipt.

**Residual risk:** Consensus cannot judge truth, usefulness, plagiarism, model quality, or legal performance. No AI oracle is introduced.

### T20. Signer or device compromise

**Attack:** Malware steals keys, modifies policy, approves fraudulent mandates, or exfiltrates wallet data.

**Controls:**

- isolated signer process or hardware;
- master/capability key separation;
- encrypted storage;
- transaction simulation and explicit policy hash;
- multisignature and delays for high value;
- offline recovery key;
- minimal APIs and memory-safe implementation.

**Residual risk:** A fully compromised device with access to authorized signing can spend within available authority. Hardware attestation is not made a consensus requirement.

### T21. Recovery-key race

**Attack:** Agent key and recovery key both attempt to spend after compromise.

**Controls:**

- delayed high-value agent path;
- immediate or faster owner recovery path where script semantics permit;
- monitoring and watchtowers;
- small hot capability balances.

**Residual risk:** Instant agent payments already broadcast may be irreversible. Recovery limits future loss, not completed settlement.

### T22. Malicious software release

**Attack:** Distribute wallet or node code that changes addresses, leaks keys, bypasses Tor, or follows invalid consensus.

**Controls:**

- reproducible builds;
- multiple independent signatures and mirrors;
- dependency pinning and review;
- no automatic consensus upgrades;
- deterministic network-leak tests;
- multiple implementations.

**Residual risk:** Users may install an unverified binary. Social concentration around one brand remains a governance risk.

### T23. Eclipse and false chain view

**Attack:** Surround a node with adversarial peers and hide the best chain or transaction state.

**Controls:**

- diverse peer selection;
- persistent and rotating outbound peers;
- multiple transports;
- anchor peers chosen by the user;
- accumulated-work validation;
- compact cross-checks from independent routes.

**Residual risk:** A fully isolated user can be delayed or shown a lower-work valid chain until honest connectivity returns.

The non-consensus [multi-host share-sync safety profile](sharechain-multihost-v1.md)
turns part of this list into exact laboratory checks: at least three configured
prefixes and operator groups, at least two transports, no more than one selected
peer per prefix or operator group, bounded connection churn, and refusal of
prefix- or operator-concentrated candidate sets. These are local heuristics,
not proof of independence. Operator labels can be forged, addresses can be
rented, transports can share upstream control, and routing can defeat apparent
diversity. Accumulated-work and complete-data validation remain authoritative.

The [routed namespace experiment](sharechain-routed-namespace-v1.md) exercises
four pinned source prefixes on the live socket boundary and rejects an identity
arriving from another configured route. All four namespaces still share one
host router, kernel, and administrator. Its two transport values are labels on
the same TCP stack, so the result does not materially reduce the residual risk
from forged labels, upstream capture, or a hostile Internet route.

The [four-operator kit](sharechain-operator-kit-v1.md) removes centralized
fixture-key distribution from the intended field workflow: every operator
creates their own private seed and exchanges only a signed public manifest.
It refuses repeated identities, endpoints, prefixes, or operator groups and a
transport monoculture. Self-signed manifests remain trust-on-first-use data,
however. They do not prove separate ownership, and the deterministic CI
packaging run sends no packet over an independently administered route.

### T24. Resource-exhaustion denial of service

**Attack:** Use large post-quantum signatures, malformed proofs, expensive scripts, peer flooding, or share spam to exhaust nodes.

**Controls:**

- parse bounds before allocation;
- staged cheap checks before expensive verification;
- multidimensional block weights;
- peer rate limits;
- bounded orphan and mempool storage;
- batch verification only when failure fallback is bounded;
- adversarial benchmarks.

**Residual risk:** Post-quantum and privacy features inherently consume more bandwidth and computation. Limits reduce throughput to preserve node accessibility.

The share-sync v1 safety profile additionally freezes 32,768-byte hellos,
131,072-byte frames, 16 active sessions, two sessions per identity, four per
IPv4 `/24` or IPv6 `/48`, deterministic handshake and message buckets, 256
replay nonces, 128 quarantines, 512 admission-bucket records per family, 128
peer candidates, and a 1,024-share catch-up ceiling. Limit state persists across
restart. The routed v1 listener now enforces the signed handshake, source pin,
session frame, and message admission on four namespace sockets with a frozen
30-second laboratory timeout. It is deliberately not publicly reachable and
does not establish safe hostile-Internet denial-of-service behavior.

The operator kit does not relax those bounds or install a public firewall. Its
runbook requires operators to restrict port `19444` to the declared experiment
routes. Safe Internet exposure, constant-time hybrid authentication, and
adversarial volumetric testing remain unresolved.

### T25. Data withholding

**Attack:** Announce headers or commitments without providing blocks, proofs, or state data.

**Controls:**

- fork choice only over fully validated available blocks;
- multiple block sources;
- penalties limited to local peer behavior, not consensus identity;
- no header-only finality assumption for full nodes.

**Residual risk:** Regional censorship can delay data. Lightweight clients have weaker availability assumptions than full nodes.

### T26. Stable-value oracle capture

**Attack:** Manipulate an external price used by agents, stable assets, collateral, or settlement limits.

**Controls:**

- no native fiat-price consensus;
- expiring signed bilateral quotes;
- multiple optional quote providers;
- agent slippage and maximum-native-amount limits;
- stable instruments remain opt-in secondary contracts.

**Residual risk:** No protocol can guarantee stable purchasing power. External stable assets introduce issuer, collateral, oracle, and legal risks.

### T27. Governance capture

**Attack:** Foundation, maintainers, miners, custodians, exchanges, or AI operators coordinate a rule change and portray it as mandatory.

**Controls:**

- no upgrade key;
- explicit node adoption;
- reproducible competing clients;
- long review periods;
- no automatic consensus update;
- miner signaling is informational only;
- missed readiness thresholds expire without mandatory lock-in;
- forced activation requires a separately named, explicitly consented fork proposal;
- consensus proposals require independent implementations and conformance tests.

**Residual risk:** Social and economic power cannot be eliminated by code. Users may voluntarily follow a captured implementation.

### T28. Custodial and ETF concentration

**Attack:** Large custodians accumulate coins, observe users, influence markets, or pressure forks.

**Controls:**

- easy self-custody;
- post-quantum multisignature and recovery;
- low-cost full validation;
- selective-disclosure accounting;
- no protocol privilege for custodial balances.

**Residual risk:** The protocol cannot prevent voluntary custody or regulated financial products. Ownership concentration is distinct from consensus validity.

## 7. Privacy attack paths

### 7.1 Network-to-ledger correlation

```text
observe residential connection
  -> identify transaction-sized encrypted burst
  -> observe transaction entering remote P2P network
  -> correlate timing
  -> combine with public transaction graph
```

Mitigation requires anonymity routing, timing variation, cover from other traffic, graph privacy, and avoidance of direct service identification. Encryption alone is insufficient.

### 7.2 Merchant correlation

```text
merchant learns customer context
  -> sees payment quote and timing
  -> links payment identifier or amount
  -> shares record with analytics or exchange
```

Mitigation requires one-time payment identifiers, hidden amounts where available, payment batching, private receipts, and minimizing identity disclosed to merchants. The protocol cannot erase merchant records.

### 7.3 Mining privacy leakage

```text
stable worker name or payout address
  -> share history
  -> hashrate and uptime estimate
  -> IP or facility correlation
```

Mitigation requires rotating identifiers, anonymous share transport, and shielded or unlinkable payouts. Public share accounting creates an inherent observability tradeoff.

## 8. AI authorization state machine

The minimum safe state machine is:

```text
DRAFT
  -> PARSED
  -> POLICY_VALIDATED
  -> QUOTE_BOUND
  -> RESERVED
  -> SIGNED
  -> PRIVATELY_BROADCAST
  -> SETTLED
  -> RECEIPTED
```

Rules:

- Failure before `SIGNED` releases the reservation without payment.
- Failure after `SIGNED` requires settlement lookup before retry.
- A mandate execution counter is consumed atomically with signing or reservation according to the final payment rail.
- The AI cannot move a payment backward or skip a state.
- A repeated intent returns the durable current state.
- Ambiguous recovery enters a stopped state requiring deterministic reconciliation or owner action.

## 9. Security acceptance criteria

A release is not eligible for public-value use unless all of the following are demonstrated:

### Consensus

- Two independent implementations agree on the complete valid/invalid corpus.
- Differential fuzzing finds no unresolved divergence.
- Initial sync and worst-case block validation meet reference hardware budgets.
- Difficulty and reorganization simulations cover documented adversarial strategies.
- Issuance can be independently calculated for every height.

### Cryptography

- Parameter sets and encodings are frozen and reviewed.
- Known-answer, malformed-input, side-channel, and fault tests exist.
- Domain-separation tests prove cross-context signatures fail.
- Cryptographic dependencies have reproducible builds and no silent runtime substitution.

### Wallet privacy

- With anonymity transports disabled or killed, packet capture observes no external wallet or origin-node transaction traffic.
- DNS, update, fee, time, and telemetry paths obey the same policy.
- The interface never reports broadcast before a privacy broadcaster accepts the transaction.
- The interface distinguishes local signing, private first-hop submission, independent network observation, and chain confirmation.
- Retry tests cannot create duplicate payment authorization.

### AI payments

- Prompt-injection corpora cannot invoke the signer directly.
- Policy evaluation is deterministic and model-independent.
- Cloned or rolled-back agent runtimes cannot multiply a fixed allowance.
- Quote substitution, fee escalation, replay, and schema ambiguity tests fail closed.
- High-value threshold and recovery paths are independently tested.

### Mining

- Miners can construct and publish blocks without a coordinator template.
- Coordinator rejection triggers tested fallback.
- Share accounting is tested under withholding, eclipse, partition, dust, and temporary-majority conditions.

### Supply chain

- Independent parties reproduce release binaries.
- Compromise exercises cover a website, one maintainer key, and one package registry.
- Running nodes do not automatically adopt consensus changes.

## 10. Incident response without an emergency key

The absence of an administrator is intentional. Incident response consists of:

1. Publish technical evidence and reproducible tests.
2. Release patched software through multiple maintainers and channels.
3. Allow node operators to choose whether and when to adopt it.
4. Pause official wallet spending when local safety invariants cannot be met.
5. Preserve forensic records without transmitting private wallet data.
6. Avoid representing developer preference as automatic consensus.

If an active cryptographic break requires a consensus restriction, the restriction is a publicly reviewed protocol change adopted by users. There is no key that can seize funds, rewrite history, or activate the change unilaterally.

## 11. Explicitly unmitigated or partially mitigated risks

- Sustained majority proof of work.
- A globally capable timing-correlation adversary.
- Fully compromised owner devices.
- Voluntary identity disclosure to merchants or custodians.
- Unknown breaks in post-quantum primitives.
- Secret specialized mining technology.
- Social capture of dominant software distribution.
- Economic volatility and inadequate security budget.
- Subjective fraud or low-quality AI services.
- Privacy loss from a small anonymity set.
- Legal coercion of identifiable companies and infrastructure.
- Human approval of an unsafe mandate.

These risks must be communicated to users. They must not be hidden behind the labels “decentralized,” “private,” “trustless,” “AI-safe,” or “quantum-proof.”

