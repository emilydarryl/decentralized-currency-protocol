# Soveroot Reduced-Data Consensus Profile

Version: 0.1 candidate profile

Status: **NORMATIVE DESIGN CANDIDATE; NOT IMPLEMENTED; NOT MAINNET-AUTHORIZED**

Evidence cutoff: 2026-08-17

## 1. Purpose and boundary

Soveroot adopts the reduced-data objective: permanent chain storage and validation cost must serve a defined monetary or protocol function. The chain is not a general-purpose file store.

This profile converts that objective into rules compatible with post-quantum authorization. It replaces blanket Bitcoin-sized limits with canonical, type-aware objects and aggregate resource budgets. It does not select final byte or cost constants, authorize consensus implementation, or claim that arbitrary content can be identified by intent.

The terms MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, and MAY are normative for the candidate consensus or standard-profile class in which they appear. Exact encodings and constants remain blocked on the canonical serialization specification and reproducible benchmarks.

## 2. Plain-language summary

Bitcoin relay policy can discourage data, but a miner can still place a consensus-valid transaction directly in a block. Soveroot closes that gap by making the final reduced-data rules part of its new chain's validity rules from block zero. Every full node, including a node run by a small miner, rejects a block that breaks them regardless of how much hash power produced it.

The rule is not simply "nothing larger than 256 bytes." An ML-DSA-65 signature is 3,309 bytes, so that rule would break the intended post-quantum payment system. Instead, each large object must declare a recognized monetary type, use one exact canonical encoding, and count against transaction and block budgets. Unknown or malformed objects are invalid.

This prevents miners from bypassing the rules, but it cannot tell what an allowed commitment represents outside the chain. A short hash might commit to an invoice, a protocol proof, or a large file stored elsewhere. Consensus can bound its own bytes and work; it cannot reliably judge human intent.

## 3. Consensus invariants

The genesis reduced-data rules SHALL satisfy all of the following:

1. **Typed objects only.** Every consensus-interpreted field has an active type and version. Unrecognized mandatory types and versions fail closed.
2. **Canonical lengths.** Fixed-size cryptographic objects have exactly one permitted length. Variable-size objects have a type-specific maximum and a canonical length prefix.
3. **No generic payload path.** Version 0 exposes no unrestricted byte-string, annex, executable no-op, or script branch whose purpose is merely to carry arbitrary data.
4. **Aggregate accounting.** Limits apply to the whole transaction and block as well as individual fields. Splitting a payload among inputs, outputs, pushes, scripts, or transactions cannot evade the applicable budget.
5. **Multidimensional cost.** Serialized bytes, cryptographic verification, script work, temporary memory, and UTXO-state growth are metered separately. Passing one budget does not excuse failure of another.
6. **Early bounds.** A validator can compute structural and resource bounds before performing attacker-selected expensive cryptography.
7. **Consensus enforcement.** Direct block submission, private relay, custom miner configuration, and block-template construction cannot relax these limits.
8. **Determinism.** Validity depends only on canonical chain data and deterministic local computation, never an AI classifier, external content scanner, identity oracle, or claimed purpose.
9. **No implicit decompression.** Consensus version 0 accepts no generic compressed payload and performs no content decompression.
10. **Explicit upgrades.** A future object type requires a separately specified activation. Unknown versions are not silently treated as spendable or as generic data carriers.

## 4. Version 0 object registry

The canonical serialization specification SHALL assign fixed numeric identifiers and exact encodings. The registry below freezes semantic categories, not wire numbers or final limits.

| Object class | Version 0 purpose | Required treatment | Unresolved item |
| --- | --- | --- | --- |
| Spending-program commitment | Bind an output to an active monetary spending program | Fixed-size commitment; no embedded script or arbitrary metadata | Commitment primitive and exact length |
| ML-DSA-65 public-key reveal | Authorize a spend whose output committed to the key or program | Exactly 1,952 bytes under FIPS 204, plus a fixed type tag; key need not appear in every output | Commitment construction and key-reuse policy |
| ML-DSA-65 signature | Standard transaction authorization | Exactly 3,309 bytes under FIPS 204, plus a fixed type tag; verify only after structural admission | Verification cost weight and batch policy |
| SLH-DSA public-key reveal | Recovery or high-assurance authorization | Exact length implied by one selected FIPS 205 parameter identifier | Parameter set not selected |
| SLH-DSA signature | Recovery or high-assurance authorization | Exact length implied by one selected FIPS 205 parameter identifier; no arbitrary choice per signature | Parameter set and verification cost weight |
| Bounded program arguments | Supply values required by an active spending program | Type-specific count and length; no generic push operation | Version 0 program inventory |
| Protocol commitment | Commit to a narrowly specified off-chain protocol object when a demonstrated monetary need exists | At most one fixed-format commitment output per transaction; never executable; no free-form memo | Whether to include it, commitment type, and exact length |
| Upgrade envelope | Reserve a namespace for future consensus-defined object versions | Inactive at genesis; unknown versions fail closed and wallets do not create them | Activation and migration specification |

