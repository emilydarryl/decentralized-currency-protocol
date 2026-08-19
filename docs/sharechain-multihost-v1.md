# Multi-host share synchronization safety profile v1

Status: **working multi-address private-lab profile; not independently operated, Internet-exposed, or production-safe**

## Plain-English summary

The previous experiment ran three separate notebook programs on one computer.
They exchanged mining-share pages, recovered after disconnection, and agreed on
the winning history. However, each pair used one shared password. Either side
could create a message that looked like it came from the other, and there were
no rules limiting how many connections one address or identity could open.

This profile adds a safety layer before a future multi-computer trial:

- every test peer has a pinned public identity key;
- both ends sign fresh connection information and derive a different secret
  for that session;
- repeated, expired, altered, downgraded, or wrong-network connections fail;
- identities and network prefixes receive exact connection and traffic limits;
- a node requires peers from several address prefixes and operator labels and
  more than one transport label; and
- recovery after a long separation stops at a fixed work and storage budget.

The laboratory then runs the original three real processes on three distinct
loopback address prefixes. Their pairwise message keys come from the signed
session transcripts, and the original partition, selective-relay, restart,
replay, flood, and convergence attacks run again.

This is a safety-profile milestone, not proof of decentralization. All three
processes still run on one physical computer. Operator and transport labels are
configured claims, which a Sybil attacker can lie about. The listener is still
restricted to loopback. Separate network namespaces, independently operated
machines, hostile Internet routes, and external cryptographic review remain
required before issue #73 can close.

## Identity and session profile

The profile identifier is `soveroot-share-sync-multihost-lab-v1`, and every
hello binds `soveroot-labnet-v1`. An accepted session hello contains exactly:

- initiator or responder role;
- peer identifier and pinned identity public key;
- self-declared operator group, transport, and endpoint;
- fresh ephemeral public key and 32-byte nonce;
- issue and expiry ticks; and
- a signature over the complete canonical ASCII JSON body.

The readable laboratory implementation checks the published RFC 8032 Ed25519
and RFC 7748 X25519 vectors. Both signed hellos enter the transcript commitment.
The X25519 secret and transcript commitment enter HKDF-SHA256. Every subsequent
frame binds that transcript, both peer identifiers, a strictly increasing
sequence, an issue tick, and its payload under HMAC-SHA256.

Ed25519 and X25519 are classical algorithms. This profile is not
post-quantum-secure. The algorithm identifiers cannot be silently changed, but
a later profile must replace or hybridize identity, key agreement, and the KDF
with reviewed standardized post-quantum components. The Python formulas are
readable deterministic test references, not constant-time or audited
production cryptography.

Unlike the v0 pairwise MAC, a signed announcement can be checked by a third
party that knows the pinned public key. Two valid conflicting announcements by
one key for one slot form portable evidence. This proves only that the key made
both signatures. It does not identify a person, prove real-world ownership, or
trigger automatic slashing, payout loss, consensus punishment, or a ban.

Test fixture identity seeds are obvious deterministic values. They are not
deployment keys and must never be reused outside the laboratory.

## Frozen admission and recovery limits

| Resource | Limit |
| --- | ---: |
| Session hello | 32,768 bytes |
| Session frame | 131,072 bytes |
| Hello lifetime | 16 deterministic ticks |
| Session lifetime | 128 deterministic ticks |
| Active sessions | 16 |
| Sessions per pinned identity | 2 |
| Sessions per IPv4 `/24` or IPv6 `/48` | 4 |
| Handshake bucket per identity and prefix | 8 tokens |
| Handshake refill | 1 token per tick |
| Message bucket per identity | 64 tokens |
| Message refill | 4 tokens per tick |
| Remembered hello nonces | 256 |
| Local quarantines | 128 |
| Admission bucket records per bucket family | 512 |
| Peer candidates considered per selection | 128 |
| Quarantine duration | 32 ticks |
| Long-partition catch-up shares | 1,024 |
| Catch-up pages | 16 |
| Shares per catch-up page | 64 |
| Catch-up operations | 64 |

A frame costs one message token per started 4,096 bytes. Parsing size and cheap
profile checks occur before signatures, share validation, or storage. Admission
state—including buckets, replay nonces, quarantines, and active counts—has a
canonical restart snapshot. Limits are local denial-of-service controls and
never affect share validity, fork choice, payout weight, or base consensus.

## Peer diversity policy

The deterministic selector requires at least:

- three selected peers;
- three distinct IPv4 `/24` or IPv6 `/48` prefixes;
- three distinct configured operator groups; and
- two configured transport types.

It selects no more than one peer per prefix, one per operator group, and two per
transport. Persistent user anchors and a future discovery/rotation mechanism
remain outside this code.

These rules stop simple concentration mistakes and make a basic eclipse more
expensive. They are not Sybil resistance. One attacker can rent addresses,
invent operator labels, compromise transports, or control upstream routing.
The node must retain accumulated-work and full-data validation regardless of
how diverse peers appear.

## Deterministic evidence

Run:

```bash
python3 contrib/mining_autonomy/run_share_multihost_lab.py \
  --output build/share-sync-multihost-v1-evidence.json
```

The current run requires 37 checks, including:

- seven exact RFC Ed25519 and X25519 results;
- three matching pairwise signed-session derivations;
- wrong identity, wrong network, downgrade, expiry, signature alteration,
  replay, and transcript alteration rejection;
- exact identity, prefix, global connection, handshake-rate, message-rate, and
  frame-size boundaries plus one;
- persisted replay and quarantine state after restart;
- accepted diverse peer sets and rejected prefix/operator concentration;
- retention of honest alternate paths during concentrated churn;
- exact 1,024-share catch-up acceptance and 1,025-share refusal;
- portable signed equivocation evidence and tamper rejection; and
- all 13 earlier three-process share-sync attacks on three distinct listener
  address prefixes.

CI runs this inside the existing Ubuntu job and uploads its JSON in the existing
mining-interoperability artifact. It adds no job or matrix.

## What remains before issue #73 can close

- make the signed handshake and admission layer the live process boundary
  instead of a deterministic preflight that supplies per-run v0 frame keys;
- run the complete share exchange across separate Linux network namespaces or
  containers with distinct routed addresses;
- obtain independent machines, operators, networks, and jurisdictions;
- review constant-time production cryptography and a post-quantum hybrid;
- design safe peer-key distribution, rotation, revocation, and recovery;
- test malicious routing, NAT, packet loss, latency, bandwidth asymmetry,
  traffic analysis, and denial of service on controlled Internet hosts;
- test peer discovery and rotation without privileged seed or identity
  authorities; and
- specify mature payout settlement, coinbase maturity, and reorganization
  behavior separately.

Template Autonomy therefore remains **OPEN**. Passing this profile does not
create a public pool, production settlement network, consensus rule, final
proof of work, mainnet, ticker, or coin with monetary value.
