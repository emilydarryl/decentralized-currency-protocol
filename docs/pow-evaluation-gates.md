# Soveroot PoW Evaluation Gates

Version: 0.1

Status: Predeclared research policy; not consensus and not evidence that the candidate passes

The machine-readable policy is [`contrib/pow_research/gates_v0.json`](../contrib/pow_research/gates_v0.json). These thresholds are governance choices intended to prevent the project from moving its goalposts after seeing favorable or unfavorable measurements. They are not scientific constants.

## Decision rule

Every mandatory gate must pass independently. A strong result in one category cannot compensate for a failure in another. A redesign result requires a new candidate or parameter set and a new complete evaluation. A reject result blocks labnet activation of the current candidate.

Changing a threshold requires a new version, written justification, and fresh evaluation. It cannot retroactively approve measurements collected under an earlier policy.

## Correctness and verifier safety

- Two independent implementations must agree on at least one million vectors across three CPU architectures. One disagreement rejects the current encoding until the cause is understood and new vectors are versioned.
- On three declared low-cost systems, incremental verifier memory must not exceed 512 MiB, epoch preparation p99 must not exceed 10 seconds, header verification p99 must not exceed 250 ms, and sustained verification must reach at least four competing headers per second.
- Exceeding 1 GiB, 30 seconds for preparation, or one second per header rejects the parameter set.

## Program and memory behavior

- Across at least 1,024 unbiased seeds per device, the ratio between p95 and p5 per-seed median execution time must be at most 1.25, and maximum-to-minimum must be at most 1.5.
- An implementation using half the declared memory must retain no more than 40% of normal throughput to pass. Retaining more than 65% rejects the construction's memory-hardness claim.
- After ordinary hardware occupancy is accounted for, large-batch or shared-initialization operation may improve per-attempt cost by at most 1.25x. More than 1.75x rejects the construction because a facility can amortize the work too strongly.

## Specialization advantage

Advantage is evaluated twice: accepted work per acquisition dollar and accepted work per joule. Prices, device lifetimes, compiler versions, power limits, and measurement methods must be published.

| Comparison | Pass ceiling: capital | Pass ceiling: energy | Reject above: capital | Reject above: energy |
|---|---:|---:|---:|---:|
| Optimized GPU over optimized consumer CPU | 8x | 5x | 16x | 10x |
| Reviewed FPGA over optimized consumer GPU | 4x | 5x | 8x | 10x |
| Reviewed ASIC over optimized consumer GPU | 8x | 10x | 20x | 25x |

Values between pass and reject require redesign and retesting. The comparisons require low-cost, midrange, and high-end CPUs; optimized implementations in two major GPU ecosystems; an independently reviewed FPGA estimate; and two independently reviewed ASIC cost models.

These ceilings do not prove mining will decentralize. Geographic energy access, chip supply, financing, pool variance, and block-template control remain separate concentration risks.

## Quantum and template autonomy

- Two independent reversible-circuit estimates must cover depth, logical and physical qubits, coherent memory, error correction, and parallelism. A material advantage without an explicitly approved economic first-mover model rejects the candidate. Soveroot must not call the PoW quantum-proof.
- Two interoperable mining implementations must demonstrate miner-created templates, direct block publication, a noncustodial payout path, and automatic coordinator fallback. Mandatory coordinator template control rejects deployment regardless of PoW performance.

## What an initial CPU report can establish

A CPU matrix can test the measurement pipeline, expose seed variance, and estimate verifier timing and working-set trends. A shared cloud runner is informational only because its CPU allocation, contention, thermal behavior, and power consumption are not controlled. It cannot pass any hardware-decentralization gate by itself.
