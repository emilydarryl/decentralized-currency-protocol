# Noncustodial payout accounting and coordinator failover on labnet

Status: **working private-labnet prototype; claims are not money or settlement**

## The result in plain English

The same external miner can now keep its own block template while trying more
than one authenticated coordinator in a configured order. If the preferred
coordinator rejects the job, disconnects, stalls, returns malformed state, or
attempts a protocol downgrade, the miner offers the exact same committed job
to the next coordinator. If every coordinator is unavailable, it continues in
direct solo fallback and publishes through its own node.

The optional accounting service now turns verified work receipts into
deterministic claims tied to the payout script supplied by the miner's wallet.
It has no wallet, private key, coinbase authority, or block-publication path.
A valid claim therefore says, “this script earned this share of the verified
test work.” It does not move coins, promise a payment, or complete a production
payout network.

## Packaged demonstration

After starting the Labnet Kit, run:

```bash
./soveroot-labnet resilience-demo
```

One miner process builds and directly publishes seven consecutive blocks. The
primary authenticated coordinator follows a deterministic hostile sequence:

1. accept the first miner-created job;
2. reject the next valid custom job;
3. disconnect;
4. stall beyond the bounded timeout;
5. return mismatched state; and
6. select a downgraded protocol version.

For cases 2-6, the configured alternate coordinator accepts the unchanged
miner-created template. Before block 7, the helper stops both coordinators and
the accounting service. The same miner process records those failures, solves
the seventh template, and directly publishes it anyway.

The demonstration retains:

- the miner's structured event stream;
- primary, alternate, and accounting logs;
- an append-only, duplicate-rejecting work-receipt ledger;
- deterministic noncustodial claims grouped by payout script;
- start and final chain heights; and
- a canonical JSON evidence document that fails if a coordinator attempt or
  publication refers to anything other than the miner's committed template.

CI uploads that evidence with the existing Labnet Kit artifact from the same
single Linux job.

## Conflicting coordinator views

The test profile also maintains a shared view registry. If two miners receive
different coordinator-state commitments for the same coordinator identity and
the same template commitment, that coordinator is quarantined. Neither view is
allowed to replace the miner-created template, and direct fallback remains
available. This is deterministic local evidence, not a global proof that every
miner on a public network saw the same message.

## Payout-claim rules

Each accepted v2 receipt binds the verified 80-byte header to:

- `chain=labnet`;
- a bounded worker label;
- height and previous block hash;
- the miner-created template commitment;
- the miner wallet's payout script; and
- whether the header meets the declared block target.

The coordinator recalculates the hash and target, assigns a canonical receipt
identifier, rejects duplicates, and counts only target-valid receipts toward
claims. Claims are sorted by payout script and expose exact work numerators and
a common denominator. They contain no destination private key and authorize no
transaction.

## What remains open

This milestone demonstrates noncustodial **accounting**, ordered failover, and
direct publication under total coordinator loss. It does not yet demonstrate:

- a decentralized share chain or independently replicated accounting state;
- an on-chain or off-chain settlement transaction paying the claims;
- resistance to Sybil miners, block withholding, payout censorship, or a
  dishonest majority of accounting peers;
- public-network denial-of-service resistance or privacy; or
- the final Soveroot proof of work.

The Template Autonomy research gate therefore remains open for decentralized
settlement and adversarial public-network testing. Labnet coins have no value.
