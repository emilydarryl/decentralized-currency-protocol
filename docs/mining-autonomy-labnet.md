# Mining autonomy on labnet

Status: **working labnet prototype; not production mining**

## The short version

In ordinary pooled mining, a pool can choose the transactions and build the
block while individual miners merely search for a winning hash. That gives the
pool operator influence beyond calculating payouts.

This prototype moves the first of those powers back to the miner. A separate
program asks the miner's own Soveroot node for its candidate transactions,
builds the complete block outside the daemon, performs the easy labnet proof
of work itself, and publishes the winning block directly to the node.

No pool coordinator participates in this path. If a future accounting
coordinator disappears, the intended design is for mining and direct block
publication to continue. This prototype proves the direct solo path only; the
coordinator and its failure test have not been built yet.

## What is implemented

The external miner in
`contrib/mining_autonomy/autonomous_labnet_miner.py` performs this sequence:

1. It explicitly connects to `chain=labnet` and stops if the node reports any
   other chain.
2. It obtains a payout script from the miner's wallet.
3. It requests a SegWit-aware block template from the miner's own node.
4. It independently creates the coinbase, includes every transaction in that
   template, calculates the Merkle root, and serializes the block.
5. It searches the nonce locally using labnet's inherited SHA256d development
   proof of work.
6. It submits the completed block directly and checks that the node adopted
   the exact block hash it found.

The daemon's convenient `generatetoaddress` RPC is not used by this autonomy
demonstration. The distinction matters: the separate miner, rather than the
node or a pool, performs block construction and proof of work.

## Try it without mining jargon

Download and start the [Soveroot Labnet Kit](labnet-kit.md), then run:

```bash
./soveroot-labnet autonomy-demo
```

Success includes output resembling:

```text
Autonomous external block accepted: <block hash>
No pool coordinator was used: the external miner built and published this block directly.
```

Labnet coins have no value. The node listens only on the local machine, and
this experiment should never be pointed at assets or secrets of real value.

## What this does and does not prove

A successful run proves that this implementation can build, solve, submit,
and validate one labnet block outside the node daemon without a mining pool.
Automated CI repeats the same packaged demonstration on every pull request.

It does **not** yet prove:

- interoperability between two independently written mining programs;
- Stratum V2 or Job Declaration support;
- decentralized share accounting or noncustodial pool payouts;
- that mining continues after a real coordinator is killed;
- resistance to block withholding or payout manipulation;
- that Soveroot's experimental proof of work is safe or selected;
- production consensus, economic decentralization, or mainnet readiness.

The research ledger therefore keeps the Template Autonomy gate open.

## Next engineering step

The next bounded milestone is a coordinator boundary test. The miner should be
able to send shares to an optional accounting process without giving that
process control over the block template or publication. CI should then kill
the coordinator and prove that the miner still produces and directly submits
a valid block. Stratum V2 and Job Declaration interoperability follow that
local failure proof; their names alone would not establish autonomy.
