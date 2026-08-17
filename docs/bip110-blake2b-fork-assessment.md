# BIP110 and BLAKE2b Fork Assessment

Status: **DESIGN DECISION RECORD; EXTERNAL FORK OBSERVATION; NO MAINNET AUTHORIZATION**

Evidence cutoff: 2026-08-17

## Executive decision

Soveroot will remain an independent new chain derived from a pinned Bitcoin Core codebase. It will not inherit Bitcoin's live chain, UTXO set, ticker, social consensus, or a proposed BIP110 successor chain.

The project may reuse ideas and individually reviewed code from Bitcoin Knots and BIP110, but it will not merge either project wholesale. The reduced-data objective is compatible with Soveroot's affordable-validation goal. BIP110's exact rules are not directly compatible with the proposed post-quantum transaction formats and must not be copied verbatim.

Soveroot will also keep the pinned Bitcoin Core v31 foundation rather than downgrade to v29. The controversial OP_RETURN change entered Core v30 as a default transaction relay and mining-policy change, not as a rule making those transactions newly valid in consensus. Starting from v29 would therefore preserve an older default without preventing a miner from placing the same consensus-valid data in a block. Soveroot will instead replace the unwanted policy explicitly and define its own reduced-data consensus rules from genesis.

Luke Dashjr's August 11, 2026 public selection of BLAKE2b is evidence that a separate proof-of-work fork is being pursued. It is not, by itself, a proof-of-work specification, security review, implementation release, activation plan, or demonstration of economic adoption. Soveroot will not select BLAKE2b merely to follow or race that proposal.

## Scope and source boundary

This assessment separates three things that are easily conflated:

1. **Bitcoin Core** is Soveroot's pinned implementation foundation.
2. **BIP110/RDTS** specifies a temporary Bitcoin soft fork that restricts several data-bearing transaction forms.
3. **The proposed BLAKE2b fork** is a separate, publicly discussed proof-of-work change following the BIP110 dispute.

Social-media posts establish what their authors publicly proposed. They do not substitute for immutable source revisions, canonical serialization, test vectors, independent implementations, deployment code, or measured adoption.

## Why the foundation remains Core v31

Bitcoin Core v30 increased the default `-datacarriersize` to 100,000 bytes and permitted multiple OP_RETURN outputs for transaction relay and mining. The release retained a configuration control, although setting it to 83 no longer exactly recreates the earlier single-output behavior because the limit is aggregate across potentially multiple outputs.

That change is important to Soveroot's policy review, but it is not a sound reason to freeze the entire implementation on v29:

- relay and block-template policy determines what an ordinary node forwards or proposes; it does not make a consensus-valid block invalid;
- a v29-derived node would still accept a large-data transaction included directly by a miner when Bitcoin consensus permits it;
- BIP110 proposed consensus restrictions precisely because policy alone cannot constrain a miner;
- downgrading the whole codebase would require separately identifying and backporting later security, correctness, performance, wallet, build, and testing improvements; and
- Soveroot is already replacing the network identity and consensus surface, so the rejected policy can be removed directly and tested explicitly.

The maintained design is therefore:

1. retain the immutable Core v31 source baseline;
2. record the v29 policy behavior as comparative evidence;
3. set strict Soveroot relay and block-template defaults;
4. make accepted monetary encodings explicit and type-aware in consensus from genesis; and
5. test that direct miner submission cannot bypass those consensus limits.

Version selection does not settle the data-policy question. The Soveroot specification and tests must settle it.

## What the August 11 thread establishes

The public thread used a commit-and-reveal mapping and Testnet4 block hashes to choose among candidate proof-of-work labels. The initial procedure was disrupted, the procedure was revised, and the final arithmetic selected BLAKE2b.

The commitment reduced one form of after-the-fact author choice, but it did not create an unmanipulable consensus ceremony. A miner able to generate candidate blocks may withhold an unfavorable result, and changing the procedure after disruption creates an additional governance dependency. This does not prove that the result was rigged. It means the ceremony is not cryptographic evidence that BLAKE2b is safe, decentralized, or broadly accepted.

The thread does not define:

- the exact BLAKE2b variant, input serialization, domain separation, or proof encoding;
- the fork height, chain identity, peer compatibility, or replay protection;
- the initial and continuing difficulty rules;
- the handling of the existing UTXO set and pre-fork signatures;
- canonical test vectors or independent compatible implementations;
- a reviewed wallet, miner, pool, or release artifact; or
- the economic actors that would recognize the resulting ledger.

