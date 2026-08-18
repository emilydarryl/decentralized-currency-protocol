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

No pool coordinator participates in the solo path. A second packaged
demonstration now adds an optional accounting-only coordinator, records a
miner's verified work, stops that coordinator process, and proves the same
still-running miner process builds and directly publishes the next block. Accounting failure is
visible to the miner but is not allowed to become a mining failure.

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
7. When configured, it sends best-effort, cryptographically checked work
   receipts to a loopback accounting process. Delivery failures are counted
   but cannot interrupt steps 1-6.

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

Then run the failure demonstration:

```bash
./soveroot-labnet coordinator-failure-demo
```

This starts the test accounting process and one external miner process. After
that miner's first block and receipt, the helper kills accounting while the
miner remains alive. The same process must publish a second block. The helper
checks that the chain advanced twice and that the ledger stopped changing.

Labnet coins have no value. The node listens only on the local machine, and
this experiment should never be pointed at assets or secrets of real value.

## What this does and does not prove

A successful run proves that this implementation can build, solve, submit,
and validate labnet blocks outside the node daemon without a mining pool. The
failure demonstration additionally proves that the same running miner process
continues after its optional accounting endpoint is killed. Automated CI repeats both packaged
demonstrations on every pull request.

It does **not** yet prove:

- interoperability between two independently written mining programs;
- Stratum V2 or Job Declaration support;
- decentralized share accounting or noncustodial pool payouts—the included
  coordinator is one local append-only test service, not a pool design;
- resilience to network partitions, malicious coordinators, forged payout
  records, or multiple competing coordinators;
- resistance to block withholding or payout manipulation;
- that Soveroot's experimental proof of work is safe or selected;
- production consensus, economic decentralization, or mainnet readiness.

The research ledger therefore keeps the Template Autonomy gate open.

## Next engineering step

The next bounded milestone is protocol interoperability: connect the
miner-created job path to an authenticated Stratum V2 and Job Declaration
profile without weakening the proven direct fallback. A second independently
written miner must then build compatible jobs and publish blocks. Noncustodial
payout accounting and adversarial coordinator-switching tests remain separate
requirements; adding a Stratum V2 label alone would not establish autonomy.
