# XOR-Key Block-Withholding Study

Status: **RESEARCH NOTE; NOT ADOPTED; NO CONSENSUS AUTHORIZATION**

Evidence cutoff: 2026-08-17

External source snapshot: Bitcoin Knots pull request #359 at commit [`4e683f13f45093fcdac52e4f4762999e44ab12e1`](https://github.com/bitcoinknots/bitcoin/commit/4e683f13f45093fcdac52e4f4762999e44ab12e1)

## Executive decision

Soveroot will study the XOR-key construction in Bitcoin Knots pull request #359 as a possible defense against **worker block withholding**. It will not copy the construction into consensus or the official mining profile now.

The idea has a useful narrow goal: a pool worker can identify ordinary payable shares but cannot tell which share is also a network-valid block. A dishonest worker must then discard a visible fraction of all shares to suppress a similar expected fraction of blocks, making sabotage costly and statistically easier to notice.

That benefit comes with a serious conflict. In the current construction, the accounting coordinator holds the secret needed to calculate and publish the final block hash. A miner cannot independently publish a discovered block while the coordinator is offline or malicious. Soveroot currently requires direct miner publication, automatic coordinator fallback, miner-created templates, and noncustodial accounting. Those properties must not be weakened to protect a centralized pool from one attack.

The current decision is therefore **research, do not adopt**. A future design must preserve miner publication authority and must pass the gates in this document.

## Plain-language explanation

In an ordinary pool, a mining machine can often recognize two things:

1. a normal share that proves it did some work; and
2. the much rarer share that is good enough to become a block.

A dishonest worker can submit the normal shares to get paid but secretly throw away the block-winning shares. The pool sees normal-looking work yet loses block revenue.

The XOR-key proposal gives the coordinator a secret mask. Part of the mask is intentionally zero so the worker can still recognize ordinary shares. The remaining secret portion hides whether an ordinary share also satisfies the harder network target. The coordinator commits to the secret before mining, and the complete block reveals it so every node can verify the result.

This changes the attack economics. If the hidden portion behaves like an independent random mask, information visible to the worker does not identify block-winning shares. To suppress roughly ten percent of the pool's blocks, the worker must discard roughly ten percent of its payable shares too. That is not prevention, but it removes the nearly free selective version of the attack.

## What the Knots draft implements

The reviewed snapshot is an unfinished hard-fork draft, not a standalone pool-protocol specification. Its version-two header contains a 128-bit `m_xor_key`, a public `m_xor_key_mask_clear_bits` value, and a hash commitment to the key. The proof-of-work function:

1. commits the key hash and clear-bit count into an intermediate tagged header hash;
2. derives a second tagged hash from the secret key as a mask;
3. clears the configured high-order mask bits;
4. computes the BLAKE2b mining result; and
5. XORs that result with the masked secret value to obtain the consensus proof hash.

The implementation comments describe a pooling miner receiving only the key commitment until a block is found. A null key disables the feature. The functional test covers the null-key behavior, mask-clear values, serialization, and block submission.

The code is currently shaped around existing Stratum V1 field layouts and ASIC inputs. It does not define a Stratum V2 Job Declaration exchange, key-release state machine, coordinator failover procedure, share-acceptance protocol, payout rule, or independent block-publication path.

## The exact protection boundary

| Threat | Result under the proposed idea | Limit |
| --- | --- | --- |
| Worker submits ordinary shares but selectively discards known blocks | Potentially reduced | The worker should not know which share is a block while enough target bits remain masked. |
| Worker discards a random fraction of all shares | Not prevented | Lost shares reduce payout and make the attack more observable, but sabotage remains possible. |
| Coordinator withholds a discovered block | Not addressed | The coordinator knows the key and can suppress publication. |
| Coordinator disappears before revealing the key | Made worse without recovery | The miner may hold useful work but be unable to construct the publishable header. |
| Coordinator imposes transaction templates or censorship | Not addressed | Key custody is independent of template authority. |
| Pool steals rewards or falsifies accounting | Not addressed | A secret mask is not noncustodial payout enforcement. |
| Majority mining, selfish mining, or eclipse attacks | Not addressed | These require separate controls. |
| Hardware or pool concentration | Not addressed | The construction changes withholding incentives, not economies of scale. |

The term "block withholding fix" must therefore be qualified as a possible **worker-selective block-withholding mitigation**.

## Interaction with the Soveroot mining profile

### Miner-created templates

The mechanism may be compatible with miner-created templates only if the miner and coordinator can jointly bind the template, key commitment, share target, payout terms, and job identifier without giving the coordinator transaction-selection power. Pull request #359 does not specify that exchange.

### Stratum V2 and Job Declaration

Soveroot does not permit legacy Stratum V1 in its official profile. Any experiment must use an authenticated Stratum V2 extension or an equivalent open protocol. The protocol must define message ordering, replay protection, job expiry, target changes, key commitment, key release, error handling, and transcript commitments.

### Direct block publication

Direct publication is a current Soveroot requirement. A coordinator-held secret violates it unless the miner can recover or receive the key quickly enough to publish without coordinator discretion. Giving the key to the miner before a solution restores publication but also restores the miner's ability to recognize and selectively withhold blocks.

Threshold release, precommitted recovery, or an independently replicated key service might reduce the outage risk, but each adds trust, latency, denial-of-service, and collusion assumptions. No such mechanism is approved.

### Decentralized share accounting

