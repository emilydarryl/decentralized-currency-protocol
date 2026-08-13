# Soveroot PoW v1 Checkpoint-Assisted Recursive Regeneration

Status: **NON-CONSENSUS REJECTION PILOT; TIME-MEMORY GATE NOT ASSESSED**

This experiment tests whether compact machine-state checkpoints reduce the replay amplification seen in repeated recursive regeneration. It deliberately preserves an unfavorable result: the best screened checkpoint configuration is worse than the existing no-checkpoint attack.

## Plain-language result

Think of the workload as a long calculation performed with a notebook. The attacker keeps only half the normal memory and recreates discarded pages when they are needed. A checkpoint is a bookmark that records the calculator's internal settings at one earlier step.

The bookmark does help restart the calculation later. But it does not contain the missing notebook page. The attacker must recursively recreate that page as it existed at the bookmark before moving forward. That extra dependency, plus the memory taken away from the attacker's other notes, costs more than the bookmark saves.

Under the same one-million-replay limit, the best screened checkpoint attack reached iteration 892. The best prior attack without checkpoints reached iteration 999. The checkpoint policy therefore regressed exact progress by 107 iterations, or 10.7%, and is rejected.

## Exact design

Each checkpoint occupies 80 bytes inside the same logical half-scratch arena:

- a 32-bit stop iteration and 32 bits of padding;
- eight 64-bit VM registers; and
- one 64-bit accumulator.

For a requested historical value at stop `S`, the regenerator selects the newest retained checkpoint strictly before `S`. It recursively reconstructs the requested scratch word at the checkpoint's stop, restores the saved machine state, and replays the remaining suffix. Stop iterations always decrease across recursion, so the dependency remains acyclic.

The selected screen configuration reserves four entries, or 320 bytes, captures every eight iterations, assigns 1/32 of possible primary-cache slots to the primary execution cache, and uses the remainder for 20 logical frames and the packed memo. No external storage is permitted. Every run fails closed without a digest at the cumulative one-million-iteration work limit.

## Standard seed-zero result

| Method | Checkpoint entries | Stride | Exact prefix | Max replay work | Proof produced |
| --- | ---: | ---: | ---: | ---: | :---: |
| Existing recursive memo | 0 | — | 999 | 1,000,000 | No |
| Selected checkpoint policy | 4 | 8 | 892 | 1,000,000 | No |

Fourteen checkpoint allocations were screened across primary-cache ratios, entry counts, and strides. None exceeded the existing 999-iteration result. The machine-readable method record contains the complete screen.

## What this does and does not establish

The Python implementation and an independent C++ mode freeze deterministic counters, checkpoint activity, exhaustion boundaries, and commitments. The checkpoint bytes displace memo bytes inside the same declared arena.

The result rejects this checkpoint policy only. It does not prove that every hierarchical recovery policy will fail, that the workload is memory-hard, or that commodity miners are competitive. The prototypes still reserve logical frame bytes without measuring actual runtime stack, allocator overhead, or peak resident memory.

The time-memory gate remains open because no exact half-memory attack has finished a proof and no controlled physical-memory and throughput measurements exist.

## Next research direction

The next design should be dependency-aware: compact summaries must accelerate recovery of both historical machine state and the scratch values needed at that state. Any candidate remains in research until it produces exact final outputs, agrees across independent implementations, accounts for real memory, and is measured on controlled hardware.

The frozen method is [`checkpoint_recursive_regeneration_v0.json`](../contrib/pow_research_v1/checkpoint_recursive_regeneration_v0.json), and the fixed cross-implementation vectors are [`checkpoint_recursive_regeneration_v0.json`](../contrib/pow_research_v1/vectors/checkpoint_recursive_regeneration_v0.json).
