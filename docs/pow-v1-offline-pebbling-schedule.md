# Soveroot PoW v1 Offline Pebbling Schedule

Status: **NON-CONSENSUS OPTIMISTIC GRAPH-ONLY SCHEDULE; TIME-MEMORY GATE NOT ASSESSED**

This completes the planned Stage B schedule search for the v1 research candidate. The deterministic planner turns the exact scratch-version DAG into concrete replay frames under a half-scratch value budget. It reports the work, recursion depth, retained-value high water, transient outputs, and encoded action-stream size that the earlier cut-set lower bound could not supply.

This is not an executable reduced-memory miner. A producer is an abstract graph node whose two scratch inputs and outputs are known; the historical registers, accumulator, program counter, address state, and dataset position required to actually re-execute that v1 iteration are absent and treated as free.

## Deterministic schedule

The planner derives each producer's two inputs and outputs from the canonical `read, read, write, write` event groups. It processes canonical reads and writes in order while retaining at most the layout's value capacity. Retention uses perfect future knowledge: the unpinned value with the farthest next canonical use is evicted, and a new value is discarded when its own next use is at least as far away.

On a read miss, the planner recursively materializes the missing version's producer inputs. It emits that producer after its dependencies, so every miss frame is a concrete dependency-postorder action stream in the scratch-version DAG. Cycles, future producers, malformed event groups, and insufficient pinned-frontier capacity are rejected.

The frozen method is [`offline_pebbling_schedule_v0.json`](../contrib/pow_research_v1/offline_pebbling_schedule_v0.json). Fixed smoke and eight-seed standard commitments are in [`vectors/offline_pebbling_schedule_v0.json`](../contrib/pow_research_v1/vectors/offline_pebbling_schedule_v0.json).

## Schedule encoding and accounting

The direct v0 encoding contains a domain-separated header with the budget, value-entry size, and producer count. Each canonical miss adds a one-byte tag, 32-bit requested version, 32-bit action count, and one 32-bit producer ordinal per replay. SHA3-384 commits to those exact bytes. The planner streams this commitment; it does not retain the multi-megabyte action stream in memory.

Schedule bytes are reported separately instead of silently omitted. They are not subtracted from the retained-value capacity, and no claim is made that this direct encoding is minimal or incompressible. This favorable treatment lets the planner study graph work, but makes every result ineligible as a half-memory implementation.

The `peak_transient_values` metric also counts the two outputs present at an abstract producer execution. It reaches capacity plus two in the standard cases. Thus even before schedules, recursion frames, or real VM state are charged, this planner is not an executable object that fits the strict ceiling.

## Deterministic standard-profile screen

Across eight fixed standard seeds, each graph contains 98,304 canonical producer iterations and the half-scratch budget is 131,072 bytes.

| Layout | Value capacity | Median canonical misses | Median replayed producers | Median abstract total work | Median max depth | Median peak retained / transient | Median direct schedule |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Compact, 16 bytes/value | 8,192 | 32,237 | 3,424,646 | 35.84x canonical | 27 | 8,192 / 8,194 | 13,989,059 B |
| Conservative, 24 bytes/value | 5,461 | 46,768 | 6,419,925 | 66.31x canonical | 29 | 5,461 / 5,463 | 26,101,215 B |

The compact replay counts range from 3,346,603 to 3,620,196; the conservative counts range from 6,296,444 to 6,649,954. These counts are much larger than the 6,984 and 9,715 median producer floors from the optimistic cut-set bound because this schedule recursively reconstructs graph dependencies rather than receiving them for free.

The schedule itself exceeds the half-memory ceiling by roughly 13.99 MB or 26.10 MB when added to retained payload. This only rejects this direct offline representation as an online design. A different deterministic policy, compressed schedule, online decision rule, checkpoint construction, or alternative proof algorithm may behave differently.

## Deliberately excluded costs

The planner receives advantages unavailable to a valid attacker:

- the complete full-memory graph and every future use are available;
- correct historical VM and address state is free;
- abstract producers may run whenever their two scratch inputs are present;
- all half-scratch bytes are devoted to retained value entries;
- schedule, stack, queue, allocator, and planner bytes are outside value capacity; and
- Python wall time and memory are offline-tool diagnostics, not mining measurements.

It does not reproduce a canonical digest with reduced memory, measure accepted-work throughput, or satisfy the independent-model and controlled-hardware requirements. The mandatory time-memory gate remains `OPEN` and `NOT_ASSESSED`.

## Decision

Stage B is complete as an offline graph study. Its result is useful negative design evidence: a straightforward oracle cache plus recursive replay produces millions of abstract replays and an action stream two orders of magnitude larger than the scratchpad itself.

The next milestone is Stage C, but it should begin with a compact online decision rule and an explicit historical-state reconstruction design—not by loading this graph or schedule. Any prototype must reject startup unless retained values, transient values, VM checkpoints, recursion or work queues, metadata, allocator overhead, and all attack-only storage fit inside the 131,072-byte standard ceiling. Exact digests, registers, and memory commitments must match the ordinary evaluator before any throughput number is meaningful.
