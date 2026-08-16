# Soveroot Branding v1

Status: Adopted engineering identity and CLI manual milestone; formal legal clearance pending

## Public names

| Surface | Name |
| --- | --- |
| Protocol and reference implementation | Soveroot |
| Node daemon | `sovrd` |
| RPC command-line client | `sovr-cli` |
| Ticker | Unassigned |

The short executable names are intended to be easy to type without making the protocol name cryptic in documentation or user interfaces.

## Upstream-maintenance boundary

The built daemon and RPC client are named `sovrd` and `sovr-cli`. Their internal CMake target names remain `bitcoind` and `bitcoin-cli` for now. Keeping those internal identifiers stable reduces unnecessary conflicts when reviewing and porting changes from the pinned Bitcoin Core upstream.

The inherited `bitcoin` wrapper remains an internal compatibility surface, but its monolithic node and RPC commands launch the Soveroot executable names.

The public daemon and RPC client now install `sovrd(1)` and `sovr-cli(1)` manual pages under the same names users execute. The manual generator follows the built output names instead of looking for nonexistent `bitcoind` and `bitcoin-cli` binaries. CMake keeps the inherited internal target names but maps each target to its public manual explicitly, and configuration fails if a declared manual is missing.

Both manuals fail closed in their examples and safety text: they require explicit `-chain=labnet`, state that labnet has no monetary value, and state that the proposed proof-of-work candidate is not in consensus. The RPC client now applies the same chain-isolation interlock as the daemon, preventing `sovr-cli` from controlling an inherited Bitcoin-network endpoint under a Soveroot name.

The inherited auxiliary tools keep their upstream names and manuals in this milestone. Production release packaging remains blocked by the broader readiness gates, data-path migration, legal review, and independent consensus research; installing accurate daemon and CLI manuals does not make the software production-ready.

## Deliberately deferred identifiers

This branding milestone does not change consensus-critical or network-separation values. The following remain unchanged until a dedicated, reviewed migration defines compatibility and test vectors:

- configuration filename and base data-directory convention (the new manuals disclose the inherited `bitcoin.conf` filename rather than hiding it);
- the `dcp-labnet` on-disk network directory;
- the `dcprt` labnet address human-readable prefix;
- labnet message magic, ports, genesis block, and genesis timestamp text;
- protocol namespace strings and the labnet chain selector;
- names of inherited auxiliary tools, libraries, GUI components, and packages.

Changing any wire, address, or genesis identifier is a protocol change, not a cosmetic rename. It must remain visibly separate from branding work.

## Naming assurance

The Soveroot name passed a preliminary engineering collision search. That search is not trademark or legal clearance. No release should represent the name as legally cleared until a qualified review is complete.
