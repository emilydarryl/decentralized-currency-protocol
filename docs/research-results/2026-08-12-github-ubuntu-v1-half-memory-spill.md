# Soveroot PoW v1 Half-Memory Spill Attack: GitHub Ubuntu shared runner 31628959519

Status: **INFORMATIONAL EXACT-OUTPUT ATTACK — TIME-MEMORY GATE NOT ASSESSED**

Raw matrix SHA3-384: `6693f66826146bb27e0be0351a3919165358a483b92077f7b706c6944a5032ade715de3aa4c94136c90cec66a2e68370`
Source revision: `07c730b242868c4850c62a4fa24b2c6ddef8e7b3`
Attack method: `soveroot-pow-v1-half-memory-attack-v0` version `0.1`
Profile: `standard`

## What was tested

The attacker retained exactly 128 KiB of the declared 256 KiB scratchpad in its explicit byte array. Even-indexed words stayed in process; odd-indexed words were read from and written to a temporary random-access file.

Every paired attempt produced the same digest-sequence commitment and digest xor as the normal backend.

## Aggregate result

- Normal attempt median: 4.228 ms
- Half-spill attempt median: 107.990 ms
- Retained throughput: 3.91% of normal
- Numerical location only: at or below the policy pass ceiling (40.00% pass ceiling; more than 65.00% rejects)

That numerical comparison is context, not a gate outcome.

## Per-seed evidence

| Seed | Normal median ms | Half-spill median ms | Retained throughput | Exact outputs | Spill reads | Spill writes |
|---:|---:|---:|---:|---|---:|---:|
| 0 | 4.331 | 109.134 | 3.97% | yes | 295097 | 294930 |
| 1 | 4.253 | 108.915 | 3.90% | yes | 294406 | 294781 |
| 2 | 4.244 | 108.224 | 3.92% | yes | 295158 | 294708 |
| 3 | 4.116 | 107.578 | 3.83% | yes | 294817 | 294990 |
| 4 | 4.170 | 107.760 | 3.87% | yes | 295213 | 295178 |
| 5 | 4.285 | 107.867 | 3.97% | yes | 295210 | 295175 |
| 6 | 4.192 | 107.349 | 3.91% | yes | 294936 | 294722 |
| 7 | 4.212 | 108.113 | 3.90% | yes | 294982 | 294740 |

## Why this cannot decide the gate

- The operating system's page cache was neither measured nor bounded, so logical retained bytes are not physical peak memory.
- The omitted half was stored externally; this implementation does not measure the required recomputation strategy.
- Per-word file seeks are a transparent correctness baseline, not a strongest-known optimized attacker.
- Shared runners do not provide controlled storage, thermal, power, or memory-bandwidth conditions.

A decisive experiment needs a reviewed recomputation or bounded-memory attack, measured resident memory, controlled physical hosts, and the strongest optimized implementation available. Until then, the mandatory time-memory-tradeoff gate remains open.
