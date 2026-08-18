# Soveroot authenticated Stratum V2 / Job Declaration labnet profile v0

Status: **FROZEN TEST PROFILE; PRIVATE LABNET ONLY; NO PRODUCTION OR CONSENSUS CLAIM**

Profile identifier: `soveroot-sv2-jd-labnet-v0`

This document freezes the behavior that the next reference implementation and an independently written miner must reproduce. It is intentionally written before network code so an implementation cannot quietly redefine acceptance, rejection, or fallback behavior.

## 1. Upstream pin and interpretation

This profile is derived from the official [`stratum-mining/sv2-spec`](https://github.com/stratum-mining/sv2-spec) repository at commit [`066971c7c750eded11b57aecd4ecdbd6e722c631`](https://github.com/stratum-mining/sv2-spec/tree/066971c7c750eded11b57aecd4ecdbd6e722c631), retrieved 2026-08-18. The relevant pinned documents are:

- [protocol overview and framing](https://github.com/stratum-mining/sv2-spec/blob/066971c7c750eded11b57aecd4ecdbd6e722c631/03-Protocol-Overview.md);
- [Noise security and server authentication](https://github.com/stratum-mining/sv2-spec/blob/066971c7c750eded11b57aecd4ecdbd6e722c631/04-Protocol-Security.md);
- [Mining Protocol custom jobs](https://github.com/stratum-mining/sv2-spec/blob/066971c7c750eded11b57aecd4ecdbd6e722c631/05-Mining-Protocol.md);
- [Job Declaration Protocol](https://github.com/stratum-mining/sv2-spec/blob/066971c7c750eded11b57aecd4ecdbd6e722c631/06-Job-Declaration-Protocol.md); and
- [message-type assignments](https://github.com/stratum-mining/sv2-spec/blob/066971c7c750eded11b57aecd4ecdbd6e722c631/08-Message-Types.md).

An upstream change has no effect on this frozen profile until a new Soveroot profile version names a new commit, publishes new vectors, passes both implementations, and documents compatibility and security consequences.

The upstream specification makes authenticated encryption mandatory for remote upstream access and optional on a local network. Soveroot v0 is stricter: the Noise-authenticated transport is mandatory for every coordinator connection, including loopback labnet demonstrations.

## 2. Security boundary

This is an official mining-software profile, not a block-consensus rule. A validating node can verify the block but cannot prove:

- which Stratum version transported work;
- whether a miner and pool share ownership;
- whether one organization operates several coordinator identities; or
- whether a third-party miner followed this profile.

Software distributed under the Soveroot miner label must follow this profile. Consensus must not reject an otherwise valid block merely because its off-chain coordination transcript is absent.

The v0 reference path continues to use inherited easy SHA256d labnet proof of work. It does not integrate the experimental Soveroot proof-of-work candidate and creates no asset with monetary value.

## 3. Roles and control

| Role | v0 responsibility | Forbidden authority |
| --- | --- | --- |
| Miner and Job Declarator Client | Ask the miner's own node for a template, construct the complete candidate, declare it, solve it, and publish it directly | Must not accept a coordinator-created substitute under the same job identifier |
| Miner-owned node / Template Provider | Select transactions and independently validate and publish the completed block | Must not delegate block validity to the coordinator |
| Job Declarator Server | Authenticate as the configured coordinator, allocate tokens, and accept, reject, or request missing transactions | Must not become a prerequisite for direct mining or direct publication |
| Pool accounting service | Validate shares and calculate test accounting under a separately reviewed profile | Must not custody a mainnet-valued reward or control the miner's payout key in v0 |

The coordinator may refuse service. It cannot revoke the miner's ability to continue on the miner-created template through direct solo labnet publication.

## 4. Identities and key handling

### 4.1 Coordinator identity

The Job Declarator Server is the Noise responder. The miner pins the 32-byte secp256k1 authority public key through a configuration channel independent of the coordinator connection. The responder presents the upstream certificate structure binding its static Noise key to that authority.

The miner must verify:

1. the configured authority key exactly matches the expected coordinator;
2. the certificate signature and validity window;
3. the Noise NX transcript and every AEAD authentication tag; and
4. monotonic transport nonces within the session.

Authentication failure terminates that connection before any `SetupConnection` message. There is no trust-on-first-use mode, certificate bypass, plaintext retry, or automatic downgrade.

Authority signing keys should remain offline. Coordinator static responder keys and certificates are rotatable. Private keys must never appear in transcripts, logs, vectors, command-line arguments, or repository fixtures. The vector authority key is an obvious non-secret fixture and must never be deployed.

### 4.2 Miner identity

Pinned Noise NX authenticates the server, not the client. Soveroot must not mislabel the v0 connection as mutually cryptographically authenticated.

The miner sends the test-only `user_identifier` only inside the encrypted session and receives a coordinator-issued `mining_job_token`. Those values bind requests within that coordinator session; they are not proof of a real-world identity and are not consensus identities. A later profile may add a reviewed client-authentication extension, but v0 does not invent an incompatible wire field.

## 5. Transport, framing, and setup

- Ordered TCP is the v0 transport.
- The upstream Noise pattern is `Noise_NX_Secp256k1+EllSwift_ChaChaPoly_SHA256`.
- The clear Stratum frame is `extension_type: U16`, `msg_type: U8`, `msg_length: U24`, followed by the payload.
- Core messages use `extension_type = 0x0000`.
- Encrypted header and payload processing follows the pinned upstream security document.
- Plaintext payloads, unauthenticated local mode, legacy Stratum V1, unknown mandatory flags, and protocol versions other than `2` fail closed.
- `SetupConnection.protocol = 1` selects Job Declaration.
- `min_version = 2`, `max_version = 2`, and `DECLARE_TX_DATA` bit 0 must be offered by the miner.
- A coordinator response selecting a different version, clearing a required behavior, or proposing Stratum V1 is a downgrade failure.

The Job Declaration and Mining Protocol connections are logically separate even if one process owns both. Before `SetCustomMiningJob`, the mining side opens an extended channel and records its channel identifier. A Job Declaration token cannot be silently reused across a different authenticated coordinator identity.

## 6. Supported upstream subset

| Message | Type | v0 use |
| --- | --- | --- |
| `SetupConnection` | `0x00` | Negotiate Job Declaration protocol version 2 |
| `SetupConnection.Success` | `0x01` | Confirm exact supported version |
| `SetupConnection.Error` | `0x02` | Visible failure; enter direct fallback |
| `OpenExtendedMiningChannel` | `0x13` | Open the accounting/share channel for a custom job |
| `OpenExtendedMiningChannel.Success` | `0x14` | Bind a channel identifier |
| `OpenMiningChannel.Error` | `0x12` | Visible failure; enter direct fallback |
| `SetCustomMiningJob` | `0x22` | Associate the miner-created declaration with the mining channel |
| `SetCustomMiningJob.Success` | `0x23` | Coordinator acknowledges the custom job |
| `SetCustomMiningJob.Error` | `0x24` | Visible failure; enter direct fallback |
| `AllocateMiningJobToken` | `0x50` | Request a session-bound job token |
| `AllocateMiningJobToken.Success` | `0x51` | Return the bounded token and coinbase allowance |
| `ProvideMissingTransactions` | `0x55` | Request declared transaction data by index |
| `ProvideMissingTransactions.Success` | `0x56` | Supply only the requested transaction data |
| `DeclareMiningJob` | `0x57` | Declare the miner-created full template |
| `DeclareMiningJob.Success` | `0x58` | Accept the declared template |
| `DeclareMiningJob.Error` | `0x59` | Reject it visibly; enter direct fallback |

`PushSolution` is not the authoritative publication path in v0. A future implementation may mirror a solved block to the coordinator, but it must first or concurrently publish the exact completed block through the miner's own `sovr-cli -chain=labnet submitblock` path. Coordinator delivery cannot substitute for direct publication.

## 7. Miner-created template record

Before contacting a coordinator, the miner records this complete semantic template:

- `chain`, fixed to `labnet`;
- block `height`, `previous_block_hash`, `version`, compact `bits`, and `curtime`;
- `coinbase_value`, miner-controlled payout script, coinbase prefix, and coinbase suffix;
- ordered transaction identifiers and corresponding full transaction bytes;
- witness commitment when required; and
- `template_commitment_sha256`, computed over canonical JSON for the semantic labnet transcript.

The semantic commitment is a test and logging invariant, not an added consensus field or an upstream Stratum extension. Issue #60 must map these fields into the exact pinned upstream binary messages and prove the solved block is byte-for-byte derived from the committed miner template.

The coordinator may request missing transaction bytes allowed by the pinned full-template mode. It may not alter transaction order, payout script, previous block, version, time, target, coinbase parts, or template commitment under the same `job_id`.

## 8. Required state machine

The accepted path is:

1. miner creates and commits the full template;
2. miner authenticates the coordinator's Noise authority;
3. both sides negotiate Job Declaration version 2;
4. miner obtains a session-bound job token;
5. miner declares the full custom job;
6. coordinator accepts the declaration;
7. miner opens an extended mining channel;
8. coordinator accepts `SetCustomMiningJob` for that declaration;
9. miner solves the committed template; and
10. miner directly publishes it to the miner-owned labnet node.

Acceptance never transfers publication authority to the coordinator.

Every failure path must be visible in structured logs, close or quarantine the affected coordinator session, enter direct fallback without replacing the miner-created template, continue solving when the template remains current, and publish directly if a valid block is found.

| Event | Mandatory behavior |
| --- | --- |
| Noise certificate, transcript, or AEAD failure | Send no Stratum message; close; direct fallback |
| `SetupConnection.Error` or version/flag downgrade | Refuse downgrade; close; direct fallback |
| Token timeout | Mark request timed out; ignore any late token; direct fallback |
| Declaration rejection | Record exact error; do not mutate template; direct fallback |
| Disconnect or stall | Close session after the bounded timeout; direct fallback |
| Malformed length, token, field, or reply | Fail parsing without partial use; close; direct fallback |
| Replayed response or request mismatch | Ignore response, quarantine session, direct fallback |
| Conflicting state for one request, token, or job | Record equivocation evidence, quarantine session, direct fallback |
| Coordinator rejects shares for an accepted custom job | Stop sending it shares; retain direct publication and permit configured coordinator switching |

The reference timeout is 2,000 milliseconds in semantic vectors. Implementation timing may be configurable for tests, but an unbounded wait is forbidden.

## 9. Canonical semantic vectors

The checked corpus is [`contrib/mining_autonomy/vectors/sv2_job_declaration_profile_v0.json`](../contrib/mining_autonomy/vectors/sv2_job_declaration_profile_v0.json). It contains nine deterministic scenarios:

1. accepted custom job;
2. rejected custom job;
3. token timeout;
4. disconnect after declaration;
5. protocol downgrade;
6. malformed reply;
7. coordinator equivocation;
8. replayed acceptance; and
9. man-in-the-middle authentication failure.

Each scenario begins with a miner-created template and ends with direct `submitblock` publication of the same job and template commitment. Each failure scenario includes an explicit `direct_fallback` transition. The generator and validator are [`sv2_job_declaration_vectors.py`](../contrib/mining_autonomy/sv2_job_declaration_vectors.py).

These are canonical semantic state transcripts, not Noise ciphertext or complete SV2 binary vectors. They freeze observable behavior while issue #60 implements the pinned binary mapping. Issue #61 must independently encode and parse the future wire vectors rather than import the reference implementation.

Run:

```bash
python3 contrib/mining_autonomy/sv2_job_declaration_vectors.py --check
python3 -m unittest discover -s test/mining_autonomy -p 'test_*.py'
```

## 10. Threats and residual limits

- **MITM:** pinned authority verification and AEAD detect an unauthenticated intermediary. Compromise of the configured authority or signing process remains outside this transport defense.
- **Replay:** request identifiers, session-bound tokens, ordered transport nonces, and active-job state reject old replies. Reuse after reconnect is forbidden.
- **Censorship:** a coordinator can reject or stall; direct fallback and later coordinator switching reduce its leverage but cannot force a pool to pay.
- **Malformed jobs or replies:** exact lengths, canonical fields, and fail-closed parsing prevent partial acceptance. Parser vulnerabilities remain an implementation risk requiring fuzzing.
- **Equivocation:** deterministic transcripts expose conflicting responses observed by miners. They do not provide global proof that every miner saw the same state.
- **Template substitution:** commitment matching and byte-level block reconstruction tests forbid silent coordinator replacement in official software. Consensus cannot prove how third-party software obtained its template.
- **Traffic analysis and denial of service:** encryption hides contents, not endpoints, timing, volume, or availability.
- **Classical authentication:** the pinned upstream Noise certificate uses secp256k1 and BIP340. It is not post-quantum authentication. This private-labnet profile must be replaced or wrapped by a separately reviewed cryptographically agile construction before any production claim.
- **Accounting and payouts:** v0 does not define decentralized accounting, noncustodial payouts, or payout dispute resolution.

## 11. Exit and change rules

This profile milestone is complete when the document, generator, checked corpus, tests, roadmap, and research ledger agree. It does not close the Template Autonomy gate.

The next milestone implements the reference accepted path and same-process direct fallback. After that, an independently written miner must reproduce the protocol without reusing the reference parser, encoder, or block builder. Adversarial coordinator switching and noncustodial payout work remain separate gates.
