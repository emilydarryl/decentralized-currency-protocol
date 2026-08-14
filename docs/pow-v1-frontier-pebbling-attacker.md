# PoW v1 Cost-Aware Frontier-Pebbling Attacker

Status: **COMPLETE NON-CONSENSUS ATTACK STUDY; NO GATE ASSESSED**

This study asks whether a miner can perform the canonical v1 job with half the normal scratch memory by keeping expensive-to-recreate historical values instead of machine-state checkpoints. The policy was frozen before the fixed vectors or holdout were observed.

## Plain-language model

Imagine the mining calculation as a 98,304-page workbook. A normal miner keeps the complete workbook. This attacker keeps only half the allowed memory and recreates missing pages from the beginning.

The previous attack stored bookmarks describing the calculator's state. This attack removes those bookmarks and stores recreated pages themselves. Each page is assigned exactly two lockers. The attacker checks both lockers every time and prefers to keep pages from later in the workbook because they usually cost more work to recreate.

That idea produced about 1.42 million successful locker lookups in every holdout case. It still failed early because every access pays for two checks and any missing calculator state must still be replayed from the beginning. Useful hits alone therefore do not make the attack efficient.

## Frozen construction

- Total attack budget: 131,072 bytes, exactly half the candidate's 262,144-byte scratch memory.
- Fixed state reserve: 512 bytes.
- Allocator allowance: 4,096 bytes.
- Preallocated arena: 126,464 bytes.
- Write bitmap: 4,096 bytes.
- Primary memo: 59 packed 16-byte entries, or 944 bytes.
- Explicit work stack: 20 packed 104-byte frames, or 2,080 bytes.
- Frontier: 9,944 packed 12-byte `(key, value)` entries, or 119,328 bytes.
- Unused arena space: 16 bytes.
- External storage, machine-state checkpoints, native recursion, offline schedules, and recovery-dependent transcript growth: none.

Each frontier key encodes the requested historical iteration and scratch word. Two deterministic, distinct slots are derived from that key. Both slots are always probed and charged. An exact key is updated; otherwise an empty slot is used. If both are occupied, the value with the smaller historical iteration is the eviction candidate, and replacement occurs only when the incoming value is later. The iteration number is already part of the key, so this cost estimate requires no hidden metadata.

The total-operation ceiling is 5,000,000. It charges every logical value request, replayed VM iteration, and frontier probe. The attacker refuses before exceeding the limit and emits no proof.

## Fresh holdout

The frozen holdout used standard-profile seed indices 8 through 15, nonce zero, and a one-million replay-iteration safety ceiling. These seeds differ from the previous checkpoint-ladder holdout, so the two result sets are not a controlled numerical head-to-head comparison.

| Seed | Exact prefix | Misses | Value requests | Replay iterations | Frontier probes | Frontier hits | Admit / replace / reject | Max stack | Proof |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| 8 | 714 | 18 | 1,430,435 | 715,209 | 2,854,356 | 1,420,675 | 1,410 / 12 / 1,828 | 7 | No |
| 9 | 813 | 36 | 1,429,987 | 714,975 | 2,855,038 | 1,422,586 | 1,621 / 18 / 827 | 6 | No |
| 10 | 809 | 42 | 1,429,711 | 714,835 | 2,855,454 | 1,423,773 | 1,607 / 15 / 353 | 5 | No |
| 11 | 820 | 23 | 1,429,705 | 714,841 | 2,855,454 | 1,423,779 | 1,622 / 13 / 338 | 5 | No |
| 12 | 759 | 26 | 1,430,028 | 715,002 | 2,854,970 | 1,422,408 | 1,484 / 11 / 1,042 | 5 | No |
| 13 | 779 | 35 | 1,429,700 | 714,832 | 2,855,468 | 1,423,808 | 1,538 / 9 / 415 | 5 | No |
| 14 | 770 | 33 | 1,430,451 | 715,209 | 2,854,340 | 1,420,616 | 1,509 / 12 / 1,755 | 6 | No |
| 15 | 828 | 42 | 1,429,891 | 714,925 | 2,855,184 | 1,423,005 | 1,645 / 16 / 631 | 6 | No |

Every case consumed exactly 5,000,000 operations. The minimum, median, and maximum exact prefixes were 714, 794, and 828. The maximum completed only 0.8423% of the 98,304-iteration job. No case produced a canonical proof.

## Reproduction and independent checks

The method and full row-level transcript commitments are in [`frontier_pebbling_attacker_v0.json`](../contrib/pow_research_v1/frontier_pebbling_attacker_v0.json). Short fixed vectors cover seeds 0 through 2 at 1,000 operations. Python unit tests check the frozen layout, replacement policy, accounting invariant, failure behavior, and commitments. A separately written C++ implementation must match every fixed-vector field in CI.

The holdout can be reproduced with:

```console
python3 contrib/pow_research_cpp/frontier_pebbling_attacker_v1.py \
  --profile standard --seed-start 8 --seeds 8 --operation-limit 5000000 \
  --output build/pow-v1-frontier-pebbling-holdout.json
```

## Interpretation and limits

This is meaningful adversarial evidence because it is a second, independently structured bounded strategy and its rules were not fitted to the observed holdout. It is not evidence that no better strategy exists. It also does not measure controlled-host throughput, energy, GPU or ASIC advantage, quantum advantage, or actual mining decentralization.

The time-memory gate remains **OPEN** and **NOT ASSESSED**. A gate-relevant measurement requires an attacker that emits exact canonical proofs within the byte ceiling, controlled physical-host measurements, and independent review. The next step is to publish the bounded attacker interface for outside attack review instead of continuing to tune internal policies against public seeds.
