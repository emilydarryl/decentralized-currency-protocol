# Replicated share accounting and direct coinbase settlement on labnet

Status: **working private-labnet prototype; not a production pool or payment system**

## Plain-English summary

The earlier prototype used one bookkeeper. It could prove which wallet script
performed test work, but it could disappear or lie alone, and its claim did
not pay anyone.

This milestone runs two independent copies of that bookkeeper. Each keeps its
own receipt file. They exchange verified receipts, reject a proof that has been
relabelled for another worker or payout script, and compute the same ordered
payout plan. The miner refuses pooled settlement unless both available copies
return byte-for-byte identical plans.

The demonstration then places those payments directly in the newly mined
block's coinbase transaction. No pool wallet receives the block reward first,
so the test service never holds a payout key or the test coins.

Think of it as two bookkeepers comparing signed work slips before the cash
register pays each named envelope directly. It is a useful laboratory step,
not yet a decentralized public pool.

## Run the packaged demonstration

Start the [Soveroot Labnet Kit](labnet-kit.md), then run:

```bash
./soveroot-labnet share-settlement-demo
```

The helper performs four direct block publications:

1. replica A records work for wallet script A;
2. replica B records work for wallet script B;
3. replica B is stopped while mining and reporting to A continue;
4. B restarts, pulls its missing receipt, both replicas produce the same plan,
   and the miner publishes a coinbase paying both scripts directly.

The command fails unless the replicas converge byte for byte, the recovering
replica adds at least one missing receipt, both payout plans match, the planned
values exactly conserve the current coinbase value, and the decoded on-chain
coinbase outputs exactly match the agreed plan.

## Security properties exercised

- Every imported receipt is revalidated from its 80-byte header and proof.
- A `work_id_sha256` binds one header and nonce independently of the claimed
  worker or payout script. The same proof cannot be counted under a new owner.
- Receipt sets and payout plans have deterministic SHA-256 commitments.
- Payout outputs are unique, canonically ordered, and at least 546 satoshis.
- The miner requires at least two distinct loopback replica endpoints and
  fails closed if one is unavailable or their complete plans disagree.
- The miner constructs and submits the multi-output coinbase itself.
- The accounting replicas have no wallet key and no block-publication role.

Automated tests also substitute a payout script, omit an eligible receipt,
return conflicting replica plans, and make one replica unavailable. Each case
must fail instead of silently settling a different result.

The retained demo evidence additionally requires the three payout-eligible
receipt hashes to equal the three blocks directly published before settlement.
The accounting service itself is not connected to a node and does not prove
arbitrary submitted headers are part of a canonical chain. Production design
must add chain-aware validation without handing a coordinator new authority.

## Retained evidence

The demonstration writes `share-settlement-evidence.json` plus both ledgers,
receipt snapshots, payout plans, recovery response, miner logs, and the decoded
settlement block under a unique `share-settlement-demo.*` directory. CI runs
the same packaged command and uploads the validated JSON with the existing
Labnet Kit artifact.

## What this does not prove

These two replicas run on one test machine and reconcile by explicitly pulling
from a known peer. This does **not** provide:

- a globally ordered P2Pool-style sharechain;
- independent operators or public-network partition recovery;
- Sybil resistance, membership discovery, or eclipse protection;
- resistance to colluding accounting majorities, censorship, or withholding;
- mature variance, fee, maturity, reorganization, or dispute rules;
- chain-aware rejection of fabricated or stale standalone receipt histories;
- production authentication, privacy, availability, or post-quantum security;
- the final Soveroot proof of work or a coin with monetary value.

Direct coinbase outputs demonstrate noncustodial settlement mechanics. They do
not make the two local bookkeepers decentralized. The Template Autonomy gate
therefore remains open until independent implementations and operators can
maintain a reviewed share history under adversarial public-network conditions.

## Next bounded step

Specify a minimal sharechain entry and fork-choice rule, then build a third,
independently written replica that synchronizes over an authenticated test
network. Tests must cover competing histories, delayed and selectively relayed
shares, restart recovery, equivocation evidence, coinbase maturity, and
reorganizations without giving any coordinator custody or publication power.
