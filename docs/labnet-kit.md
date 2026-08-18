# Soveroot Labnet Kit

The Soveroot Labnet Kit is a small, test-only bundle for running a local node,
creating wallets, mining blocks, and sending coins that have **no monetary
value**. It is intended to let non-specialists see the current software work
without implying that Soveroot is ready for public money.

## What is in the kit

- `bin/sovrd`: the Soveroot node daemon;
- `bin/sovr-cli`: the command-line wallet and node client;
- `soveroot-labnet`: a helper with safe local defaults;
- `libexec/autonomous_labnet_miner.py`: the external labnet block builder and
  miner used by `autonomy-demo`;
- `libexec/share_accounting_coordinator.py`: the loopback-only, accounting-only
  test service used by `coordinator-failure-demo` and `resilience-demo`;
- `libexec/build_resilience_evidence.py`: the fail-closed validator that retains
  coordinator, template, publication, and noncustodial-claim evidence;
- `libexec/share_replica_client.py` and
  `libexec/build_share_settlement_evidence.py`: the loopback reconciliation
  client and fail-closed direct-settlement evidence validator;
- `libexec/soveroot-sv2-reference`: the pinned official-library Noise and Job
  Declaration helper used by `job-declaration-demo`;
- `libexec/soveroot-sv2-independent-miner`: the separately written message and
  block implementation used by `interoperability-demo`;
- `libexec/run_interoperability.py` and its canonical vector: the byte-level
  cross-implementation gate;
- the `sovrd(1)` and `sovr-cli(1)` manual pages;
- `BUILD-INFO.txt`, this guide, and the MIT license.

The current bundle is built for **Ubuntu 24.04-compatible Linux on x86-64**.
Windows users can run it inside an Ubuntu 24.04 WSL environment. Native Windows
packaging is a later milestone. Python 3 is required for `autonomy-demo` and is
included by default in Ubuntu 24.04.

## Important limitations

- Labnet is isolated development infrastructure, not a public testnet or mainnet.
- The included wallet is the inherited Bitcoin Core descriptor wallet adapted
  to Soveroot's isolated labnet. It is not yet the final post-quantum,
  fail-closed anonymity wallet described by the protocol specification.
- Labnet mining currently uses inexpensive inherited development consensus.
  It does not activate the proposed Soveroot proof-of-work research candidate.
- The artifact is not a signed production release. Do not use it for assets,
  secrets, or transactions of real value.
- The helper binds RPC and peer listening to the local machine only. It does
  not create a publicly reachable node.

## Download and verify

1. Open the repository's **Actions** page on GitHub.
2. Open a successful **CI** run from the intended commit.
3. Download the `soveroot-labnet-kit-linux-x86_64-...` artifact.
4. Unzip the GitHub artifact. It contains a `.tar.gz` archive and a matching
   `.sha256` file.
5. In an Ubuntu terminal, enter the download directory and verify it:

   ```bash
   sha256sum -c soveroot-labnet-kit-linux-x86_64-*.tar.gz.sha256
   tar -xzf soveroot-labnet-kit-linux-x86_64-*.tar.gz
   cd soveroot-labnet-kit-linux-x86_64-*
   ```

The verification must say `OK`. Stop if it does not.
This checksum detects an incomplete or altered archive, but it is delivered in
the same development artifact and is not a production signature or independent
authentication guarantee.

## First test in plain English

Start the private local node:

```bash
./soveroot-labnet start
```

Run the complete demonstration:

```bash
./soveroot-labnet demo
```

The demonstration creates independent `miner` and `receiver` wallets, mines
enough blocks to make test coins spendable, sends one coin, mines its
confirmation, and prints the receiver's balance.

Run the separate mining-autonomy demonstration:

```bash
./soveroot-labnet autonomy-demo
```

In this second demonstration, a program outside the daemon obtains candidate
transactions from the miner's own node, constructs the full block, searches
for the labnet proof of work, and submits the winning block directly. No pool
coordinator is used. See [Mining autonomy on labnet](mining-autonomy-labnet.md)
for the plain-English boundary and the features that remain unfinished.

Prove that optional accounting cannot stop the miner:

```bash
./soveroot-labnet coordinator-failure-demo
```

The helper starts a local accounting process on `127.0.0.1:29445`, mines one
external block while verified work receipts are recorded, kills accounting,
then requires the same still-running miner process to directly publish another
block. It refuses success unless the chain advances by two and the receipt
ledger stops changing after shutdown.

Exercise authenticated Job Declaration and direct fallback:

```bash
./soveroot-labnet job-declaration-demo
```

The helper generates a disposable coordinator authority, declares the miner's
own first block template over authenticated Stratum V2, then kills the
coordinator. The same miner process must publish the first accepted job and a
second direct-fallback block through its own node. The demo fails unless both
block publications and both distinct declaration states are visible.

Exercise two independent implementations:

```bash
./soveroot-labnet interoperability-demo
```

The helper requires the reference and independent miners to agree byte for
byte on the published fixture. It then lets each miner declare, solve, and
directly publish one block against the reference coordinator. It fails unless
the chain advances by exactly two and retains a JSON evidence report.

