# Soveroot PoW v1 Indexed-Gap Reconstruction

Status: **NON-CONSENSUS INDEXED-GAP STAGE C PILOT; TIME-MEMORY GATE NOT ASSESSED**

This Stage C pilot adds a page-count index and bounded neighbor rebalancing to the fixed-page replay layout. The page-count Fenwick tree replaces linear page scans. Before allocating a split page, a full page moves one boundary value into the adjacent page with the larger available gap. The goal is to recover most fragmentation loss without restoring global packed-array shifts.

The machine-readable method is [`indexed_gap_reconstruction_v0.json`](../contrib/pow_research_v1/indexed_gap_reconstruction_v0.json). Fixed independent Python/C++ boundaries are in [`vectors/indexed_gap_reconstruction_v0.json`](../contrib/pow_research_v1/vectors/indexed_gap_reconstruction_v0.json).

## Standard half-scratch layout

| Component | Bytes | Capacity |
| --- | ---: | ---: |
| Fixed state/control reserve | 512 | - |
| Canonical write bitmap | 4,096 | 32,768 words |
| Direct-mapped primary cache | 30,512 | 1,907 values |
| Replay membership bitmap | 4,096 | 32,768 words |
| Global rank Fenwick directory | 258 | 129 counters |
| Logical page directory | 698 | 349 identifiers |
| Physical page counts | 698 | 349 counts |
| Page-count Fenwick index | 700 | 350 counters |
| Paged replay values | 89,344 | 11,168 slots |
| Unused alignment | 158 | - |
| Total admitted | 131,072 | - |

The additional index costs three physical pages relative to the prior paged layout. Every lookup and update probe is counted. A page split rebuilds the position-keyed page index after inserting into the logical directory.

## Bounded neighbor rebalancing

If a target page is full, the evaluator inspects its immediate logical neighbors. When either has room, the neighbor with the larger gap absorbs one boundary value and the new value is inserted in sorted order. This uses only overlapping page-local moves and one scalar value; it does not allocate a temporary page or list. A 16/16 split occurs only when both adjacent pages are full or absent.

Every shifted existing value, directory move, rank probe, page-index probe, directory probe, and rebalance is charged. Replay begins at genesis for each canonical miss, must match the live registers and accumulator, and refuses without a digest if another split is required after all physical pages are allocated.

## Standard seed-zero result

| Metric | Paged gap | Indexed gap |
| --- | ---: | ---: |
| Physical pages | 352 | 349 |
| Peak occupied values | 6,667 | 10,142 |
| Slot utilization | 59.2% | 90.8% |
| Successful reconstructions | 423 | 1,267 |
| Exact execution prefix | 3,599 | 5,759 |
| Attempted replay iterations | 1,122,637 | 5,129,838 |
| Linear directory probes | 489,836,489 | 134,249,745 |
| Page-index probes | - | 371,109,670 |
| Neighbor rebalances | - | 3,698,021 |
| Shifted bytes | 183,331,802 | 1,387,026,310 |
| Exact proof outputs | 0 | 0 |

The index and neighbor policy recover most of the page fragmentation and advance 60.0% farther than the paged pilot. Total page metadata accesses remain approximately 505 million because index updates and split rebuilds replace much of the eliminated scan work. Movement rises to 1.39 GB due to millions of neighbor operations, but remains about 130 times below the packed array's 180.8 GB.

The indexed layout still stops before the packed layout's iteration 6,615 boundary and far before the 98,304-iteration workload completes. This is one deterministic seed and a logical byte model, not an unbiased seed study, a controlled benchmark, or a physical-memory measurement.

## Interpretation and next step

The result separates capacity from completion: reaching 90.8% page utilization does not yield an exact proof because replay remains genesis-based and the fixed value budget is still exhausted. The next useful construction should introduce byte-accounted time checkpoints or hierarchical replay so each miss does not restart at iteration zero. A wider rebalance window is lower priority unless it can be shown to recover enough of the remaining 9.2% fragmentation without excessive movement.

The time-memory gate remains open until an independently reviewed attacker completes exact outputs and measured total physical memory stays within the half-scratch ceiling.
