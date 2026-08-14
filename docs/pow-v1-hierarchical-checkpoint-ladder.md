# Soveroot PoW v1 Hierarchical Checkpoint-Ladder Pilot

Status: **NON-CONSENSUS PILOT; HOLDOUT COMPLETE; TIME-MEMORY GATE NOT ASSESSED**

This milestone gives the bounded half-memory attacker a different checkpoint policy. Instead of linearly checking twelve recent dependency bundles, it keeps sixty-four bundles in four directly addressed time scales. The memory partition, eight seeds, nonce, lookup rule, and five-million-operation ceiling were committed before the holdout ran.

## Plain-language result

Imagine recreating missing notebook pages while keeping bookmarks. The prior attacker kept twelve bookmarks in one small tray and checked the whole tray every time. The new attacker has four labeled drawers: bookmarks for every 8th, 64th, 512th, and 4,096th step. A page number points to exactly one place in each drawer, so every search checks four places—never all sixty-four.

This is a stronger attack. Its median progress rises from step 886 to 945.5, and its best case rises from 952 to 982. But the complete job has 98,304 steps. The best result is still less than 1% of a proof, all eight cases spend exactly five million work tokens, and none produces a spendable mining proof. One seed gets worse, which is retained rather than hidden.

The result is useful evidence against our design because we want to find the strongest reduced-memory miner we can. It is not evidence that memory hardness has passed: an even smarter strategy may exist, and an attacker that never finishes cannot be timed against an ordinary miner.

## Frozen memory and work rules

| Component | Bytes |
| --- | ---: |
| Fixed control-state reserve | 512 |
| Allocator allowance | 4,096 |
| Preallocated arena | 126,464 |
| Total attack budget | 131,072 |

Inside the arena are a 4,096-byte written-word bitmap, a 944-byte primary cache, twenty packed 104-byte work frames, 7,680 bytes of checkpoints, and a 111,648-byte packed memo table. Sixteen arena bytes remain unused. External storage, offline schedules, native recursive self-calls, and recovery-dependent transcript growth are forbidden.

The checkpoint ladder is fixed as follows:

| Level | Step spacing | Entries | Arena slots |
| ---: | ---: | ---: | ---: |
| 0 | 8 | 32 | 0–31 |
| 1 | 64 | 16 | 32–47 |
| 2 | 512 | 8 | 48–55 |
| 3 | 4,096 | 8 | 56–63 |

Every lookup charges exactly four checkpoint probes. The total-operation counter also charges every logical value request, replayed VM iteration, and memo probe. It refuses before exceeding 5,000,000 and emits no proof on refusal.

## Complete holdout

| Seed | Prior prefix | Ladder prefix | Change | Recovered misses | Ladder hits | Explicit depth | Proof |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| 0 | 712 | 875 | +163 | 44 | 2,444 | 6 | No |
| 1 | 952 | 840 | -112 | 38 | 2,205 | 7 | No |
| 2 | 946 | 982 | +36 | 49 | 2,586 | 5 | No |
| 3 | 895 | 978 | +83 | 57 | 1,474 | 5 | No |
| 4 | 723 | 914 | +191 | 45 | 2,069 | 5 | No |
| 5 | 939 | 965 | +26 | 48 | 706 | 6 | No |
| 6 | 877 | 977 | +100 | 53 | 1,374 | 5 | No |
| 7 | 771 | 926 | +155 | 49 | 1,868 | 6 | No |

The ladder prefixes range from 840 to 982 with a median of 945.5. All exhaustion reasons are `operation_limit`; all totals are exactly 5,000,000. Maximum explicit depth is seven, below the fixed capacity of twenty. The frozen machine-readable method retains every counter and transcript commitment.

## Independent checks

Python and C++ separately implement the directly addressed four-level lookup and capture rules. Three frozen short vectors compare their complete deterministic JSON boundaries, including memory layout, counters, operation totals, exhaustion state, checkpoint levels, and transcript commitment. The C++ comparison and compiler stack limit become authoritative when the Linux CI job passes.

Those checks establish agreement at the frozen boundaries, not production safety. They do not show that no better attack exists.

## What comes next

Further parameter tuning of this same replay family would risk optimizing to eight public seeds. The next milestone is independent adversarial review and a second bounded attack family with its policy frozen before results. Controlled-host throughput measurement becomes meaningful only if an eligible half-memory attacker completes canonical proofs.

The frozen method and full holdout are [`hierarchical_checkpoint_ladder_v0.json`](../contrib/pow_research_v1/hierarchical_checkpoint_ladder_v0.json). Fixed cross-language vectors are [`vectors/hierarchical_checkpoint_ladder_v0.json`](../contrib/pow_research_v1/vectors/hierarchical_checkpoint_ladder_v0.json).