A P2Pool-like share DAG has no obvious single trusted key holder. A shared or threshold key could add a committee that becomes a liveness and censorship dependency. The defense must be evaluated against decentralized accounting rather than assuming a conventional centralized pool.

### Post-quantum margin

The external draft uses a 128-bit secret and SHA-256 tagged hashes. That is not automatically suitable for Soveroot's post-quantum security objectives. The key exists only for a short mining job, which changes the practical threat window, but any Soveroot variant must still justify its key length, domain separation, primitive choice, and Grover-style search margin. External field sizes and Bitcoin-specific hash tags must not be copied by default.

## Required security assumptions

The narrow argument works only if all of the following hold:

1. The coordinator commits to one fresh secret before receiving shares and cannot substitute another secret later.
2. The hidden mask bits are computationally unpredictable to the worker.
3. Visible share-acceptance responses do not leak the hidden mask.
4. A key is never reused across jobs whose responses could reveal it.
5. The clear-bit setting lets a worker verify its payable share threshold but leaves enough network-target information hidden.
6. The masked proof output remains uniformly distributed and does not bias difficulty.
7. The job transcript binds the miner's template, payout, target, key commitment, and expiry.
8. Key release cannot be withheld by one party without an explicit and acceptable recovery consequence.
9. Firmware, proxy, coordinator, and node implementations agree on byte order and exact-target comparison rather than relying only on leading-zero shorthand.

These are hypotheses requiring protocol and cryptographic review, not properties established by the current draft.

## Idealized model included in this repository

[`contrib/pool_research/xor_withholding_model.py`](../contrib/pool_research/xor_withholding_model.py) exhaustively checks a deliberately small leading-zero model. It enumerates all visible shares and all possible hidden masks and confirms that, averaged over an unknown uniform mask, selecting shares by their visible unmasked value does not increase the probability that a selected share is a block.

The model also shows the intended economic consequence: if visible information is independent of the final hidden target bits, discarding a fraction of shares suppresses the same expected fraction of blocks.

The model does **not** establish the security of BLAKE2b, the tagged-hash construction, arbitrary numeric targets, a fixed mask under adaptive queries, Stratum messaging, key custody, implementation side channels, or production pool economics. It is a regression check for one combinatorial claim only.

## Adoption gates

The research status remains `OPEN` until all gates below pass. Passing them would authorize a design review, not consensus activation.

1. **Protocol specification:** Publish a complete Stratum V2-compatible state machine, wire encoding, transcript commitment, share rule, and key lifecycle.
2. **Direct-publication preservation:** Demonstrate that a miner can publish a discovered block during coordinator crash, partition, censorship, or refusal without learning enough in advance to restore selective withholding.
3. **Template autonomy:** Demonstrate that the coordinator cannot change or veto the miner's transaction set beyond rejecting the accounting relationship.
4. **Exact-target analysis:** Replace the leading-zero model with exact 256-bit target analysis, including non-power-of-two pool targets and difficulty changes.
5. **Adaptive attack analysis:** Test whether accepted/rejected shares, timing, target updates, job reuse, chosen templates, or multiple workers leak mask information.
6. **Malicious-coordinator analysis:** Test key grinding, equivocation, refusal to reveal, stale-job replay, reward theft, and selective denial of service.
7. **Decentralized accounting test:** Implement the construction with a P2Pool-like share system or document why it cannot preserve the required trust model.
8. **Independent interoperability:** Two independently written miners and two coordinators must reproduce fixed vectors and adversarial failure cases.
9. **Cryptographic review:** Obtain independent review of primitive choice, key size, domain separation, output uniformity, and post-quantum margin.
10. **Operational evidence:** Measure block propagation, failover latency, false-positive withholding alerts, payout effects, and coordinator-switch behavior on an isolated lab network.

## Current recommendation

Do not add XOR-key fields to the Soveroot block header. First prototype the idea entirely outside consensus as a versioned mining-protocol experiment. Preserve the invariant that a miner's own node constructs the template and can publish the block. If no design can provide both hidden block recognition and independent publication without a trusted coordinator, Soveroot should reject this mitigation and focus on decentralized share accounting, observable coordinator behavior, and rapid switching.

## Primary source snapshot

- [Bitcoin Knots PR #359](https://github.com/bitcoinknots/bitcoin/pull/359) — draft status, stated goals, and review discussion.
- [`src/primitives/block.cpp` at the reviewed commit](https://github.com/bitcoinknots/bitcoin/blob/4e683f13f45093fcdac52e4f4762999e44ab12e1/src/primitives/block.cpp) — key commitment, clear-bit mask, BLAKE2b inputs, and final XOR.
- [`src/primitives/block.h` at the reviewed commit](https://github.com/bitcoinknots/bitcoin/blob/4e683f13f45093fcdac52e4f4762999e44ab12e1/src/primitives/block.h) — version-two header fields and serialization.
- [`feature_powchange.py` at the reviewed commit](https://github.com/bitcoinknots/bitcoin/blob/4e683f13f45093fcdac52e4f4762999e44ab12e1/test/functional/feature_powchange.py) — functional coverage and explicit null-key behavior.
- Miller, Kosba, Katz, and Shi, [Nonoutsourceable Scratch-Off Puzzles to Discourage Bitcoin Mining Coalitions](https://www.cs.umd.edu/~jkatz/papers/nonoutsourceable.pdf) — related nonoutsourceable-puzzle research; not evidence that the Knots construction has the same properties.
