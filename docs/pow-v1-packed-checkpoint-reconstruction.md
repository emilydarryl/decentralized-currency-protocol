# Soveroot PoW v1 Packed Checkpoint Reconstruction

Status: **NON-CONSENSUS PACKED-CHECKPOINT STAGE C PILOT; TIME-MEMORY GATE NOT ASSESSED**

This Stage C pilot replaces the replay table's 64-bit word tag per value with a membership bitmap and rank directory. Exact replay values remain packed in logical-word order inside the same half-scratch arena. The goal is to measure how much farther a denser exact checkpoint can progress and what update cost it creates.

The machine-readable method is [`packed_reconstruction_v0.json`](../contrib/pow_research_v1/packed_reconstruction_v0.json). Fixed independent Python/C++ boundaries are in [`vectors/packed_reconstruction_v0.json`](../contrib/pow_research_v1/vectors/packed_reconstruction_v0.json).

## Layout

At the standard profile, the 131,072-byte ceiling is partitioned as follows:

| Component | Bytes | Capacity |
| --- | ---: | ---: |
| Fixed state/control reserve | 512 | - |
| Canonical write bitmap | 4,096 | 32,768 words |
| Direct-mapped primary cache | 30,512 | 1,907 values |
| Replay membership bitmap | 4,096 | 32,768 words |
| 16-bit Fenwick rank directory | 258 | 129 counters |
| Packed replay values | 91,592 | 11,449 values |
| Unused alignment | 6 | - |
| Total admitted | 131,072 | - |

The prior tagged sparse table held 4,940 replay values. The packed checkpoint therefore increases exact replay-value capacity by 2.32 times, while reducing the primary cache from 2,964 to 1,907 entries.

## Exact access and update

Membership is one bit per logical word. A 16-bit Fenwick directory stores counts over 256-word chunks. To read a present word, the evaluator computes its rank from the directory plus at most 32 bitmap bytes, then reads the corresponding packed 64-bit value.

On the first write to a word, later packed values shift eight bytes to preserve logical-word order. The evaluator accounts for every rank/bitmap probe and every shifted byte. This makes the layout auditable but exposes its principal weakness: dense capacity is purchased with expensive insertion movement.

At each canonical miss, replay still starts from iteration zero, independently matches the live registers and accumulator, retains the recovered value in the primary cache, and retries the interrupted operation. The evaluator refuses without output when the packed value area fills.

## Independent minimum-profile boundaries

Python and C++ freeze the complete counters, first and last recovery, transcript, rank work, shifted bytes, and exact exhaustion boundary for all three canonical minimum-profile vectors. They recover 43–48 values and advance to iterations 180–182 before the 312-value packed area fills. Every replayed machine state matches.

## Standard pilot

A deterministic standard seed-zero pilot produced:

| Metric | Result |
| --- | ---: |
| Packed replay capacity | 11,449 values |
| Successful reconstructions | 1,732 |
| Exact execution prefix | 6,615 of 98,304 iterations |
| Attempted replay work | 8,010,906 iterations |
| Rank and bitmap probes | 425,431,477 |
| Bytes shifted by insertions | 180,801,640,520 |
| Exact proof outputs | 0 |

The flat-table seed-zero result stopped at iteration 2,609 after 117 recoveries. Packing therefore extends this seed's exact prefix by 2.54 times, but the 180.8 GB of cumulative internal movement makes the current sorted-insertion representation unsuitable as a performant attacker.

This is one fixed standard seed, not an unbiased seed study or throughput benchmark. The committed workflow can collect up to eight seeds, but Python execution is intentionally expensive because it performs and charges the actual packed shifts.

## Interpretation

The pilot demonstrates that metadata compression materially changes the bounded reconstruction frontier. It also rules out treating compactness as free: a representation can save arena bytes while imposing enormous time and memory-bandwidth work.

The next milestone is a byte-accounted block-gap, indexed-packed, or bounded time-checkpoint layout that reduces insertion movement without restoring a full 64-bit tag per value. Exact final outputs and measured physical memory remain mandatory before the time-memory gate can be assessed.
