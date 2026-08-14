# Soveroot PoW v1 Iterative Work-Stack Pilot

Status: **NON-CONSENSUS PILOT; HOLDOUT COMPLETE; TIME-MEMORY GATE NOT ASSESSED**

This milestone replaces the reduced-memory attacker's native recursive calls with twenty packed frames stored inside its already byte-accounted arena. It preserves the dependency-bundle algorithm and five-million-operation ceiling while removing the conservative 40,960-byte recursion reserve used by the previous physical-memory pilot.

## Plain-language result

Imagine that the attacker must recreate missing notebook pages. The earlier program left a chain of reminders on the computer's hidden call stack. We budgeted generously for those hidden reminders, which left less room in the attacker's notebook.

The new version puts every reminder on a numbered index card in a reserved drawer inside the notebook itself. Each card is exactly 104 bytes, the drawer holds twenty cards, and the program refuses if it would need a twenty-first. There is no recursive call chain. This makes the important working memory explicit, fixed, and independently encodable.

The reclaimed arena space lets the eight attackers progress farther than the prior physical-reserve screen: iterations 712 through 952 instead of 641 through 853. However, the complete job is 98,304 iterations. The best case reaches about 0.97%, every case spends exactly five million charged operations, and none produces a proof.

## Frozen accounting

| Component | Bytes |
| --- | ---: |
| Fixed control-state reserve | 512 |
| Allocator allowance | 4,096 |
| Preallocated arena | 126,464 |
| Total attack budget | 131,072 |

Inside the arena, 2,080 bytes hold twenty 104-byte work frames. The remainder contains the write bitmap, primary cache, twelve dependency-bundle checkpoints, and packed memo table. The rolling transcript remains 48 bytes with zero recovery-dependent growth. External storage, an offline schedule, and native recursion are forbidden.

The 512-byte fixed reserve is not a claim that a C++ function uses no native stack at all. CI asks GCC to classify `RecursiveRegenerator::ValueAtIterative` as statically or dynamically bounded and to report no more than 512 bytes for its nonrecursive control frame.

## Complete holdout

The nonce, eight seeds, memory partition, and operation limit were committed before the holdout ran.

| Seed | Exact prefix | Recovered misses | Explicit depth | Proof |
| ---: | ---: | ---: | ---: | :---: |
| 0 | 712 | 25 | 6 | No |
| 1 | 952 | 54 | 6 | No |
| 2 | 946 | 43 | 4 | No |
| 3 | 895 | 42 | 4 | No |
| 4 | 723 | 26 | 6 | No |
| 5 | 939 | 47 | 5 | No |
| 6 | 877 | 44 | 5 | No |
| 7 | 771 | 29 | 6 | No |

The median prefix is 886. Maximum observed explicit depth is six, below the capacity of twenty. Every exhaustion reason is `operation_limit` and every total is exactly 5,000,000.

## Independent checks

Python and C++ implement the same four-phase frame machine: enter, request the first dependency, receive it and request the second, then receive the second and advance the replay. Three frozen short vectors compare the complete deterministic JSON boundary, including layout, counters, exhaustion state, and transcript commitment. The Python test also rejects a direct self-call in the iterative worker.

The C++ parity and compiler-stack checks are authoritative only after Linux CI passes. They establish implementation agreement at the frozen vectors, not production safety or a proof-of-work gate.

## What this does and does not establish

This closes the known native-recursion accounting gap for this attacker design. Its suspended work is now visible inside one preallocated arena, and exhaustion remains fail closed.

It does not establish memory hardness. The attacker does not finish, so there is no accepted-work throughput ratio. Whole-process memory has not been measured on controlled hosts, allocator accounting still needs independent review, and another independently designed attack could be stronger. All mandatory proof-of-work gates therefore remain open.

The frozen method and holdout are [`iterative_work_stack_regeneration_v0.json`](../contrib/pow_research_v1/iterative_work_stack_regeneration_v0.json). Fixed cross-language vectors are [`vectors/iterative_work_stack_regeneration_v0.json`](../contrib/pow_research_v1/vectors/iterative_work_stack_regeneration_v0.json).