FIPS 205 defines 12 SLH-DSA parameter sets. Their signatures range from 7,856 to 49,856 bytes, while their public keys are 32, 48, or 64 bytes. This profile therefore cannot responsibly select a single witness limit until the recovery construction, parameter set, signing latency, verification cost, and low-cost-node benchmarks are fixed.

Public keys SHOULD normally be committed to by an output and revealed only when needed for authorization. This reduces persistent UTXO size, but the final construction must analyze key reuse, address privacy, recovery, and quantum-era exposure. It is not yet specified here.

## 5. Resource-accounting envelope

Every transaction and block SHALL be valid under independently enforced limits for at least:

- total canonical serialized bytes;
- bytes by object class;
- number of inputs, outputs, programs, signatures, and commitment outputs;
- ML-DSA verification cost units;
- SLH-DSA verification cost units by the single active parameter set;
- hashing and script cost units;
- temporary validation memory;
- newly created persistent UTXO bytes; and
- worst-case state reads and writes.

The final specification SHALL define a deterministic, overflow-safe cost function using integer arithmetic. It MUST charge objects before expensive validation when their type and length make that possible. Invalid signatures still consume the same pre-verification admission charge as valid signatures of the same declared type.

No ratio between bytes and verification work is frozen by this document. A single weight number is acceptable only if benchmarks demonstrate that it conservatively bounds every independent dimension; otherwise independent ceilings remain mandatory.

### 5.1 Benchmark gate for constants

Final transaction, block, and UTXO constants require reproducible measurements on every declared low-cost reference platform. The benchmark corpus MUST include:

- maximum valid and near-maximum invalid transactions and blocks;
- ML-DSA-65 verification with valid, invalid, and malformed inputs;
- each candidate SLH-DSA parameter set still under consideration;
- worst-case script, hash, memory, and state-access combinations;
- initial synchronization and reindexing under maximum permitted load;
- adversarial mixes designed to maximize cost per serialized byte; and
- at least two independent implementations before mainnet review.

The published result SHALL record hardware, operating system, compiler, library revisions, method, raw data, integrity hashes, and limitations. Constants MUST be chosen before public-value launch and may not be raised merely because existing miners prefer larger blocks.

## 6. Protocol-commitment outlet

Version 0 SHOULD omit a generic OP_RETURN-equivalent unless a concrete monetary or protocol need survives review. If included, it SHALL be a fixed-format protocol-commitment object rather than an arbitrary byte array.

The object MUST:

- carry a recognized commitment type and one fixed-length digest;
- appear no more than once per transaction;
- create no spendable UTXO;
- consume transaction and block commitment budgets; and
- have no script execution, annex, memo, MIME type, compression flag, or nested payload.

These rules bound on-chain cost. They do not prove what the digest commits to, prevent somebody from encoding meaning in ordinary payment choices, or justify content policing by consensus.

## 7. Mapping from BIP110

| BIP110 element | Soveroot version 0 treatment |
| --- | --- |
| 34-byte ordinary output-script limit | Replace with one fixed-size spending-program commitment format selected by the address and serialization review. |
| 83-byte OP_RETURN allowance | Do not inherit. Omit it or replace it with the single typed commitment in Section 6 after a use-case review. |
| 256-byte push and witness-item limits | Reject as a global rule. Use exact post-quantum object lengths, type-specific argument limits, and aggregate budgets. |
| Undefined witness and Tapleaf versions | Replace with a Soveroot-native registry. Inactive and unknown versions fail closed until an explicit activation defines them. |
| Taproot annex and control-block rules | Do not inherit automatically. Version 0 has no generic annex; any future control proof needs a dedicated bounded type. |
| OP_SUCCESS and executed conditional restrictions | Review while freezing the version 0 program inventory. No no-op or unreachable branch may become a data-carrier bypass. |
| Pre-activation UTXO grandfathering | Not needed for a new genesis. Future migrations require a separate non-confiscation and activation analysis. |
| Miner signaling and automatic expiry | Not inherited. Genesis rules start at block zero; later changes use Soveroot's conservative activation process. |

