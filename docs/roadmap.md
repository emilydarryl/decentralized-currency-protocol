# Soveroot Public Roadmap

Status: **WORKING DESIGN; PRIVATE LABNET ONLY; NOT SAFE FOR MONETARY USE**

Soveroot advances by published evidence and review, not by calendar promises. A milestone is complete only when its exit criteria are supported by reproducible artifacts. Favorable and unfavorable results remain public.

The [decision and research ledger](research-ledger.md) is the source of truth for current decisions, evidence, and open gates. The [protocol specification](protocol-specification.md) defines the proposed architecture. This roadmap is the shorter public view of how that work fits together.

## Current position

Soveroot is between the research-freeze and consensus-laboratory phases. The Bitcoin-derived node runs an isolated private `labnet`, but the proposed proof of work remains separate research code and is not part of block consensus. There is no public testnet, production network, ticker, or asset with monetary value.

Completed foundations include:

- an isolated `labnet` identity that does not start inherited Bitcoin networks;
- two-node CI coverage for explicit peering, mining, CLI access, and a test-only wallet transfer;
- fail-closed `sovrd` and `sovr-cli` operation unless `-chain=labnet` is selected;
- a byte-level v1 proof-of-work research candidate with independent Python and C++ agreement on fixed vectors;
- published reduced-memory attack models, including unfavorable and incomplete results; and
- a public external-attack challenge, independent-research call, and evaluator runbook.

These are engineering and research milestones. They do not establish memory hardness, hardware fairness, production safety, anonymity, or mainnet readiness.

## Milestones

| Milestone | State | Exit criteria |
| --- | --- | --- |
| 0. Isolated laboratory | **In progress** | Finish the inherited-assumptions audit, pin every production-relevant upstream revision, and keep automated network-confusion tests passing. |
| 1. Proof-of-work evidence | **Research blocker** | Close every frozen PoW evaluation gate, obtain independent attack and hardware review, and select or reject the candidate construction without weakening thresholds after seeing results. |
| 2. Consensus core | **Blocked by Milestone 1 and open protocol parameters** | Freeze canonical serialization, header and difficulty rules, issuance constants, resource limits, and post-quantum authorization parameters; produce shared vectors and two interoperable minimal validators. |
| 3. Public testnet | **Not launched** | Run the consensus core with P2P networking, post-quantum test wallets, fail-closed broadcasting, miner-created templates, reproducible builds, and adversarial network tests. Test coins have no monetary value. |
| 4. Mining and agent testnet | **Blocked by Milestone 3** | Demonstrate interoperable Job Declaration, direct block publication, decentralized share accounting, noncustodial payouts, capability wallets, mandates, receipts, and automated attack simulations. |
| 5. Privacy research network | **Research-only** | Test post-quantum receiving schemes and any shielded construction separately, with supply auditability and node-resource measurements. Unreviewed privacy code does not enter mainnet. |
| 6. Mainnet readiness review | **Not eligible** | Close every README blocker, complete independent audits, operate multiple interoperable clients, reproduce builds, simulate activation failures, and publish all remaining risks before any launch decision. |

## Immediate public deliverables

### 1. Independent reduced-memory attack

Obtain and review a genuinely independent implementation of the frozen [external attack challenge](pow-v1-external-attack-challenge.md). The submission must pass qualification vectors, disclose every memory allocation and unit of work, freeze its source before fresh cases are assigned, and undergo conflict and accounting review.

No submission, or many failed submissions, would still not prove memory hardness. If an eligible attacker completes the workload and emits canonical proofs, measure its elapsed time and resident memory on controlled physical computers.

### 2. Reproducible hardware evidence

Expand testing beyond shared-runner software screens:

- determinism vectors across at least three CPU architectures;
- unbiased seed-variance and low-cost verifier measurements;
- optimized CPU and two-ecosystem GPU comparisons;
- independently reviewed FPGA and ASIC cost models; and
- reversible-circuit, quantum-memory, and economic first-mover analysis.

The candidate does not advance merely because one attacker is slow or one hardware class performs favorably.

### 3. Mining-autonomy prototype

Build an end-to-end test profile in which miners construct their own block templates, use authenticated Stratum V2 Job Declaration for work coordination, publish valid blocks directly, and can switch away from a coordinator that rejects custom jobs. Test a P2Pool-like share system without creating a second centralized consensus authority.

This is an official mining-software profile, not a block-consensus claim. Nodes cannot verify which off-chain transport or real-world organization produced a proof of work.

## Research gates that remain open

The current PoW dashboard leaves all mandatory gates open:

- determinism and seed variance;
- verifier cost on declared low-cost systems;
- time-memory tradeoffs;
- facility-scale amortization;
- optimized GPU, FPGA, and ASIC comparisons;
- quantum concentration analysis; and
- interoperable template autonomy.

The exact evidence gap for each gate is maintained in the [research ledger](research-ledger.md#mandatory-pow-gate-dashboard) and machine-readable [`research_status_v0.json`](../contrib/pow_research/research_status_v0.json).

## Mainnet blockers

The complete, authoritative blocker list remains in the [project README](../README.md#mainnet-blockers). It includes proof of work, resource limits, serialization, difficulty adjustment, issuance, post-quantum performance, decentralized share accounting, receiving-address design, privacy feasibility, independent implementations, upstream provenance, network isolation, and activation simulations.

Passing a research gate does not silently change consensus. Any consensus candidate still requires a separate specification, security review, testnet deployment, and explicit user adoption under the documented [upgrade and activation process](upgrade-activation.md).

## How to participate

- Read [Mining Decentralization in Plain English](mining-decentralization-in-plain-english.md) for the nontechnical design and evidence summary.
- Submit a different reduced-memory strategy or volunteer as an evaluator through the [independent research call](pow-v1-independent-research-call.md).
- Reproduce published measurements from the [research-results index](research-results/README.md).
- Report favorable, unfavorable, failed, invalid, and ineligible results with the same evidence standard.

There is currently no bounty, token reward, public mining program, or mainnet launch date.
