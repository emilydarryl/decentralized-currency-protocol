# Soveroot PoW v1 Workload Objectives

Version: 0.1

Status: Predeclared research screening policy; not consensus and not evidence of production readiness

These objectives freeze the reason for redesigning the v0 research VM and the minimum signals expected from a v1 candidate before its implementation is benchmarked. They supplement, but do not replace, the mandatory gates in [`pow-evaluation-gates.md`](pow-evaluation-gates.md).

## Evidence requiring redesign

The instrumented standard-profile run on GitHub's shared Ubuntu runner measured the v0 baseline as follows:

| Phase | Median time | Share of median attempt |
|---|---:|---:|
| Input setup | 6,384 ns | 0.3% |
| Scratchpad initialization | 955,061 ns | 42.2% |
| VM execution | 74,509 ns | 3.3% |
| Finalization | 1,223,041 ns | 54.1% |

Increasing dataset size 64x changed median attempt time by 1.00x. Increasing either the instruction count or pass count 16x changed it by only 1.13x. The v0 attempt is therefore dominated by SHAKE scratchpad expansion and a final hash over the entire scratchpad, not by the intended data-dependent VM workload. The full report and raw samples are preserved in [`research-results/2026-08-12-github-ubuntu-phase-standard.md`](research-results/2026-08-12-github-ubuntu-phase-standard.md) and [`research-results/2026-08-12-github-ubuntu-phase-standard.json`](research-results/2026-08-12-github-ubuntu-phase-standard.json).

This is a redesign signal, not a formal gate result. The runner was shared, only eight seeds were measured, energy was not measured, and no optimized GPU, FPGA, ASIC, or time-memory-tradeoff implementation was tested.

## v1 construction requirements

1. **Per-attempt work.** Nonce-specific work MUST dominate an attempt. Epoch preparation MAY be shared, but the candidate MUST NOT treat a large reusable dataset as evidence of per-attempt memory hardness.
2. **Dependent memory access.** Every mixing iteration MUST include a dataset read and a scratchpad read or write whose address depends on state produced by an earlier iteration. The schedule MUST NOT be reducible to one precomputed address stream shared across nonces.
3. **Declared memory use.** The standard schedule MUST perform, on average, at least two scratchpad reads and one scratchpad write per declared scratchpad word per pass. Retaining less memory must require recomputation that is evaluated under the existing time-memory-tradeoff gate.
4. **Bounded execution.** Seeds MAY select operations and addresses but MUST NOT select loop counts, rejection-sampling duration, memory size, or other unbounded work. Every valid header under one parameter set MUST execute the same number of mixing iterations.
5. **Fixed-size finalization.** Finalization MUST hash only fixed-size state totaling at most 4 KiB. It MUST NOT rescan or hash the full scratchpad or dataset.
6. **Independent specification.** v1 MUST use new domain separators, an explicit byte-level encoding, and new test vectors. The Python and C++ implementations MUST be independently written from that specification. v0 behavior and vectors remain frozen.
7. **Verifier limits.** All arithmetic, allocation, indexing, and serialization MUST be bounded and deterministic. Invalid parameter encodings MUST fail before large allocation or expensive preparation.

## Predeclared screening objectives

These are engineering screens for the standard research profile. They decide whether a v1 candidate is worth wider hardware evaluation; they do not approve labnet or mainnet activation.

| Signal | Advance to controlled hardware tests | Redesign signal |
|---|---:|---:|
| Mixing phase share of median attempt | at least 60% | below 50% |
| Scratchpad initialization share | at most 25% | above 35% |
| Finalization share | at most 10% | above 20% |
| 16x instruction budget, if retained | at least 8x total attempt time | below 4x |
| 16x pass count | at least 8x total attempt time | below 4x |
| 64x scratchpad size | 16x to 80x total attempt time | below 8x or above 128x |
| Dataset cache-tier sweep on controlled physical hardware | at least 1.25x mixing-phase change | below 1.10x |

Values between the advance and redesign bounds require explanation and another predeclared experiment. Phase shares are measured independently across seeds and are diagnostic only; implementations must also publish total latency, throughput, energy, temperature, memory traffic, and compiler settings.

The instruction-budget screen is removed if v1 has no independently variable instruction count. It cannot be declared passed by deleting a parameter after results are known. The pass-count, scratchpad, dependent-access, finalization, and mandatory evaluation gates still apply.

## What these objectives cannot guarantee

A balanced software profile does not prove memory hardness, ASIC resistance, quantum resistance, or decentralized mining. It also cannot cap a pool's real-world hashrate: miners can split identities, hide coordination, or use multiple endpoints. Pool concentration must be addressed separately through miner-created block templates, direct block publication, noncustodial payouts, low-variance solo or peer-to-peer pooling, and automatic coordinator fallback.

v1 advances only after its independent implementations agree and the screening measurements justify the much more expensive controlled CPU, GPU, FPGA, ASIC, quantum, and mining-autonomy studies required by the governing gates.
