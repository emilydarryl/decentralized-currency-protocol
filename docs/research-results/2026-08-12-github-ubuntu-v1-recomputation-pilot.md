# Soveroot PoW v1 No-Spill Recomputation Baseline: GitHub Ubuntu shared runner 31640088148

Status: **INFORMATIONAL EXACT-OUTPUT BASELINE — HALF-MEMORY GATE NOT ASSESSED**

Raw matrix SHA3-384: `353552e105c87298d96eff94ccb3812f144717fb52f571882e1946d8904f40b677152a048b6b424530c63d1cbc0dcc92`
Source revision: `11054d547745c80c27737a5eba84dd1b203b8204`
Method: `soveroot-pow-v1-recomputation-baseline-v0` version `0.1`
Profile: `pilot`

## What was tested

The primary execution retained 16 KiB of its 32 KiB scratchpad and used no external storage. Each read of a discarded odd-indexed word replayed the ordinary evaluator from iteration zero.

Every paired attempt produced the same digest-sequence commitment and digest xor as the normal backend.

## Aggregate result

- Normal attempt median: 0.265 ms
- Recomputation attempt median: 433.802 ms
- Retained throughput: 0.06% of normal
- Replayed iterations per seed median: 8,396,715
- Declared peak scratch allocation: 49,152 bytes (150% of normal)

## Per-seed evidence

| Seed | Normal ms | Recompute ms | Retained throughput | Recomputed reads | Replayed iterations | Exact outputs |
|---:|---:|---:|---:|---:|---:|---|
| 0 | 0.260 | 428.898 | 0.06% | 4118 | 8,271,840 | yes |
| 1 | 0.269 | 431.233 | 0.06% | 4084 | 8,351,238 | yes |
| 2 | 0.256 | 436.371 | 0.06% | 4106 | 8,442,193 | yes |
| 3 | 0.270 | 436.380 | 0.06% | 4104 | 8,448,423 | yes |

## Why this cannot decide the gate

- The half-sized retained array stays live while each replay allocates a complete scratchpad, so peak scratch allocation is 150%, not 50%.
- Resident memory, allocator overhead, metadata, stack use, power, and memory traffic were not measured.
- Replaying from iteration zero is an auditable baseline, not an optimized checkpoint strategy.
- Shared runners do not provide controlled thermal, power, or bandwidth conditions.

The result establishes exact no-spill recomputation and its work counter only. A later attacker must replace the full replay workspace with explicitly budgeted checkpoints and keep measured total attack memory within the half-memory limit. The mandatory gate remains open.
