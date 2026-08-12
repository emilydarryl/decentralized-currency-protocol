# Soveroot PoW v1 Budgeted Cache Screen: GitHub Ubuntu shared runner 31643942109

Status: **INFORMATIONAL LOWER BOUND — TIME-MEMORY GATE NOT ASSESSED**

Raw matrix SHA3-384: `e594238e3bc8585a9c9c70da8a1c22dd395c38de91032c29d897773c5d11015eee5d1f7398270ecdbac9ecc104ad824d`
Source revision: `9b5647219b60665f8962f1421b166877406312eb`
Method: `soveroot-pow-v1-budgeted-cache-screen-v0` version `0.1`
Profile: `standard`; seeds: 8

## Accounted half-memory layouts

The declared scratchpad contains 32,768 values (262,144 bytes). Each simulated cache receives at most 131,072 bytes including per-entry identity and replacement metadata.

| Layout | Entry bytes | Cached values | Scratch words represented | LRU miss share | Offline-optimal miss share |
|---|---:|---:|---:|---:|---:|
| Compact | 16 | 8,192 | 25.00% | 72.15% | 22.36% |
| Conservative | 24 | 5,461 | 16.67% | 81.32% | 33.64% |

The offline-optimal result is a lower bound for this completed trace: it knows every future access and refuses to retain values that will be overwritten before another read. A real online miner cannot know those value-dependent future addresses in advance.

## Per-seed conservative layout

| Seed | Materialized reads | LRU misses | LRU miss share | Oracle misses | Oracle miss share |
|---:|---:|---:|---:|---:|---:|
| 0 | 172,572 | 140,446 | 81.38% | 58,133 | 33.69% |
| 1 | 172,411 | 140,175 | 81.30% | 58,030 | 33.66% |
| 2 | 172,448 | 140,409 | 81.42% | 58,036 | 33.65% |
| 3 | 172,453 | 140,378 | 81.40% | 58,038 | 33.65% |
| 4 | 172,588 | 140,154 | 81.21% | 57,962 | 33.58% |
| 5 | 172,644 | 140,410 | 81.33% | 58,056 | 33.63% |
| 6 | 172,423 | 140,077 | 81.24% | 57,762 | 33.50% |
| 7 | 172,546 | 139,873 | 81.06% | 57,668 | 33.42% |

## Why this cannot decide the gate

- Neither cache policy recomputes a missing value or produces an exact proof.
- Offline-optimal replacement has future knowledge unavailable to an online miner.
- An executable attacker must deduct control state, work queues, stack, checkpoints, and allocator overhead from the same budget.
- A full scratch snapshot cannot fit inside the half-memory budget, while register-only checkpoints cannot resume the state machine.

The oracle miss count is the most favorable cache-only lower bound under the stated entry representation. The next exact attack should be selected only after comparing its recomputation plan with that unavoidable missing-value workload. The mandatory time-memory gate remains open.
