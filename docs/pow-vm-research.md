# Soveroot Proof-of-Work VM Research Specification

Version: 0.1 research draft

Status: Candidate direction only; not approved for mainnet or consensus implementation

## 1. Objective

Soveroot is investigating a permanent, chain-specific proof-of-work virtual machine with deterministic workload variation and substantial memory-bandwidth demand.

The objective is not to make capital investment, specialization, ASICs, pools, or quantum advantage impossible. The objective is to:

- prevent immediate reuse of another chain's dominant fixed-function mining fleet;
- keep optimized commodity CPUs and GPUs economically relevant if benchmarks support that claim;
- increase the engineering cost and reduce the useful lifetime of a secret narrow-purpose advantage;
- preserve deterministic validation on affordable full-node hardware; and
- avoid governance-selected periodic algorithm changes.

## 2. Fixed algorithm, variable program

The consensus algorithm would permanently define:

- VM instruction semantics;
- program-generation rules;
- dataset and scratchpad construction;
- seed schedule;
- header commitment and nonce encoding;
- execution count and termination;
- result hashing and target comparison; and
- every verifier resource limit.

Programs would vary deterministically by epoch. This is not algorithm rotation: no person, foundation, miner, model, release, or external randomness service chooses an algorithm.

## 3. Candidate work pipeline

The research construction has five conceptual stages:

1. **Epoch seed:** derive a domain-separated seed from a sufficiently buried block committed before the target epoch.
2. **Program generation:** expand the seed into a canonical integer-only VM program.
3. **Memory initialization:** derive a read-only dataset and per-attempt scratchpad using the epoch seed.
4. **Execution:** execute a bounded number of instructions using the candidate header and nonce as input.
5. **Result:** domain-separate and hash the canonical VM output, then compare the result as an unsigned integer with the active difficulty target.

This document intentionally does not assign byte encodings or numeric constants. Doing so before profiling and cryptanalysis would create false precision.

## 4. Seed scheduling requirements

The final schedule MUST:

- reveal each seed far enough ahead for all implementations to prepare equivalent optimized code and datasets;
- use only authenticated chain data;
- derive the seed from a block buried deeply enough that ordinary reorganization does not change active work;
- specify behavior for a reorganization crossing the seed block;
- prevent the immediately preceding miner from cheaply grinding among many future programs;
- prevent indefinite precomputation; and
- avoid permanent checkpoints or subjective finality.

Candidate schedules MUST be simulated under selfish mining, withheld blocks, timestamp manipulation, epoch-boundary reorganizations, and temporary majority work.

## 5. VM requirements

The VM MUST be deterministic across architectures and languages. It MUST NOT depend on:

- floating-point behavior;
- undefined integer overflow;
- host endianness;
- wall-clock time;
- thread scheduling;
- network data;
- vendor drivers;
- trusted hardware; or
- model inference.

Every instruction requires exact bit-level semantics, fixed latency is not assumed, and all loops and memory accesses MUST be bounded by consensus constants.

The candidate instruction mix SHOULD exercise integer arithmetic, rotations, multiplication, dependent memory addressing, and unpredictable reads. Instructions included only to disadvantage a particular vendor are rejected unless they improve a measurable security property.

## 6. Memory-hardness requirements

The work function SHOULD make time-area and memory-bandwidth tradeoffs expensive enough that removing memory creates a material throughput penalty.

Research MUST measure:

- dataset and scratchpad sizes;
- random versus sequential bandwidth;
- cache sensitivity and recomputation tradeoffs;
- CPU and GPU energy per accepted work unit;
- FPGA on-chip and external-memory costs;
- estimated ASIC die area, memory interface, packaging, and energy;
- batch, parallel, and precomputation advantages; and
- light-verifier and initial-sync costs.

"Memory-hard" is not accepted as a qualitative label. A proposal must publish reproducible measurements and a defensible hardware cost model.

## 7. Verification budget