Reusable BIP110 vectors MAY enter the comparative test corpus only with immutable source provenance and license review. They are insufficient without Soveroot-native post-quantum and aggregate-budget cases.

## 8. Consensus and policy boundary

The reference node's relay, mempool, wallet, and block-template policy SHOULD be stricter than or equal to consensus. The official profile:

- does not inherit Bitcoin Core's 100,000-byte aggregate data-carrier default;
- does not create generic data-carrier transactions;
- rejects nonstandard objects before relay when inexpensive to determine;
- exposes no configuration option that makes a consensus-invalid object valid; and
- clearly distinguishes a policy rejection from a consensus-invalid result in diagnostics.

Policy protects node resources before blocks exist. Consensus is the security boundary against a miner that uses private submission, modified template software, or no public mempool at all.

## 9. Required anti-bypass tests

The implementation gate SHALL include at least these paired mempool and block-validation tests:

1. accept every exact valid boundary and reject the one-byte, one-count, and one-cost-unit excess;
2. reject unknown types, inactive versions, invalid parameter identifiers, noncanonical lengths, trailing bytes, duplicate fields, and alternate encodings;
3. reject a direct `submitblock` containing an object that relay policy already rejected for a consensus reason;
4. reject fragmentation of one disallowed payload across fields, arguments, outputs, or commitment objects when an aggregate limit is exceeded;
5. reject multiple protocol-commitment outputs and nested commitment carriers;
6. reject generic annexes, no-op carriers, unreachable-branch carriers, and unrecognized program arguments;
7. charge invalid cryptographic objects before verification and enforce block-level verifier budgets;
8. reject blocks that exceed serialized, verifier, script, memory, UTXO, or state-access limits independently;
9. produce identical results during initial validation, reindex, reorganization, and direct block import;
10. prove that miner, RPC, and policy configuration cannot relax consensus limits;
11. preserve valid monetary edge cases, including standard ML-DSA-65 and the selected SLH-DSA recovery paths; and
12. pass a shared differential corpus in at least two independent validators before mainnet review.

Every negative vector SHALL identify the exact rule violated. A test that only observes reference-node rejection is not sufficient evidence of a consensus rule unless direct block validation is exercised.

## 10. Activation and change discipline

The completed version 0 profile SHALL activate at the new genesis block. It has no Bitcoin UTXO grandfathering, miner lock-in phase, or automatic expiry.

Any later relaxation or new object type is a consensus change and MUST follow [upgrade-activation.md](upgrade-activation.md). Miner signaling is readiness telemetry, not authority. A tightening proposal must also analyze whether it confiscates or strands already valid outputs.

The following remain mainnet blockers:

1. canonical binary serialization and fixed object identifiers;
2. the spending-program commitment and receiving-address construction;
3. the exact SLH-DSA parameter set and recovery encoding;
4. the decision to omit or include the protocol-commitment outlet;
5. transaction, block, verification, memory, and UTXO constants derived from benchmarks;
6. the version 0 script/program inventory and static cost table;
7. reusable BIP110 patch and test-vector inventory with provenance;
8. shared conformance vectors and two independent implementations; and
9. security review covering denial of service, covert carriers, upgrade safety, and post-quantum failure modes.

No consensus patch should be merged merely because this candidate profile exists. The profile must first be completed with exact encodings and benchmark-derived constants, reviewed independently, and approved as part of the Phase 0 research freeze.

## 11. Primary sources

- [NIST FIPS 204, Module-Lattice-Based Digital Signature Standard](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf) — standardized ML-DSA encodings and Table 2 key and signature sizes.
- [NIST FIPS 205, Stateless Hash-Based Digital Signature Standard](https://nvlpubs.nist.gov/nistpubs/fips/nist.fips.205.pdf) — standardized SLH-DSA parameter sets and Table 2 key and signature sizes.
- [BIP110 source specification](https://github.com/bitcoin/bips/blob/master/bip-0110.mediawiki) — comparative reduced-data rules, deployment, and rationale.
- [Bitcoin Core v30 release notes](https://github.com/bitcoin/bitcoin/blob/master/doc/release-notes/release-notes-30.0.md) — relay and mining-policy changes for data-carrier transactions.
- [Soveroot BIP110 and BLAKE2b fork assessment](bip110-blake2b-fork-assessment.md) — project-specific adoption, modification, rejection, and follow-up decisions.