Until those artifacts exist and are reviewed, the thread is a public design signal rather than a deployable protocol.

## BLAKE2b decentralization assessment

BLAKE2b is a well-known hash construction, but choosing a respected hash does not establish a decentralized proof of work. Proof-of-work centralization depends on the complete construction, hardware market, memory and bandwidth requirements, miner software, difficulty adjustment, pool protocol, energy economics, and supply chain.

Commercial mining hardware has already targeted Blake2B-family workloads. That fact does not prove that existing machines can mine an unspecified Bitcoin-derived BLAKE2b construction: input serialization and surrounding work can change compatibility. It does prove that the label "BLAKE2b" must not be described as ASIC-resistant or as an automatic reset to commodity mining.

Soveroot therefore records the following conclusions:

- The public selection ceremony is not a substitute for cryptanalysis or hardware modeling.
- Existing specialized hardware is a material incumbent-risk signal.
- A sudden PoW replacement may exchange one concentrated hardware population for another.
- A low-difficulty launch without a tested adjustment algorithm can be stalled, oscillated, or reorganized.
- Miner and pool decentralization still requires independent templates, direct publication, noncustodial accounting, coordinator switching, affordable validation, and an uncontested network identity.

## BIP110 rule assessment

The current BIP source describes seven temporary restrictions: a 34-byte ordinary output-script limit with an 83-byte OP_RETURN exception; 256-byte limits on data pushes and script-argument witness items; restrictions on undefined witness and Tapleaf versions; rejection of Taproot annexes; a 257-byte control-block limit; rejection of OP_SUCCESS opcodes; and rejection of executed OP_IF or OP_NOTIF in Tapscript. It also defines pre-activation UTXO grandfathering, miner-signaling deployment, and automatic expiry.

Soveroot's proposed ML-DSA-65 and SLH-DSA authorization objects are much larger than 256 bytes. A global 256-byte witness-item limit would therefore reject intended monetary transactions or force artificial fragmentation. The correct design question is not whether to permit arbitrary large byte strings everywhere. It is how to give each recognized monetary object a canonical, type-specific, resource-bounded encoding while rejecting unrecognized or unbounded payloads.

| BIP110 component | Soveroot decision | Reason and required work |
| --- | --- | --- |
| Reduced-data objective | **Adopt the objective** | Permanent node costs should be justified by monetary or protocol function rather than an unsupported general data-storage service. |
| Bitcoin Core implementation foundation | **Keep pinned v31** | Mature validation engineering is valuable. Replace the rejected v30-era data-carrier policy explicitly rather than downgrading the whole implementation; Bitcoin network identity and consensus values must still be replaced. |
| Knots and BIP110 source code | **Review patch by patch** | Record immutable upstream commits, consensus-versus-policy classification, local changes, tests, and license provenance. Do not create a second merge base. |
| 34-byte ordinary scriptPubKey limit | **Modify after serialization review** | A bounded commitment-sized output is desirable, but the exact limit must fit Soveroot's post-quantum address and recovery formats. |
| 83-byte OP_RETURN allowance | **Re-evaluate and explicitly specify** | Keep only a small, bounded commitment outlet if a demonstrated monetary or protocol need survives review. Do not inherit the number by tradition alone. |
| 256-byte push and witness-item limit | **Reject verbatim** | It conflicts with post-quantum signatures. Replace it with canonical type-aware limits and aggregate transaction and block budgets. |
| Undefined witness and Tapleaf restrictions | **Replace with Soveroot-native version rules** | Soveroot must define its own post-quantum spend namespace and fail-closed upgrade path rather than inherit Bitcoin's temporary freeze. |
| Annex, control-block, OP_SUCCESS, OP_IF, and OP_NOTIF restrictions | **Review individually** | Each rule needs a Soveroot use-case inventory, denial-of-service analysis, post-quantum compatibility check, and focused test vectors. |
| Pre-activation UTXO grandfathering | **Not applicable at genesis** | A new chain can make accepted formats valid from block zero and has no legacy Bitcoin outputs to protect. Future migrations still require explicit non-confiscation analysis. |
| One-year automatic expiry | **Reject as an inherited default** | Genesis rules must not silently change because a Bitcoin emergency deployment used a timer. Any sunset or replacement requires a Soveroot-specific rationale and activation review. |
| Miner-signaling and mandatory-lock-in deployment | **Do not inherit** | Genesis rules need no signaling. Later miner signals are readiness telemetry, not binding votes; forced activation requires a separately consented fork proposal. |
| BIP110 test vectors | **Reuse as negative and comparative inputs where licensed** | Ported vectors must be tied to the reviewed source revision, supplemented with Soveroot post-quantum formats, and never treated as complete coverage. |

