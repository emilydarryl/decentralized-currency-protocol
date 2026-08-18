# Independent Soveroot labnet miner

This crate is the second implementation required by issue #61. It was written
against the frozen `soveroot-sv2-jd-labnet-v0` profile and canonical vectors.
It does not import the Python reference miner, the `sv2-reference` crate, or
their block-construction, message-encoding, or message-parsing code.

Independence boundary:

- SV2 Job Declaration and Mining payloads are encoded and parsed manually in
  `src/wire.rs` from the published field order and primitive encodings.
- Coinbase, merkle, header, proof-of-work, and block serialization are
  independently implemented in `src/block.rs`.
- Node access uses only ordinary `sovr-cli -chain=labnet` RPC calls.
- The pinned upstream `binary_sv2`, `codec_sv2`, `network_helpers_sv2`, and
  `key-utils` crates are used only for the generic payload trait, Noise NX
  transport, encrypted framing, and pinned coordinator-key verification.
  Official message-structure crates are deliberately absent from `Cargo.toml`.

This is private-labnet research software. It inherits easy SHA256d labnet proof
of work, has no production-hardening claim, and must not be used with assets of
value.
