# Sharechain private-lab profile v0

Status: **frozen offline conformance profile; not a public pool or production settlement system**

## Plain-English summary

A small miner should not have to give a pool operator control of its block
template, block publication, or reward wallet merely to receive frequent
payouts. A sharechain is a linked notebook of lower-difficulty proofs. Each
entry points to the previous entry and names the miner's payout script. The
best history is selected by accumulated work, so a single bookkeeper does not
get to rewrite the notebook by decree.

This milestone freezes the first notebook format and gives the same hostile
examples to two separately written calculators. Both calculators accept and
reject all 15 examples identically. That is specification evidence, not a live
decentralized pool: the examples are local files, the round information is a
trusted test fixture, and no peers exchange shares yet.

## Goals and boundary

The profile tests five narrow properties:

- one canonical share format and identifier;
- a fixed share target that a miner cannot make easier;
- binding to a trusted labnet round and miner-created header;
- deterministic accumulated-work fork choice, finality, and payout accounting;
- rejection of proof reassignment and malformed or stale histories.

The sharechain is off-chain accounting. It cannot make an invalid block valid,
change base-chain proof of work, identify a real mining organization, or cap an
organization's hash rate. The profile deliberately supplies no peer protocol,
peer discovery, Sybil or eclipse defense, production settlement, or final
Soveroot proof of work.

## Frozen constants

| Item | Value |
| --- | --- |
| Profile | `soveroot-sharechain-labnet-v0` |
| Corpus format | `soveroot-sharechain-adversarial-v0` |
| Share format | `soveroot-labnet-share-v0` |
| Chain | `labnet` |
| Canonical encoding | ASCII JSON, keys sorted, no insignificant whitespace |
| Identifier and commitment hash | SHA-256 |
| Labnet network bits | `207fffff` |
| Share target | `bfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff` |
| Work per accepted share | 2 integer work units |
| Finality depth | 2 shares behind the selected tip |
| Payout window | Last 4 finalized shares |
| Maximum corpus shares | 4,096 |
| Maximum trusted rounds | 64 |
| Equal-work tie break | Lowest `share_id_sha256` |

The easier share target permits genuine proofs that are valid shares but not
base-chain block candidates. The target is part of the profile, not miner
input.

## Canonical share

Each share contains exactly these fields plus `share_id_sha256`:

| Field | Meaning |
| --- | --- |
| `format`, `profile`, `chain` | Domain and network separation |
| `sequence` | Parent sequence plus one; the root is zero |
| `previous_share_id` | Parent share, or 32 zero bytes for the one root |
| `round_height` | Trusted labnet template height |
| `round_previous_block_hash` | Trusted base-chain parent for that round |
| `header_hex`, `header_hash` | Exact 80-byte header and verified SHA256d hash |
| `network_bits` | Frozen labnet block target encoding |
| `share_target_hex` | Frozen profile share target |
| `template_commitment_sha256` | Trusted commitment for the miner-created template |
| `payout_script_hex` | Canonical script receiving this share's accounting claim |
| `work_id_sha256` | Commitment to profile, chain, round, and header |
| `block_candidate` | Whether the header also meets the network target |
| `share_id_sha256` | SHA-256 of the canonical share body |

The work identifier deliberately excludes the payout script and share parent.
Consequently, the same header cannot be copied into a second share and credited
to another payout script or branch.

## Trusted round context

The corpus contains a small frozen table of labnet rounds so both validators
can be tested without a running node. Production software must not trust round
data merely because it appears in a share or file. It must obtain the previous
block, height, network bits, and template commitment from the miner's own
validated node through an authenticated local boundary.

An entry may stay in the same round only while its parent is not a block
candidate. A block-candidate parent ends that round. Its child must use the
next trusted height, must name the candidate's header hash as the next
base-chain parent, and must use that round's trusted template commitment.
Extending the old round after a block candidate is stale and invalid.

## Validation and state selection

A validator checks limits and exact fields, canonical lowercase encodings,
trusted round data, the complete header, network bits, header hash, share proof,
block-candidate marker, work identifier, and share identifier. It then requires
one root, unique share and work identifiers, existing parents, consecutive
sequences, and valid round transitions.

Every accepted share contributes two work units. The selected tip has the most
accumulated work; equal work selects the numerically lowest share identifier.
The canonical path is reconstructed from that tip. The final two shares are
excluded from settlement, and claims are grouped by payout script over the last
four remaining shares. These claims are deterministic accounting output only;
the profile does not spend coins.

## Frozen adversarial corpus

| Scenario | Expected result |
| --- | --- |
| `valid_linear_chain` | Accept a normal linked history |
| `longer_competing_fork` | Select the branch with more accumulated work |
| `equal_work_tie_break` | Select the lowest share identifier |
| `delayed_order_reconstruction` | Reconstruct the same state from reordered input |
| `restart_reconstruction` | Reconstruct the same state after restart |
| `unknown_parent` | Reject an absent parent |
| `miner_supplied_share_target` | Reject a miner-chosen target, even when rehashed |
| `fabricated_network_bits` | Reject substituted block difficulty |
| `untrusted_round_context` | Reject a round absent from the trusted table |
| `proof_above_share_target` | Reject insufficient proof |
| `duplicate_share` | Reject a repeated share identifier |
| `proof_reassigned_to_other_payout` | Reject one proof credited twice |
| `invalid_parent_sequence` | Reject a nonconsecutive sequence |
| `malformed_header` | Reject a header that is not exactly 80 bytes |
| `stale_extension_after_block` | Reject continuation of a completed round |

The checked corpus is
[`contrib/mining_autonomy/vectors/sharechain_v0.json`](../contrib/mining_autonomy/vectors/sharechain_v0.json).
Its top-level commitment detects changes to scenario contents.

## Reproduce the evidence

The reference generator and validator is `sharechain_v0.py`. The independent
validator imports no reference code and separately implements parsing, proof
checks, graph selection, finality, and payout grouping.

```bash
python3 contrib/mining_autonomy/sharechain_v0.py --check
python3 contrib/mining_autonomy/independent_sharechain_v0.py --check
python3 -m unittest discover -s test/mining_autonomy -p 'test_sharechain_v0.py' -v
```

Regenerate the frozen corpus only when intentionally revising this version:

```bash
python3 contrib/mining_autonomy/sharechain_v0.py --write
```

CI runs both validators inside the existing mining-autonomy job and retains the
independent report with the existing mining interoperability evidence.

## What remains before a public sharechain

The next bounded experiment is authenticated synchronization among three
independent processes. It must bound orphan memory and message sizes and test
partitions, delayed and selective relay, equivocation, restart recovery, and
peer disagreement. Later work must address peer discovery, Sybil and eclipse
resistance, payout maturity and reorganization economics, payout privacy,
real-node round sourcing, and independently operated public infrastructure.

Until those properties are implemented and attacked, the Template Autonomy
research gate remains **OPEN**.
