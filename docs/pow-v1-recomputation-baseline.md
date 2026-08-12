# Soveroot PoW v1 No-Spill Recomputation Baseline

Status: **NON-CONSENSUS, INFORMATIONAL ATTACK HARNESS**

This milestone establishes an exact-output recomputation reference without hiding state in a file or an uncounted cache. It is deliberately not presented as a half-memory result. The machine-readable method is [`contrib/pow_research_v1/recomputation_baseline_v0.json`](../contrib/pow_research_v1/recomputation_baseline_v0.json).

## Strategy

The primary execution retains even-indexed scratchpad words and discards writes to odd-indexed words. When it later reads an odd word, it replays the ordinary evaluator from iteration zero through the last completed iteration, obtains the exact current value from the replay scratchpad, and then discards that replay workspace.

The backend:

- uses no temporary file or other external backing store;
- produces the ordinary digest, registers, and memory commitment;
- records retained reads and writes, recomputed reads, discarded writes, and replayed iterations;
- declares both steady retained bytes and peak scratch bytes;
- compares every digest sequence with the ordinary backend.

## Why it does not assess the gate

The primary retained array is half the declared scratchpad, but each missing read temporarily allocates one complete replay scratchpad while the retained array remains live. Peak scratch allocation is therefore 150%, before metadata, stack, allocator, dataset, and executable overhead.

This is a correctness and work-amplification baseline—not a bounded-memory attacker. Its purpose is to prevent later checkpoint work from quietly relying on external storage or a full unreported replay buffer.

The mandatory time-memory gate remains open until an independently reviewed implementation keeps total measured attack memory within the declared half-memory budget and is tested on controlled physical hosts.

## Next construction

Replace the full transient replay workspace with explicitly budgeted checkpoints and a bounded value cache. Accounting must include retained words, checkpoint snapshots, register and accumulator state, address metadata, recursion or work queues, and allocator overhead. Exact outputs remain mandatory.
