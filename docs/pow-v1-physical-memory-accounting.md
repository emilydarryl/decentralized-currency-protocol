# Soveroot PoW v1 Physical-Memory Accounting

Status: **NON-CONSENSUS PILOT; HIDDEN MEMORY EXPOSED; TIME-MEMORY GATE NOT ASSESSED**

This milestone deducts native recursion-stack and allocator allowances from the same 131,072-byte half-scratch budget used by the attack arena. It also replaces a growing C++ transcript buffer with a fixed-size rolling commitment and adds whole-process resident-memory diagnostics for Linux.

## Plain-language result

The previous model said the attacker had half the normal notebook space, but the program also kept some working notes elsewhere. Its recursive function used the computer's real call stack, and the C++ audit log grew every time a missing value was recovered. On one pathological seed, that log alone could grow to tens of megabytes even though the modeled budget was only 128 KiB.

The new mode pays those costs up front. Of the 131,072-byte allowance:

- 85,504 bytes remain for the arena;
- 40,960 bytes reserve up to twenty native stack frames at 2,048 bytes each;
- 4,096 bytes cover allocator and temporary-allocation slack; and
- 512 bytes remain reserved for fixed machine state.

The audit transcript is now a 48-byte rolling hash. It never grows with the number of recoveries.

With less hidden memory, the eight tested attackers reach between step 641 and step 853 of a 98,304-step job. The previous operation-bounded maximum was 999. Every case spends exactly five million charged operations and refuses without a proof.

## Complete holdout

| Seed | Exact prefix | Recovered misses | Maximum depth | Proof |
| ---: | ---: | ---: | ---: | :---: |
| 0 | 669 | 22 | 8 | No |
| 1 | 768 | 30 | 7 | No |
| 2 | 773 | 30 | 6 | No |
| 3 | 853 | 37 | 5 | No |
| 4 | 848 | 41 | 6 | No |
| 5 | 641 | 21 | 7 | No |
| 6 | 755 | 33 | 6 | No |
| 7 | 771 | 30 | 6 | No |

The median prefix is 769.5 and the maximum observed recursion depth is eight. The reserve permits twenty frames, so the screened executions do not approach the declared depth capacity.

## Compiler and process checks

The Linux C++ build emits GCC `-fstack-usage` records. A symbol-specific verifier makes CI fail unless `RecursiveRegenerator::ValueAt` is classified as `static` or `dynamic,bounded` and its reported bound is no greater than the 2,048-byte per-frame allowance. Unbounded dynamic stack use is rejected. The arena vector also refuses if its allocated capacity exceeds its requested bytes plus the allocator allowance.

A separate harness runs the ordinary evaluator and attacker under `/usr/bin/time -v`. It records whole-process peak resident set size and page faults. Whole-process RSS includes executable code, libraries, the epoch dataset, and other state shared with an ordinary miner, so it is reported separately from the 131,072-byte attack-specific budget.

GitHub's shared runner is useful for checking the measurement pipeline but cannot pass a hardware gate. Its CPU allocation, contention, memory placement, and host configuration are not controlled.

The first retained run reported a 352-byte compiler-bounded recursive frame. Across eight paired processes, median whole-process RSS was 7,806,976 bytes for ordinary evaluation and 7,897,088 bytes for the attacker. Those totals include the executable, runtime, and 2 MiB dataset; they are diagnostic rather than proof of the 131,072-byte attack-specific limit. The [raw evidence and interpretation](research-results/2026-08-14-github-ubuntu-v1-physical-memory.md) are preserved with the runner identifier and integrity hashes.

## What this establishes

This closes two known accounting gaps: native stack capacity now reduces the usable attack arena, and transcript memory is constant rather than recovery-dependent. Python and C++ independently commit to the same deterministic refusal boundaries.

It does not prove that all allocator or runtime memory is bounded on every implementation, and it does not pass the time-memory gate. No reduced-memory attacker has completed an exact proof, no accepted-work throughput ratio exists, controlled measurements on three declared machines are absent, and a second independently reviewed attack model is still required.

The frozen method and holdout are [`physically_accounted_dependency_bundle_regeneration_v0.json`](../contrib/pow_research_v1/physically_accounted_dependency_bundle_regeneration_v0.json). Fixed vectors are [`physically_accounted_dependency_bundle_regeneration_v0.json`](../contrib/pow_research_v1/vectors/physically_accounted_dependency_bundle_regeneration_v0.json).
