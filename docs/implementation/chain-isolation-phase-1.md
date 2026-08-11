# Chain Isolation Phase 1

Status: Temporary safety interlock

The imported Bitcoin Core baseline contains valid parameters for Bitcoin mainnet, testnet3, testnet4, and signet. Those parameters are retained temporarily for source comparison and low-level upstream tests, but this fork must not operate as a Bitcoin network client.

## Active rule

Network-capable application initialization accepts only the project-specific
`labnet`. Selecting the default chain, `main`, `test`, `testnet4`, `signet`, or
Bitcoin `regtest` fails before data directories are created and before node
networking starts.

The expected error is:

```text
Inherited Bitcoin networks, including Bitcoin regtest, are disabled in this experimental fork. Use -chain=labnet for isolated project development.
```

## Why parameters remain in the source

Deleting inherited parameters before replacements exist would make comparison harder and unnecessarily destroy upstream test coverage. The temporary interlock separates two concerns:

1. inherited constructors remain available to deterministic unit and differential tests; and
2. application startup cannot join any inherited Bitcoin network.

Labnet's identity is specified in `labnet-identity-v1.md`. It is a
non-production laboratory network and does not satisfy the removal criteria
for a public network.

## Removal criteria

The interlock may be replaced only when all project networks have:

- new genesis blocks produced by the committed launch procedure;
- unique chain and message identifiers;
- unique P2P and RPC ports;
- unique address and extended-key namespaces;
- empty project-controlled seed and checkpoint sets;
- project-specific data and configuration paths; and
- negative tests proving rejection of Bitcoin peers, addresses, messages, signatures, and chain data.

Removing or weakening the interlock in the same change that introduces new parameters is prohibited. New parameters must first pass review and test coverage while the guard remains active; enabling a project network is a later explicit change.
