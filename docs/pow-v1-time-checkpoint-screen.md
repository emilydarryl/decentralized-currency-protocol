# Soveroot PoW v1 Time-Checkpoint Feasibility Screen

Status: **NON-CONSENSUS FULL-MEMORY OFFLINE SCREEN; TIME-MEMORY GATE NOT ASSESSED**

This screen asks whether one conventional exact time checkpoint can solve the capacity failure exposed by the Stage C replay pilots. It evaluates 17 fixed cuts from 0/16 through 16/16 of the mixing iterations, charges explicit bytes for three representations, and preserves unfavorable results.

The machine-readable method is [`time_checkpoint_screen_v0.json`](../contrib/pow_research_v1/time_checkpoint_screen_v0.json). Fixed independent Python/C++ boundaries are in [`vectors/time_checkpoint_screen_v0.json`](../contrib/pow_research_v1/vectors/time_checkpoint_screen_v0.json).

## Models

The analysis records the ordinary full-memory execution and identifies every scratch read that consumes a value produced by an earlier write. A backward scan treats a later write as killing the prior value of that word. This yields the exact live word-value frontier for a single forward execution that retains values instead of recursively regenerating them.

Each nonempty store uses one bit per logical scratch word, a 16-bit Fenwick rank directory per 256-word chunk, and one 8-byte value per retained word. Every model also reserves 512 bytes for registers, accumulator, iteration position, and bounded control state.

- **Full checkpoint:** every materialized word at the cut.
- **Naive snapshot plus delta:** an immutable full checkpoint plus every distinct word written in the suffix.
- **Optimistic staged store:** one reusable store sized to the larger of the exact capture and resume live peaks.

The optimistic model is deliberately stronger than an executable miner. It knows the complete future trace and charges no bytes for a cache, future-use schedule, allocator overhead, or physical-memory effects. Therefore, fitting would prove little; failure is adverse evidence for the no-regeneration, one-checkpoint approach.

## Standard seed-zero result

The standard profile has 32,768 scratch words, 98,304 mixing iterations, a 262,144-byte declared scratchpad, and a 131,072-byte half-scratch attack ceiling.

| Metric | Result |
| --- | ---: |
| Global maximum live values | 18,828 |
| Optimistic staged bytes | 155,490 |
| Over ceiling | 24,418 bytes (18.63%) |
| Best naive snapshot-plus-delta bytes | 267,010 |
| Naive cuts fitting | 0 of 17 |
| Optimistic cuts fitting | 0 of 17 |
| Exact canonical output | Matched |

Screen commitment: `84128227908bc801ae5ece9388407da2ca5e891a44b28073645d83213bbbf2fb1c3bb96fd6868da20572113a8de522ab`

| Cut | Snapshot values | Suffix writes | Frontier | Capture peak | Resume peak | Staged peak |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0/16 | 0 | 32,768 | 0 | 0 | 18,828 | 18,828 |
| 4/16 | 28,916 | 32,768 | 17,861 | 17,861 | 18,828 | 18,828 |
| 8/16 | 32,768 | 32,768 | 18,637 | 18,828 | 18,640 | 18,828 |
| 12/16 | 32,768 | 28,915 | 18,251 | 18,828 | 18,255 | 18,828 |
| 16/16 | 32,768 | 0 | 16 | 18,828 | 16 | 18,828 |

For every cut, the maximum of the capture and resume phases equals the original execution's global live-value maximum. Moving a single boundary only partitions the same no-regeneration liveness problem; it does not reduce its peak. The fixed canonical vectors independently commit to this calculation in Python and C++.

The much smaller smoke profile does allow the optimistic representation to fit at 3,938 bytes within its 4,096-byte ceiling. That is a useful boundary check and prevents the screen from being hard-coded to reject. Its naive snapshot-plus-delta representation still does not fit.

## Interpretation and next step

This screen rejects full snapshots, immutable snapshot-plus-delta storage, and even the optimistic one-store staged representation for standard seed zero. It does **not** prove that every time-memory attack fails, does not run a reduced-memory evaluator, and does not assess throughput or physical resident memory.

The next construction must allow exact values to be discarded and recursively regenerated. It must use one preallocated half-scratch arena and explicitly charge the retained-value cache, identity metadata, dependency/work stack, cycle guards, transient values, machine state, alignment, and allocator allowance. It must fail closed without a digest on exhaustion. Only exact final outputs and controlled physical-memory measurements can contribute to the mandatory time-memory gate.
