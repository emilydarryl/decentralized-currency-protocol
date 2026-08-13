# Soveroot PoW v1 Bounded Repeated Reconstruction

Status: **NON-CONSENSUS REPEATED STAGE C RESULT; TIME-MEMORY GATE NOT ASSESSED**

This Stage C milestone repeatedly reconstructs missing materialized scratch values inside the same logical half-scratch arena. It uses no offline graph, trace, oracle schedule, spill file, mapped backing store, helper process, or second arena allocation.

The machine-readable method is [`repeated_reconstruction_v0.json`](../contrib/pow_research_v1/repeated_reconstruction_v0.json). Fixed independent Python/C++ boundaries are in [`vectors/repeated_reconstruction_v0.json`](../contrib/pow_research_v1/vectors/repeated_reconstruction_v0.json).

## Policy

The 131,072-byte standard arena keeps the existing 512-byte fixed reserve and 4,096-byte write bitmap. Its remaining entries stay split between a 47,424-byte direct-mapped primary cache and a 79,040-byte, 4,940-entry sparse replay table.

At every missing materialized read, the evaluator:

1. stops before registers, accumulator, or scratch state change;
2. clears only the already reserved replay table;
3. runs the canonical VM from iteration zero to the interrupted boundary;
4. stores every distinct replay-written word and refuses if the table fills;
5. requires replayed registers and accumulator to equal the live machine state;
6. commits the boundary and exact recovered value;
7. retains that value in the primary cache and retries the interrupted operation; and
8. repeats until exact completion or workspace exhaustion.

The evaluator records successful and attempted replay iterations separately. A terminal attempt charges only fully completed replay iterations plus every hash probe performed by the partial iteration that fills the table. Reconstruction depth is one because this policy never recursively reconstructs an evicted replay value.

## Independent fixed boundaries

All three canonical minimum-profile vectors agree between Python and C++ on the complete counters, first and last recovery, transcript commitment, replay-table high water, and exact exhaustion boundary. Each case reconstructs one or two values and then fills its 135-entry replay table. All successful replayed machine states match independently.

## Deterministic standard screen

Across eight fixed standard seeds, every case reconstructs repeatedly and then refuses without a digest.

| Metric | Result |
| --- | ---: |
| Successful reconstructions | 109–137; median 120.5 |
| Exact execution prefix | 2,609–2,658; median 2,634.5 iterations |
| Attempted replay work | median 235,081 iterations |
| Cumulative hash probes | median 4,281,280 |
| Terminal replay-table high water | 4,940 of 4,940 entries |
| Exact proof outputs | 0 of 8 |

This is a substantial advance over stopping at the second miss, but the work amplification is already large: the median attempted replay count is about 89 times the median canonical prefix. That ratio is descriptive for these fixed cases, not a general lower bound or controlled throughput measurement.

## Interpretation

The result demonstrates that independent exact prefix replay can recover many successive evictions without future knowledge or external storage. It also identifies the flat policy's concrete failure mode: once the historical prefix contains more distinct written words than the reserved sparse table can represent, reconstruction cannot proceed.

It does not complete a reduced-memory proof, measure process resident memory, or establish an economic hardware limit. Checkpoints may shorten replay work but consume arena bytes; recursive recovery may avoid storing the full prefix but introduces additional depth, work queues, and state. Those tradeoffs must be byte-accounted and independently implemented.

The next milestone is a bounded checkpoint or recursive reconstruction policy that goes beyond this flat-table exhaustion boundary. Until an evaluator reaches exact final outputs and measures all process memory on controlled hosts, the time-memory gate remains `OPEN` and `NOT_ASSESSED`.