A full node verifies proof of work; it does not mine it. Verification MUST remain deterministic and denial-of-service resistant on the declared low-cost reference system.

The final design MUST publish:

- peak verifier memory;
- worst-case verification time;
- initialization and epoch-transition time;
- costs for validating competing headers during initial sync;
- cache-sharing rules across candidate chains; and
- limits preventing peers from forcing unbounded dataset creation.

A design that keeps mining accessible by requiring every validating node to allocate excessive memory is rejected. Cheap verification takes priority over an unproven claim of ASIC resistance.

## 8. Hardware-decentralization evaluation

No mainnet candidate proceeds without at least:

- two independent CPU implementations;
- optimized implementations for two major GPU ecosystems;
- an FPGA prototype or independently reviewed synthesis estimate;
- an independently reviewed candidate-ASIC cost model;
- open benchmark tooling and raw results; and
- testing on low-cost, midrange, and high-end consumer systems.

The report MUST distinguish pool concentration, hardware ownership, energy concentration, manufacturing concentration, and block-template authority. A favorable CPU-to-ASIC ratio does not prove decentralized mining.

The project SHOULD define a target maximum specialization advantage before benchmarking. Missing that target triggers redesign or rejection; the target MUST NOT be adjusted after results merely to approve a favored construction.

## 9. Quantum analysis

The work function MUST receive explicit analysis of:

- generic quantum search advantage;
- reversible circuit depth and qubit count;
- coherent and classical memory requirements;
- parallelization limits;
- the security margin of the result size; and
- effects of a temporary quantum first mover on difficulty and concentration.

Difficulty adjustment preserves average block timing; it does not distribute political or economic control. The protocol MUST NOT describe the PoW as quantum-proof.

## 10. Pool architecture is a separate control

Even an accessible PoW can centralize around payout variance and template control. Official Soveroot mining software therefore also requires:

- miner-created templates;
- authenticated Stratum V2 custom-job declaration or an equivalent successor;
- direct publication of discovered blocks;
- decentralized share accounting;
- noncustodial payouts;
- automatic fallback when custom jobs are rejected; and
- visible coordinator-concentration warnings.

These controls reduce what a large coordinator can command. They do not create a Sybil-vulnerable consensus cap on pool names.

## 11. Attack analysis

Before selection, the construction MUST be tested for:

- seed grinding and biased program selection;
- programs with accidentally weak or unusually fast execution paths;
- cross-epoch precomputation;
- dataset amortization by large facilities;
- time-memory and memory-bandwidth tradeoffs;
- header malleability and duplicate work;
- remote denial of service against verifiers;
- long-range and epoch-boundary reorganizations;
- selfish mining and block withholding;
- compiler, JIT, and architecture divergence; and
- hidden instruction or microarchitectural backdoors.

## 12. Rejection criteria

The candidate direction is rejected or redesigned if any of the following occurs:

- independent implementations disagree on valid work;
- verifier costs exceed the node resource budget;
- common CPUs or GPUs become economically irrelevant at launch estimates;
- seed control gives recent block producers a material private advantage;
- one facility can amortize initialization so strongly that variation increases concentration;
- a practical specialization estimate substantially exceeds the predeclared target;
- quantum analysis shows an unacceptable first-mover concentration risk; or
- the design requires trusted setup, vendor attestation, secret constants, or human-selected rotation.

## 13. Research phases

1. Specify a minimal deterministic VM and canonical interpreter.
2. Build a differential test-vector generator.
3. Sweep memory, program, and epoch parameters on commodity hardware.
4. Commission FPGA, ASIC, and reversible-circuit analysis.
5. Simulate seed manipulation, reorganizations, and hash-rate shocks.
6. Run the strongest surviving candidate on a disposable research network.
7. Freeze byte-level rules only after independent reproduction and public review.
8. Implement on labnet in a dedicated consensus PR only after explicit approval.

Until all phases pass, labnet retains its inherited test-only proof of work and no document may represent Soveroot's final PoW as selected.
