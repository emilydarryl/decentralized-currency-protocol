# Soveroot PoW v1 Online Bounded Probe

Status: **NON-CONSENSUS FAIL-CLOSED STAGE C SCAFFOLD; TIME-MEMORY GATE NOT ASSESSED**

This is the first Stage C implementation milestone for the v1 research candidate. It replaces the offline graph oracle with an online evaluator backed by one logically admitted half-scratch arena. The probe executes the canonical VM exactly while its cache can supply every previously written word. At the first missing materialized word, it stops before mutating machine state, commits to that boundary, and emits no digest.

The machine-readable method is [`bounded_probe_v0.json`](../contrib/pow_research_v1/bounded_probe_v0.json). Fixed independent Python/C++ boundaries are in [`vectors/bounded_probe_v0.json`](../contrib/pow_research_v1/vectors/bounded_probe_v0.json).

## Why refusal is required

A scratch cache miss is not permission to return zero. Zero is correct only if the word has never been written. The probe therefore keeps one write bit per logical scratch word. A missing word whose bit is clear returns the canonical initial zero. A missing word whose bit is set causes immediate refusal.

This distinction prevents a partial attack implementation from silently producing a plausible but invalid proof. A refused run has no digest or memory commitment and cannot be counted as mining work.

## Online layout

The half-scratch budget is divided into:

- a conservative 512-byte logical reserve for registers, accumulator, loop and cache control, allocation bookkeeping, final samples, and a refusal record;
- a one-bit-per-word write bitmap; and
- direct-mapped entries containing a 64-bit word tag and 64-bit value.

The implementation uses a single arena allocation for the bitmap and cache payload. At the standard profile, the declared scratchpad is 262,144 bytes and the admitted budget is 131,072 bytes:

| Component | Bytes |
| --- | ---: |
| Fixed state/control reserve | 512 |
| Write bitmap for 32,768 words | 4,096 |
| 7,904 tagged cache entries | 126,464 |
| Total admitted | 131,072 |

This is logical admission, not a measured peak-memory proof. Stack high water, resident memory, and allocator behavior are still unmeasured. The shared read-only dataset and epoch schedule remain outside the scratch-specific ceiling under the frozen gate policy.

## Exact-prefix commitment

When a materialized read misses, SHA3-384 commits to the domain, seed, header digest, nonce, parameters, consumer and read slot, missing word, and exact pre-read registers and accumulator. The independent Python and C++ implementations must agree on this boundary for all fixed vectors.

Agreement proves that both implementations reached the same canonical prefix and refused at the same unsafe operation. It does not prove that the prefix can be resumed.

## Deterministic standard screen

Across eight fixed standard seeds, every run refused without emitting a digest. The direct-mapped cache holds 7,904 values. Exact completed iterations before refusal ranged from 100 to 939, with a median of 685 out of 98,304 canonical iterations.

| Seed | Exact iterations | Missing word | Evictions before refusal |
| ---: | ---: | ---: | ---: |
| 0 | 693 | 16,455 | 72 |
| 1 | 100 | 15,964 | 3 |
| 2 | 225 | 8,002 | 7 |
| 3 | 677 | 4,323 | 79 |
| 4 | 939 | 16,451 | 141 |
| 5 | 784 | 178 | 104 |
| 6 | 324 | 72 | 19 |
| 7 | 702 | 376 | 75 |

The early failures are properties of this simple direct-mapped online policy, not lower bounds. A set-associative cache, different replacement rule, compression scheme, or reconstruction algorithm may reach a different boundary.

## What remains

The probe does not yet reconstruct the missing value or historical VM state. Machine state alone is insufficient: the earlier addresses and updates that produced it depended on scratch values that may also be absent. The next milestone must add a bounded reconstruction path at the committed miss boundary while preserving these invariants:

- no graph, trace, offline schedule, spill file, mapped backing store, helper process, or network service;
- every cache, checkpoint, recursion frame, queue, bitmap, allocator allowance, and transient value charged inside the ceiling;
- exact agreement on digest, registers, and memory commitment; and
- failure without output whenever the reconstruction cannot remain inside its admitted layout.

Until a run reaches `exact_complete`, measures actual memory, and meets the independent-model and controlled-host requirements, the time-memory gate remains `OPEN` and `NOT_ASSESSED`.
