# Soveroot PoW v1 Bounded First Reconstruction

Status: **NON-CONSENSUS ONE-MISS STAGE C RESULT; TIME-MEMORY GATE NOT ASSESSED**

This Stage C milestone reconstructs the first materialized scratch value missing from the online cache. The reconstruction uses no offline graph, trace, oracle schedule, spill file, mapped backing store, helper process, or second allocation. It reuses a sparse replay workspace reserved inside the same logical half-scratch arena before execution starts.

The machine-readable method is [`bounded_reconstruction_v0.json`](../contrib/pow_research_v1/bounded_reconstruction_v0.json). Fixed independent Python/C++ results are in [`vectors/bounded_reconstruction_v0.json`](../contrib/pow_research_v1/vectors/bounded_reconstruction_v0.json).

## Construction

The arena keeps the earlier 512-byte fixed-state reserve and one-bit-per-word write bitmap. The remaining 16-byte entries are split before execution: five eighths form a bounded sparse replay table and three eighths form the direct-mapped primary cache.

At the first missing materialized read:

1. execution stops before registers, accumulator, or scratch state change;
2. the replay table is cleared without allocating new memory;
3. the canonical VM runs from iteration zero to the interrupted iteration, retaining every distinct written word in an open-addressing table;
4. replay refuses if that table fills;
5. replayed registers and accumulator must equal the live pre-read machine state;
6. the requested word is read from the exact replay state and committed together with the matching machine state;
7. the recovered value enters the primary cache and the interrupted iteration retries; and
8. the prototype refuses without output at the next materialized miss.

The retry rule matters when the first missing value is the first input: recomputing that value may expose a different missing second input in the same iteration. That is recorded as the next refusal rather than hidden.

## Byte layout

At the standard profile, the 131,072-byte logical ceiling is partitioned as follows:

| Component | Bytes | Entries |
| --- | ---: | ---: |
| Fixed state/control reserve | 512 | - |
| Write bitmap | 4,096 | 32,768 bits |
| Direct-mapped primary cache | 47,424 | 2,964 |
| Sparse replay workspace | 79,040 | 4,940 |
| Total admitted | 131,072 | - |

The single arena payload is bounded, but the 512-byte reserve remains a declared allowance rather than a measured stack and allocator high water. This result therefore cannot satisfy the gate's physical-memory requirement.

## Independent fixed boundaries

For all three canonical minimum-profile vectors, Python and C++ agree on:

- the first missing read;
- the exact reconstructed 64-bit value;
- the reconstruction replay work and table high water;
- the reconstruction commitment;
- the matching replayed machine state; and
- the next fail-closed boundary and its state commitment.

The reconstructed values are accepted only when all eight registers and the accumulator independently match at the interrupted boundary.

## Deterministic standard screen

Across eight fixed standard seeds, every case reconstructs one value with matching machine state and later refuses without a digest.

| Metric | Result |
| --- | ---: |
| Median first reconstruction iteration | 432.5 |
| Median replayed iterations | 432.5 |
| Median replay-table high water | 854.5 of 4,940 entries |
| Median exact prefix after recovery | 619.5 of 98,304 iterations |
| Exact proof outputs | 0 of 8 |

The exact prefix after recovery ranges from 439 to 785 iterations. One seed reconstructs the first input at iteration 785 and immediately refuses on the second input of that same iteration; other seeds advance farther before the next miss. This is useful boundary evidence, not a throughput measurement or lower bound.

## Interpretation

This result answers a narrow question positively: an early missing value and the historical machine state needed to validate it can be reconstructed exactly within a prepartitioned half-scratch logical arena.

It does not show that every later miss can be handled. Replay from iteration zero becomes more expensive, the sparse table eventually fills as distinct written words accumulate, and the smaller primary cache creates more misses. A complete attacker will require repeated reconstruction, recursive eviction recovery, checkpoints, a different cache/replay split, or a combination of those techniques.

The next milestone is repeated fail-closed reconstruction under the same arena, with cumulative replay work, maximum recursion or checkpoint depth, and workspace exhaustion reported. Until an evaluator reaches exact final outputs and measures all process memory on controlled hosts, the time-memory gate remains `OPEN` and `NOT_ASSESSED`.
