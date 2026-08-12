# Soveroot PoW v1 Dependency and Batch Screen: GitHub Ubuntu shared runner 31633897277

Status: **INFORMATIONAL DIAGNOSTICS — NO POW GATE PASSED**

Trace matrix SHA3-384: `229c92b18944ebea4461bc5dc860ef550006399b2bba712ece9328867bb7af7042a64d28958d9bd021a78d05693616b9`
Batch matrix SHA3-384: `83a1b7a61d936359528a9b1da34d9ff1eb8da5989317ab8af38bb65688ec458fef3411126f31de8a26e2752b09dada90`
Source revision: `3cd8ce52c3bb4bc72eaac2136fe03bb7b508d6d9`
Method: `soveroot-pow-v1-dependency-batch-screen-v0` version `0.1`

## Dependency trace

Across 8 seeds, the median trace had 24,124 reads of untouched zero values and 172,499 reads of values written earlier in the attempt.

The offline maximum live-value count was 18,666 words (56.96% of the scratchpad). This uses the completed trace and therefore is not an online attack strategy.

| Simulated value cache | Materialized read hits | Materialized read misses | Miss share |
|---|---:|---:|---:|
| Half capacity | 93,517 | 79,042 | 45.81% |
| Quarter capacity | 48,047 | 124,501 | 72.15% |

These LRU simulations use a full-memory execution trace. A miss identifies a value that an online bounded-memory implementation must retain, compress, or recompute; the simulator itself does none of those and does not produce a proof.

## Sequential batch amortization

| Batch | Inclusive per attempt ms | Evaluation per attempt ms | Inclusive advantage | Evaluation-only advantage |
|---:|---:|---:|---:|---:|
| 1 | 68.734 | 5.701 | 1.00x | 1.00x |
| 4 | 21.223 | 5.525 | 3.24x | 1.04x |
| 16 | 9.410 | 5.471 | 7.28x | 1.04x |
| 64 | 6.444 | 5.462 | 10.68x | 1.05x |
| 256 | 5.714 | 5.470 | 12.01x | 1.04x |
| 1024 | 5.525 | 5.464 | 12.46x | 1.04x |
| 4096 | 5.492 | 5.477 | 12.52x | 1.04x |

At batch 4,096, the inclusive advantage was 12.52x and the evaluation-only advantage was 1.04x. The inclusive value lies above the policy rejection boundary (1.25x pass ceiling; more than 1.75x rejects).

That comparison is numerical context only. The shared runner did not measure hardware occupancy, parallel miners, energy, temperature, or memory traffic, so the facility-amortization gate remains open.

## Consequence for the recomputation attack

The next implementation must reproduce exact outputs without external storage while accounting for all retained values, checkpoints, metadata, and stack state. The trace narrows that design problem but cannot substitute for it. A large miss share or live set is encouraging only until a reviewed online attack demonstrates the actual throughput tradeoff.
