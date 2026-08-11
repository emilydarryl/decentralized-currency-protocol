# Labnet Identity v1

Status: Non-production consensus laboratory

Labnet is the first independently identified network in this repository. It is
for deterministic local and manually connected development only. It has no
monetary value, no automatic peer discovery, and is not the future public
testnet or mainnet.

## Selection and isolation

Start labnet explicitly with:

```text
-chain=labnet
```

Application initialization rejects Bitcoin mainnet, testnet3, testnet4,
signet, and Bitcoin regtest. Their constructors remain available only to the
inherited low-level regression suite and cross-network negative tests.

## Identity constants

| Surface | Labnet v1 value |
| --- | --- |
| Chain name | `labnet` |
| Network data directory | `dcp-labnet` |
| P2P message start | `d1 f5 f7 1d` |
| P2P port | `29444` |
| RPC port | `29443` |
| Bech32/Bech32m HRP | `dcprt` |
| Base58 public-key version | `9` |
| Base58 script version | `72` |
| Base58 secret-key version | `176` |
| Extended public-key version | `a4 8a af 01` |
| Extended secret-key version | `d9 2c 57 68` |
| DNS seeds | none |
| Fixed seeds | none |
| AssumeUTXO snapshots | none |
| Minimum chain work | zero |
| Default assumed-valid block | none |

The message-start and Base58 version bytes are the leading bytes of SHA-256
over the corresponding lowercase namespace label:

```text
decentralized-currency-protocol/labnet/p2p/v1
decentralized-currency-protocol/labnet/base58/<kind>/v1
```

The address versions are transitional laboratory encodings for inherited
classical scripts. They do not select or prejudge the production
post-quantum address format.

## Laboratory genesis

The labnet genesis is deliberately separate from the future fair-launch
genesis. Its coinbase output is a zero-value `OP_RETURN` and cannot represent a
premine.

| Field | Value |
| --- | --- |
| Timestamp text | `Decentralized Currency Protocol labnet genesis v1 - no monetary value` |
| Time | `1786406400` (2026-08-11 00:00:00 UTC) |
| Version | `1` |
| Difficulty bits | `207fffff` |
| Nonce | `0` |
| Reward | `0` |
| Merkle root | `6744cd92d9f1c63c0f74e4c38f907cf3a6c3a79874647a44240ff76e1b40a445` |
| Block hash | `5e0a0388d08796f24641a42cdcf87c7dc786b15a2b33e50b52dfb16d080bc28f` |

The production genesis remains blocked on the protocol specification's
committed future-public-event procedure and independent review.

## Test obligations

`chainparams_tests/labnet_identity_isolated_from_bitcoin` pins every value
above and proves that labnet's genesis, wire magic, P2P port, Bech32 HRP, and
all Base58/extended-key versions differ from each inherited Bitcoin network.
`argsman_tests/chain_isolation_interlock` proves labnet is the only chain that
application initialization may start.
