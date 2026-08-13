# Soveroot PoW v1 Paged-Gap Reconstruction

Status: **NON-CONSENSUS PAGED-GAP STAGE C PILOT; TIME-MEMORY GATE NOT ASSESSED**

This Stage C pilot replaces global sorted-array insertion with fixed 32-value pages. It preserves bitmap-ranked exact values in the same half-scratch arena, but shifts only within a page and a small logical page directory. The experiment asks whether this representation reduces the packed checkpoint's prohibitive byte movement without hiding memory.

The machine-readable method is [`paged_gap_reconstruction_v0.json`](../contrib/pow_research_v1/paged_gap_reconstruction_v0.json). Fixed independent Python/C++ boundaries are in [`vectors/paged_gap_reconstruction_v0.json`](../contrib/pow_research_v1/vectors/paged_gap_reconstruction_v0.json).

## Layout

At the standard profile, the 131,072-byte ceiling is partitioned as follows:

| Component | Bytes | Capacity |
| --- | ---: | ---: |
| Fixed state/control reserve | 512 | - |
| Canonical write bitmap | 4,096 | 32,768 words |
| Direct-mapped primary cache | 30,512 | 1,907 values |
| Replay membership bitmap | 4,096 | 32,768 words |
| 16-bit Fenwick rank directory | 258 | 129 counters |
| Logical page directory | 704 | 352 page identifiers |
| Physical page counts | 704 | 352 counts |
| Paged replay values | 90,112 | 11,264 slots |
| Unused alignment | 78 | - |
| Total admitted | 131,072 | - |

Each 256-byte physical page stores 32 values. A separate 16-bit directory defines logical order, so splitting a full page never moves later value pages. A split moves 16 values into a free page, updates page counts, and shifts only the later two-byte directory identifiers. Insertions into non-full pages shift only that page's suffix.

## Exactness and accounting

Membership and global rank use the same replay bitmap and 16-bit Fenwick directory as the packed pilot. The prototype currently locates a ranked value by scanning logical page counts, explicitly charging each directory and count probe. It also charges bytes moved within pages, during page splits, and in directory insertion.

At every canonical miss, replay starts from iteration zero, validates the replayed registers and accumulator against the live prefix, retains the recovered value in the primary cache, and retries the interrupted operation. The evaluator refuses without output when a required split has no free physical page.

## Fixed minimum-profile boundaries

Independent Python and C++ implementations freeze complete counters and commitments for all three canonical vectors. They recover 9-11 values and stop at iterations 97-98 with all replayed machine states matching. The nine physical pages contain 177-179 values when exhausted, exposing the expected fragmentation of split pages.

## Standard seed-zero pilot

The deterministic standard-profile result is:

| Metric | Result |
| --- | ---: |
| Physical pages / value slots | 352 / 11,264 |
| Peak occupied values | 6,667 |
| Successful reconstructions | 423 |
| Exact execution prefix | 3,599 of 98,304 iterations |
| Attempted replay work | 1,122,637 iterations |
| Rank and bitmap probes | 57,195,303 |
| Page-directory/count probes | 489,836,489 |
| Bytes shifted | 183,331,802 |
| Exact proof outputs | 0 |

The global packed-array pilot reached iteration 6,615 but shifted 180.8 GB. The paged layout shifts 183.3 MB, approximately 986 times less, at the cost of earlier exhaustion from page fragmentation. It still advances beyond the earlier flat tagged-table result at iteration 2,609.

This is one deterministic seed and a logical byte model, not an unbiased seed study, a controlled throughput benchmark, or a physical-memory measurement.

## Interpretation and next step

Paged gaps resolve the worst global insertion-movement failure, but they reveal two new limits. Only 59.2% of reserved value slots are occupied at exhaustion, and linear page lookup performs almost 490 million metadata probes. The immediate next milestone is a byte-accounted page-count index plus bounded gap rebalancing. The time-memory gate remains open until an exact-output attacker completes the workload and its total physical memory is independently measured within the half-scratch ceiling.
