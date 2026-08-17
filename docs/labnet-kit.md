# Soveroot Labnet Kit

The Soveroot Labnet Kit is a small, test-only bundle for running a local node,
creating wallets, mining blocks, and sending coins that have **no monetary
value**. It is intended to let non-specialists see the current software work
without implying that Soveroot is ready for public money.

## What is in the kit

- `bin/sovrd`: the Soveroot node daemon;
- `bin/sovr-cli`: the command-line wallet and node client;
- `soveroot-labnet`: a helper with safe local defaults;
- the `sovrd(1)` and `sovr-cli(1)` manual pages;
- `BUILD-INFO.txt`, this guide, and the MIT license.

The current bundle is built for **Ubuntu 24.04-compatible Linux on x86-64**.
Windows users can run it inside an Ubuntu 24.04 WSL environment. Native Windows
packaging is a later milestone.

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
submit a wallet transaction, and confirm it locally. It does **not** prove
production consensus safety, privacy against network observers,
post-quantum security, economic decentralization, or readiness for real value.
