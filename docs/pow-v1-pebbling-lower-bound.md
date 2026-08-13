# Soveroot PoW v1 Offline Pebbling Lower Bound

Status: **NON-CONSENSUS OPTIMISTIC OFFLINE DIAGNOSTIC; TIME-MEMORY GATE NOT ASSESSED**

This Stage B method scans every cut of the exact versioned scratch-dependency graph and asks how many future producer iterations are unavoidable when all still-needed values cannot fit in half the declared scratch bytes. The machine-readable method is [`contrib/pow_research_v1/pebbling_lower_bound_v0.json`](../contrib/pow_research_v1/pebbling_lower_bound_v0.json).

## Cut-set argument

A materialized version is live after its write and until its last future read. At any graph cut, every live version must either occupy retained storage or be recreated before that last read.

The planner subtracts the byte-accounted value capacity from the live set. It then gives the attacker the most favorable possible grouping: if two absent values are outputs of the same producer iteration, one future execution may recover both. Every remaining absent value requires another producer execution within the canonical graph-pebbling model. The maximum of this minimum across all cuts is the reported lower bound. Algebraic shortcuts, value compression below the named layouts, or a different proof algorithm are outside this model.

This is a lower bound, not a schedule. It cannot demonstrate that the required replays are sufficient or executable.

## Deliberately optimistic assumptions

The model grants the attacker:

- perfect knowledge of every future address, edge, and last read;
- the entire half-scratch budget for retained values;
- zero-byte schedules, queues, registers, stacks, allocator metadata, and control state;
- free availability of the correct historical machine state;
- free regeneration of dependencies; and
- both useful outputs from one producer execution.

Each relaxation can only reduce the reported work relative to an actual implementation. Planner runtime and Python object memory are not attack measurements. The canonical graph byte count is recorded separately, and the executable attacker is forbidden from loading the graph or an oracle schedule.

## Deterministic standard-profile screen

Across the eight fixed standard seeds, the median peak live set is 18,666.5 versions. With a 131,072-byte half-scratch budget:

| Layout | Value capacity | Median values over capacity at strongest cut | Median unavoidable producer replays | Fraction of 98,304 normal iterations |
| --- | ---: | ---: | ---: | ---: |
| Compact, 16 bytes/value | 8,192 | 10,452 | 6,984 | 7.10% |
| Conservative, 24 bytes/value | 5,461 | 13,183 | 9,715 | 9.88% |

These figures mean that even an impossible oracle cannot carry every future-needed value through the strongest cut. They do **not** mean a half-memory miner needs only 7–10% extra work. Dependency reconstruction and historical machine state are deliberately free in this lower-bound model, so a real replay schedule can require much more work.

Fixed per-seed bounds are preserved in [`pebbling_lower_bound_v0.json`](../contrib/pow_research_v1/vectors/pebbling_lower_bound_v0.json). Reproducible GitHub-runner matrices and reports belong in the [research-results index](research-results/README.md).

## Decision

The first Stage B result supplies a deterministic floor for reviewing later schedules. It neither passes nor rejects the time-memory gate and supplies no throughput estimate.

The follow-on [graph-only schedule search](pow-v1-offline-pebbling-schedule.md) now counts recomputed nodes, dependency depth, peak retained and transient values, and encoded schedule bytes against this floor. Stage C must attempt an exact online evaluator that fits all attack state inside the half-memory ceiling without reading the graph, a trace, an oracle schedule, external storage, or a full transient scratchpad.