## Independent-chain decision

The possibility that another fork launches first does not change Soveroot's ancestry decision. Launch order is not a security property.

Soveroot will:

- create a unique genesis block and never copy Bitcoin balances;
- use unique network magic, ports, address encodings, data directories, signing domains, seeds, and peer identity;
- add explicit cross-network rejection and replay tests;
- preserve the pinned Bitcoin Core source history and copyright attribution;
- port selected Knots or BIP110 work only through the provenance process;
- keep proof-of-work outside consensus until every mandatory research gate passes; and
- describe any external fork as an observed experiment, not as Soveroot's upstream network.

## Evidence to collect from an external launch

If a BIP110-associated BLAKE2b chain launches before Soveroot, the project should record evidence without promoting or attacking the chain. Useful measurements include:

1. published client source, tags, reproducible builds, and independent implementations;
2. exact proof-of-work serialization and compatibility with existing Blake2B hardware;
3. initial difficulty, block cadence, timestamp behavior, and reorganization history;
4. identifiable miner and coordinator concentration, while acknowledging attribution limits;
5. template authority, pool custody, payout construction, and direct-publication support;
6. peer count, reachable autonomous-system diversity, bootstrap dependencies, and eclipse resistance;
7. wallet separation, replay protection, address confusion, and exchange naming;
8. chainwork and economic-node behavior during competing histories; and
9. public incident reports, unfavorable test results, and corrective consensus changes.

These observations may invalidate Soveroot assumptions. They may not waive Soveroot's predeclared proof-of-work, privacy, post-quantum, resource, or activation gates.

## Required Soveroot follow-up

This assessment creates the following bounded work items:

1. Complete the candidate [Soveroot reduced-data profile](reduced-data-profile.md) with canonical encodings and benchmark-derived type-aware limits before consensus implementation.
2. Benchmark full ML-DSA-65 and candidate SLH-DSA transactions before setting witness, transaction, and block budgets.
3. Produce a BIP110 patch inventory against the pinned Knots source and classify every diff as consensus, policy, wallet, mining, test, or deployment code.
4. Port only reusable tests first; do not port activation or consensus code until the specification review closes.
5. Add cross-network and replay-safety vectors before any public-value network exists.
6. Maintain an external-fork observation log using reproducible measurements and immutable source links.
7. Keep the final PoW selection and difficulty formula as mainnet blockers.

## Plain-language conclusion

Soveroot is not trying to win a race to be the first Bitcoin fork after BIP110. It is building a separate monetary network that learns from Bitcoin, Knots, BIP110, and any new fork without inheriting their identity or copying unresolved decisions.

The useful part of BIP110 is the goal of keeping permanent node costs bounded and focused on money. The rules must be redesigned around Soveroot's larger post-quantum signatures. The useful part of the BLAKE2b announcement is the real-world experiment it may create. The announcement is not enough evidence to choose Soveroot's PoW.

## Primary sources

- [BIP110 source specification](https://github.com/bitcoin/bips/blob/master/bip-0110.mediawiki) — current source snapshot, exact rules, tradeoffs, deployment, and status.
- [Bitcoin Core v30 release notes](https://github.com/bitcoin/bitcoin/blob/master/doc/release-notes/release-notes-30.0.md) — documents the default 100,000-byte aggregate data-carrier limit and multiple OP_RETURN policy change.
- [Initial proof-of-work selection post](https://x.com/LukeDashjr/status/2087164051797192886) — commitment and original Testnet4 procedure.
- [Public report that the first procedure was disrupted](https://x.com/LukeDashjr/status/2087183652555817033).
- [Revised selection criteria](https://x.com/LukeDashjr/status/2087223637271052452).
- [Final BLAKE2b arithmetic post](https://x.com/LukeDashjr/status/2087224739265687685).
- [Bitmain algorithm and miner table](https://support.bitmain.com/hc/en-us/articles/4414648885273-Algorithms-and-Corresponding-ANTMINERs) — evidence that commercial Blake2B-family ASIC hardware has existed; not proof of compatibility with an unspecified fork.
- [NIST FIPS 204](https://csrc.nist.gov/pubs/fips/204/final) — ML-DSA standard.
- [NIST FIPS 205](https://csrc.nist.gov/pubs/fips/205/final) — SLH-DSA standard.