Exercise hostile coordinators, switching, and noncustodial accounting:

```bash
./soveroot-labnet resilience-demo
```

One still-running miner offers each self-created template to the preferred
coordinator first. Across seven blocks, that coordinator accepts once and then
rejects, disconnects, stalls, returns malformed state, and proposes a protocol
downgrade. The miner retries the exact same committed template with the
alternate coordinator. Before the final block, both coordinators and the
accounting service are stopped; the miner must still solve and publish directly.
The demo also writes deterministic work claims grouped by the payout script
from the miner's wallet. Those claims neither hold nor transfer coins.

Reconcile two accounting replicas and settle their identical plan directly:

```bash
./soveroot-labnet share-settlement-demo
```

The helper gives different wallet scripts work on replicas A and B, reconciles
them, stops B, and mines another block while A remains available. After B
restarts it must import the missing receipt. Both replicas must then return the
same canonical payout plan before the miner creates a multi-output coinbase.
The demo decodes that block and fails unless its positive-value outputs exactly
match the plan. The replicas never hold a wallet key or receive the reward.
See [Replicated share accounting and direct coinbase settlement](replicated-share-settlement-labnet.md).

Inspect the node and loaded wallets:

```bash
./soveroot-labnet status
```

Mine additional blocks:

```bash
./soveroot-labnet mine 10
```

Use any available RPC command through the safety wrapper:

```bash
./soveroot-labnet cli getblockchaininfo
./soveroot-labnet cli -rpcwallet=miner getbalances
./soveroot-labnet cli -rpcwallet=receiver listtransactions
```

Stop the node cleanly:

```bash
./soveroot-labnet stop
```

## Files and network boundaries

By default, the helper stores its configuration, wallets, chain, and logs in:

```text
~/.soveroot-labnet-kit
```

The chain-specific data is kept below the isolated `dcp-labnet` directory.
RPC listens only on `127.0.0.1:29443`, and peer traffic listens only on
`127.0.0.1:29444`. The helper always supplies `-chain=labnet`; inherited
Bitcoin networks remain blocked by the daemon and client interlocks.
The helper rewrites its dedicated `soveroot-labnet.conf` with these safe local
settings each time it starts. Do not use that generated file for custom node
configuration. Because a fresh private chain has no fee history, the generated
labnet configuration uses a fallback fee rate of `0.0002` test coin per kvB.
This setting applies only to the test-only labnet data directory.
The accounting-failure demonstration temporarily uses loopback port `29445`
and retains its receipt ledger and log in a uniquely named
`accounting-failure-demo.*` directory below the same Labnet Kit data directory.
The Job Declaration demonstration uses loopback port `29446`, creates its
private authority key under a mode-`077` temporary
`job-declaration-demo.*` directory, and never prints that private key.
The interoperability demonstration reuses loopback port `29446` after the Job
Declaration demo has stopped and retains its logs and byte-level report in an
`interoperability-demo.*` directory.
The resilience demonstration uses primary coordinator port `29446`, alternate
coordinator port `29447`, and accounting port `29445`. It retains all logs, the
receipt ledger, payout claims, and `coordinator-resilience-evidence.json` in a
unique `resilience-demo.*` directory.
The share-settlement demonstration uses accounting replica ports `29445` and
`29448`. It retains both ledgers, canonical snapshots and plans, outage and
recovery logs, the decoded block, and `share-settlement-evidence.json` in a
unique `share-settlement-demo.*` directory.

To use a separate disposable data directory, set it before every command:

```bash
export SOVEROOT_LABNET_HOME="$PWD/my-labnet-data"
./soveroot-labnet start
```

The helper intentionally has no reset or delete command. Stop the node before
manually removing a disposable data directory, and verify the exact path first.

## What successful testing proves

A successful demonstration proves that this build can start an isolated
labnet node, create and use descriptor wallets, generate development blocks,
submit a wallet transaction, and confirm it locally. A successful
`autonomy-demo` additionally proves that the packaged external miner can build,
solve, and directly publish one inherited-PoW labnet block without a pool
coordinator. A successful `job-declaration-demo` proves one reference miner and
coordinator exchange the pinned encrypted Job Declaration/custom-job messages
and that coordinator loss cannot halt that miner. A successful
`interoperability-demo` proves two separately written payload and block
implementations agree on the canonical bytes and each directly publishes a
labnet block. A successful `resilience-demo` proves the same miner process
preserves its own template across an ordered coordinator list, directly
publishes during total coordinator loss, and emits deterministic accounting
claims tied to wallet payout scripts. A successful `share-settlement-demo`
proves two local receipt stores recover after one outage, return the identical
deterministic plan, and cause the miner to publish that plan as direct coinbase
outputs. A successful
`coordinator-failure-demo` proves the same packaged miner process advances the
chain after its local accounting process is killed. These demonstrations do
**not** prove a global decentralized sharechain, independent public operators,
or protection against colluding coordinators, Sybil identities, block withholding,
production consensus safety, privacy against network observers,
post-quantum security, economic decentralization, or readiness for real value.
