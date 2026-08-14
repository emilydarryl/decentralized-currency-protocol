# Soveroot PoW v1 Direct-Dependency Bundle Regeneration

Status: **NON-CONSENSUS PILOT; SEED-ZERO ATTACK RECORD ADVANCED; TIME-MEMORY GATE NOT ASSESSED**

This experiment extends target-aware checkpoints from one exact scratch value to four values already present in the current replay step. It advances the standard seed-zero attack record from iteration 999 to 1,006 under the same half-memory and one-million replay-iteration ceilings. It does not complete a proof, does not generalize cleanly across the partial holdout, and exposes that replay iterations alone do not bound all attacker work.

## Plain-language result

The earlier bookmark stored the calculator state and one notebook value. The new bookmark also stores the values immediately used and written by that calculation step. If a later recovery needs one of those values, it can resume from the bookmark instead of rebuilding from the beginning.

With twelve bookmarks, the seed-zero attacker reaches step 1,006. The prior best was step 999, so the global record advances by seven steps, or 0.7%. The complete job contains 98,304 steps. The attacker therefore completes only about 1.02% before spending its one-million replay allowance and refusing without a proof.

This is useful because it defeats our previous best attack by a small amount. It is not evidence that the final mining design is decentralized or even proven memory-hard.

## Exact 120-byte entry

Each entry is charged inside the same logical half-scratch arena:

- one 32-bit stop iteration;
- four 16-bit scratch-word identities;
- four 64-bit exact scratch values;
- four alignment bytes;
- eight 64-bit VM registers; and
- one 64-bit accumulator.

The four candidates are the requested target, the first direct read, the second direct read/write, and the sequential write at the current replay step. Duplicate word identities collapse. No growing dependency map is carried in recursive frames.

Entries are written to `target_word mod checkpoint_capacity`. A lookup scans all twelve entries, counts every probe, and restores the latest strictly earlier entry containing the requested word. All restored values and machine state come from completed exact replay.

The arena allocator also now reserves one complete four-way memo set before maximizing recursion frames. The earlier formula reserved only one 12-byte memo entry even though the memo is allocated in groups of four. This correction matters for the small fixed-vector layout, which uses 18 frames and eight memo entries; existing configurations with enough room retain their prior layouts and vectors.

## Matched seed-zero comparison

| Method | Entries | Entry bytes | Memo entries | Exact prefix | Recoveries | Max depth | Proof |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| One-value target checkpoints | 12 | 88 | 10,196 | 951 | 50 | 5 | No |
| Four-value dependency bundles | 12 | 120 | 10,164 | 1,006 | 55 | 3 | No |
| Previous global record | 4 one-value entries | 88 | 10,252 | 999 | 53 | 4 | No |

The bundle table consumes 384 more bytes than the matched one-value table and displaces 32 packed memo entries. Despite that cost, it advances 55 more primary iterations in the matched comparison and seven beyond the prior global record.

Capacity is highly non-monotonic. Among every capacity from 3 through 32, twelve entries are the only screened configuration to exceed 999. The full matrix is frozen in [`dependency_bundle_regeneration_v0.json`](../contrib/pow_research_v1/dependency_bundle_regeneration_v0.json).

## Partial holdout and new limit

The same twelve-entry policy was compared with twelve one-value checkpoints on additional standard seeds:

| Seed index | One-value prefix | Bundle prefix | Delta |
| ---: | ---: | ---: | ---: |
| 0 | 951 | 1,006 | +55 |
| 1 | 940 | 952 | +12 |
| 2 | 982 | 946 | -36 |

Seed 3 was manually stopped after several minutes without returning; seeds 4 through 7 were not run. The replay loop still respected its one-million iteration counter, but memo hits, recursive calls, and checkpoint probes can grow without consuming that counter. This is a control-limit gap, not a completed performance result.

The seed-zero record is therefore preserved, while any claim of a general bundle advantage is rejected. A follow-up must add a deterministic total-operation ceiling covering calls and probes before completing the holdout.

## Interpretation and limits

The pilot establishes that a few exact related values can repay their checkpoint bytes and slightly strengthen one half-memory attack. Python also checks the first recovered standard value against a full-scratch oracle. Frozen small-profile results are independently reproduced by C++.

It does not assess the time-memory gate. No exact proof is completed; actual call-stack bytes, allocator overhead, peak resident memory, controlled throughput, energy, GPUs, FPGAs, ASICs, and cross-architecture behavior remain unmeasured. A stronger attack is evidence against the candidate, not evidence that mining is decentralized.

The machine-readable method is [`dependency_bundle_regeneration_v0.json`](../contrib/pow_research_v1/dependency_bundle_regeneration_v0.json), and fixed vectors are [`dependency_bundle_regeneration_v0.json`](../contrib/pow_research_v1/vectors/dependency_bundle_regeneration_v0.json).

The completed follow-up is [Total-Operation-Bounded Bundle Regeneration](pow-v1-operation-bounded-dependency-bundle-regeneration.md). It closes the call/probe gap, finishes all eight seeds, and shows that the 1,006-step replay-only record falls back to 999 under combined work accounting.
