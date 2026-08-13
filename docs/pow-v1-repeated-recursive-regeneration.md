# Soveroot PoW v1 Repeated Recursive Regeneration

Status: **NON-CONSENSUS REPEATED REGENERATION PILOT; TIME-MEMORY GATE NOT ASSESSED**

This Stage C milestone extends the first recursive value recovery across every successive primary-cache miss until a fixed cumulative replay-work limit is exhausted. The packed four-way memo persists across recoveries, all values are regenerated from exact earlier dependencies, and the evaluator fails closed without a digest when it cannot finish another recovery.

The machine-readable method is [`repeated_recursive_regeneration_v0.json`](../contrib/pow_research_v1/repeated_recursive_regeneration_v0.json). Fixed independent Python/C++ boundaries are in [`vectors/repeated_recursive_regeneration_v0.json`](../contrib/pow_research_v1/vectors/repeated_recursive_regeneration_v0.json).

## Standard seed-zero allocation screen

Every allocation uses the same 131,072-byte logical half-scratch ceiling, 20 reserved logical recursion frames, no external storage, and a cumulative limit of 1,000,000 completed replay iterations. The primary allocation is the fraction of possible 16-byte primary entries retained after the written-word bitmap; the remaining arena is used by frames and the 12-byte memo.

| Primary allocation | Primary entries | Memo entries | Recoveries | Exact prefix | Max depth | Memo evictions |
| :---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1/128 | 61 | 10,284 | 23 | 719 | 6 | 1,111 |
| 1/64 | 123 | 10,200 | 51 | 983 | 5 | 123 |
| 1/32 | 247 | 10,036 | 47 | 999 | 4 | 63 |
| 1/16 | 494 | 9,704 | 22 | 861 | 4 | 552 |
| 1/8 | 988 | 9,048 | 15 | 885 | 5 | 761 |

The inherited 1/64 baseline recovers 51 exact historical values and advances primary execution from the prior pilot's iteration 270 to iteration 983. Its last completed recovery is at consumer 951, word 8,588, with exact value `12379780771041351792`. The next miss at consumer 983 reaches the cumulative work ceiling and is refused.

The 1/32 split produces the longest screened prefix, iteration 999, despite completing fewer recoveries. More primary cache is not monotonically better: it delays or avoids some primary misses but displaces memo entries and changes deterministic memo collisions. This five-point, one-seed screen does not establish a generally optimal allocation.

## What improved

The prior milestone established one recursive recovery and stopped by policy at the second miss. This implementation reuses its exact memo across successive misses and validates that primary execution can safely retry dozens of interrupted reads. Fixed minimum-profile vectors agree between Python and C++ on all counters, first and last values, exhaustion state, and transcript commitments. Full-memory oracle runs independently confirm each fixed first and last recovered value.

## Why the gate remains open

All standard allocations consume one million replay iterations after completing less than 1.1% of the 98,304 mixing iterations. None reaches final sampling or produces an exact proof. The work ceiling is a deterministic experimental bound, not a measured profitability threshold.

The arena charges logical frame bytes, but the current Python and C++ prototypes still use their runtime call stacks. Actual stack bytes, allocator overhead, peak resident memory, and controlled throughput are unmeasured. Consequently, this result neither passes nor fails the time-memory tradeoff gate.

The next milestone should reduce replay amplification rather than merely raise the work limit. Candidate directions are byte-accounted hierarchical memoization, bounded time checkpoints combined with recursive gaps, or a non-recursive explicit work stack whose physical allocation can be measured directly. Exact final outputs and controlled physical-memory measurements remain mandatory.
