# Independent miner interoperability on labnet

Status: **working private-labnet gate; not production mining**

## The result in plain English

Soveroot now has two separately written mining programs that read the same
published rules and produce the same protocol messages and block, byte for
byte. Both can connect to the authenticated test coordinator, declare a block
chosen by the miner, solve it, and publish it directly through the miner's own
node.

This matters because a test that uses only one program can repeat the same bug
on both sides. Agreement between independently written encoders, parsers, and
block builders is stronger evidence that the published profile is precise and
implementable. Any disagreement stops CI instead of selecting one program as
automatically correct.

It does not prove production security, decentralized payouts, resistance to
large mining facilities, or readiness for coins with value.

## Independence and provenance

The reference path uses the official Stratum V2 Rust message structures. The
second implementation is the standalone Rust crate in
`contrib/mining_autonomy/sv2-independent-miner/` and deliberately does not
import the Python reference miner, `sv2-reference`, or their parser, encoder,
coinbase, merkle, header, proof-of-work, or block-building code.

The independent miner manually implements the supported Job Declaration and
Mining payload encodings from the frozen profile. It uses pinned upstream
`binary_sv2`, `codec_sv2`, `network_helpers_sv2`, and `key-utils` crates only
for the generic payload trait, Noise NX, encrypted framing, and coordinator-key
authentication. It does not depend on the upstream Job Declaration,
common-message, or mining-message structure crates. Its node boundary is the
normal fail-closed
`sovr-cli -chain=labnet` interface.

## Reproducible evidence

The canonical fixture is
`contrib/mining_autonomy/vectors/sv2_interoperability_v0.json`. It fixes the
public test authority, candidate template, authentication transcript, clear
SV2 payloads, template commitment, solved header, and serialized block.

The comparison gate runs both binaries independently and writes a JSON
artifact containing their full reports:

```bash
python3 contrib/mining_autonomy/run_interoperability.py \
  --reference-helper build/sv2-reference/release/soveroot-sv2-reference \
  --independent-miner build/sv2-independent/release/soveroot-sv2-independent-miner \
  --reference-miner contrib/mining_autonomy/autonomous_labnet_miner.py \
  --fixture contrib/mining_autonomy/vectors/sv2_interoperability_v0.json \
  --output build/sv2-interoperability-evidence.json
```

CI fails unless these exact results agree:

- the authenticated authority and Noise transcript inputs;
- every supported clear SV2 message payload and type;
- the miner-created template commitment;
- the coinbase, header, nonce, hash, and complete block bytes; and
- the declared result for each required negative vector.

The live tests additionally connect the independent manual codec to the
reference coordinator. They require invalid authority authentication to fail
before any SV2 message, malformed lengths to fail closed, stale templates to
stop, duplicate state to be rejected, and rejected custom jobs to enter visible
direct fallback.

## Packaged demonstration

After downloading the Labnet Kit, run:

```bash
./soveroot-labnet interoperability-demo
```

The helper first repeats the offline byte comparison. It then starts one local
reference coordinator. The existing reference miner declares, solves, and
directly publishes one block. The standalone independent miner separately
declares, solves, and directly publishes the next block. Success requires the
chain to advance by exactly two and retains the byte-level evidence and logs.

## Remaining boundary

This closes the independent-implementation portion of the Template Autonomy
gate, not the entire gate. Noncustodial shared payouts, adversarial switching
among multiple coordinators, parser fuzzing, public-network testing, and the
final Soveroot proof of work remain unfinished. Labnet uses inherited easy
SHA256d development proof of work and its coins have no monetary value.
