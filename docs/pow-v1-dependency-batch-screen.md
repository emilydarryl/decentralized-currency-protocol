# Soveroot PoW v1 Dependency and Batch Screen

Status: **NON-CONSENSUS DIAGNOSTICS; NO POW GATE PASSED**

This milestone prepares the next bounded-memory attack without pretending that a cache simulation is a valid proof generator. It also measures the simplest large-batch advantage through the 4,096-attempt evidence floor in the governing facility-amortization gate.

The predeclared machine-readable method is [`contrib/pow_research_v1/dependency_batch_screen_v0.json`](../contrib/pow_research_v1/dependency_batch_screen_v0.json).

## Exact dependency tracing

The standalone C++ implementation can record every scratchpad word read and written while executing with the full scratchpad. Trace mode returns the ordinary result digest and memory commitment, and canonical vectors require both to remain unchanged.

The summary records:

- reads that still observe the scratchpad's initial zero value;
- reads of values written earlier in the same attempt;
- distinct read and written word counts;
- an offline maximum live-value count found by scanning the completed trace backward;
- half- and quarter-capacity LRU simulations over materialized values;
- a SHA3-384 commitment to the ordered, domain-separated access trace.

The trace itself is value-dependent and cannot be known without executing the attempt. The offline live set and simulated cache therefore diagnose pressure; they do not constitute an online reduced-memory algorithm.

## Batch experiment

The standard screen measures sequential batches of 1, 4, 16, 64, 256, 1,024, and 4,096 attempts for each of eight deterministic seeds. It reports two costs:

- **inclusive cost** adds epoch preparation to all measured attempts and divides by batch size;
- **evaluation-only cost** divides the attempt timings by batch size and excludes preparation.

Each batch is compared with the same seed's single-attempt measurement. Execution order rotates deterministically by seed to reduce a fixed first-run bias.

## Interpretation limits

The trace and batch screen cannot pass either the time-memory or facility-amortization gate:

- tracing retains the entire scratchpad;
- LRU misses do not reproduce missing values;
- sequential CPU batches do not model parallel miners or specialized hardware;
- hardware occupancy is not measured;
- shared runners do not control power, temperature, memory traffic, or competing load.

The report may locate the sequential inclusive advantage relative to the frozen 1.25x pass ceiling and 1.75x rejection boundary, but that remains numerical context until controlled hardware occupancy is accounted for.

## Next attack construction

The dependency measurements should be used to select checkpoint intervals and eviction policies for an exact no-spill recomputation implementation. Its accounting must include retained values, checkpoints, register state, metadata, and call-stack state. Only an independently reviewed implementation with measured peak resident memory can contribute to the mandatory time-memory gate.
