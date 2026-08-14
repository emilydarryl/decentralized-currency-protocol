# Soveroot PoW v1 Target-Aware Checkpoint Regeneration

Status: **NON-CONSENSUS PILOT; GLOBAL ATTACK RECORD TIED; TIME-MEMORY GATE NOT ASSESSED**

This experiment repairs the central weakness of state-only checkpoints. Each checkpoint now binds the VM machine state to the exact historical scratch value being recovered. That removes a recursive lookup, improves one weak memory allocation substantially, and preserves bounded depth—but it does not extend the best known attack prefix or produce a proof.

## Plain-language result

The prior checkpoint was like a bookmark that remembered a calculator's settings but not the notebook value needed at that point. The attacker had to recreate the missing value before it could use the bookmark.

The new bookmark stores both pieces: the calculator state and one exact notebook value. On the sparse 1/128 primary-cache allocation, this raises progress from iteration 719 to iteration 999 under the same one-million-replay limit. That is 280 additional primary iterations, or about 38.9%.

However, a different no-checkpoint allocation had already reached iteration 999. The new method therefore improves a weak allocation but only ties the global record. It still completes about 1% of the 98,304-iteration workload and emits no proof.

## Exact entry and policy

Each target-aware checkpoint occupies 88 bytes inside the same logical half-scratch arena:

- 32-bit stop iteration;
- 32-bit target scratch word;
- 64-bit exact target value at that stop;
- eight 64-bit VM registers; and
- one 64-bit accumulator.

The table retains the newest checkpoint in slot `target_word mod checkpoint_capacity`. A lookup succeeds only when the target tag matches and the stored stop is strictly earlier than the requested stop. The restored target value was produced by completed exact replay, so no new recursive lookup is required at the checkpoint boundary.

The selected configuration assigns 1/128 of possible primary entries to the direct-mapped primary cache, reserves four target checkpoints captured every eight iterations, retains 20 logical recursion frames, and gives the remaining arena to the packed memo. Total admitted memory remains exactly half the declared scratchpad, with no external storage.

## Standard seed-zero comparison

| Method | Primary allocation | Checkpoint bytes | Exact prefix | Recoveries | Max depth | Proof |
| --- | :---: | ---: | ---: | ---: | ---: | :---: |
| Repeated recursion | 1/128 | 0 | 719 | 23 | 6 | No |
| Target-aware checkpoints | 1/128 | 352 | 999 | 53 | 4 | No |
| Best prior repeated recursion | 1/32 | 0 | 999 | 47 | 4 | No |

Checkpoint capacity is not monotonic. Four entries tie the record, while 16, 64, 256, and 512 entries reach 844, 885, 943, and 926 iterations respectively. Larger tables record more hits in some cases but remove more general memo entries and change deterministic collision patterns.

## Interpretation and limits

This experiment establishes that dependency-aware checkpoints are technically useful: they eliminate the state-only checkpoint's extra recursive dependency and improve a previously weak allocation without increasing the fixed memory ceiling.

It does not establish a stronger global half-memory attack. Every screened configuration exhausts one million replay iterations before final sampling. The Python and independent C++ implementations reserve logical frame bytes but still do not measure actual stack allocation, allocator overhead, peak resident memory, or controlled throughput.

The time-memory gate remains open. No exact half-memory attacker has finished a proof, and no result here demonstrates commodity-hardware fairness, ASIC resistance, or mining decentralization.

## Next direction

The next experiment should generalize from one target value per checkpoint to a compact bundle of related dependency values. A bundle is worthwhile only if the replay work it saves exceeds the memo entries and lookup work it displaces.

The machine-readable method is [`target_checkpoint_regeneration_v0.json`](../contrib/pow_research_v1/target_checkpoint_regeneration_v0.json), and fixed independent vectors are [`target_checkpoint_regeneration_v0.json`](../contrib/pow_research_v1/vectors/target_checkpoint_regeneration_v0.json).
