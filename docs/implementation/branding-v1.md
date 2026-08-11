# Soveroot Branding v1

Status: Adopted engineering identity; formal legal clearance pending

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

Renamed manual pages are intentionally not installed in this milestone because the inherited pages still document the old command names. Correct Soveroot manual pages must be produced before release packaging is enabled.

## Deliberately deferred identifiers

This branding milestone does not change consensus-critical or network-separation values. The following remain unchanged until a dedicated, reviewed migration defines compatibility and test vectors:

- configuration filename and base data-directory convention;
- the `dcp-labnet` on-disk network directory;
- the `dcprt` labnet address human-readable prefix;
- labnet message magic, ports, genesis block, and genesis timestamp text;
- protocol namespace strings and the labnet chain selector;
- names of inherited auxiliary tools, libraries, GUI components, and packages.

Changing any wire, address, or genesis identifier is a protocol change, not a cosmetic rename. It must remain visibly separate from branding work.

## Naming assurance

The Soveroot name passed a preliminary engineering collision search. That search is not trademark or legal clearance. No release should represent the name as legally cleared until a qualified review is complete.
