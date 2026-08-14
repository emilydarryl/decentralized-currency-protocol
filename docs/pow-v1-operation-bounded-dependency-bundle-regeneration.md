# Soveroot PoW v1 Total-Operation-Bounded Bundle Regeneration

Status: **NON-CONSENSUS PILOT; WORK-BOUND GAP CLOSED; TIME-MEMORY GATE NOT ASSESSED**

This experiment places one deterministic ceiling around the direct-dependency bundle attack. Every recursive call, replayed VM iteration, memo access, and checkpoint-entry scan consumes one unit from the same five-million-operation allowance. All eight predetermined standard seeds finish the experiment by refusing without a proof.

## Plain-language result

The previous attacker had a one-million limit on rebuilding notebook pages, but some bookkeeping was free. One seed could therefore spend minutes making recursive requests and searching bookmarks even though its replay counter had not reached the limit.

The new rule gives the attacker five million tokens. Asking for a value costs one token, redoing one calculation step costs one token, checking the memo table costs one token, and checking one bookmark costs one token. When the tokens are gone, the experiment stops before doing more work.

This closes the runaway-work loophole. It also removes the bundle method's small seed-zero record: that seed now reaches step 999 rather than 1,006. Across eight seeds, the attacker reaches between step 480 and step 999 of a 98,304-step job. It never finishes and never produces a proof.

That is useful negative evidence, not proof that mining will be decentralized. It says this particular half-memory shortcut is bounded and unsuccessful under this allowance. A smarter shortcut may still exist.

## Exact operation rule

The counter charges one unit immediately before each of these events:

- entering a recursive `value_at` call;
- executing one replay iteration;
- performing one memo get or put; and
- probing one checkpoint-table entry.

The implementation refuses before an event that would push the total above the limit. Therefore:

`total = recursive calls + replay iterations + memo probes + checkpoint probes`

Every screened result ends at exactly 5,000,000. The earlier one-million replay ceiling remains as a secondary safety limit, but the combined ceiling is reached first.

## Complete eight-seed holdout

| Seed | Exact prefix | Recovered misses | Calls | Replay steps | Memo probes | Checkpoint probes | Proof |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| 0 | 999 | 53 | 1,991,227 | 995,588 | 1,989,233 | 23,952 | No |
| 1 | 952 | 54 | 1,986,756 | 993,351 | 1,985,465 | 34,428 | No |
| 2 | 946 | 41 | 1,986,531 | 993,246 | 1,984,535 | 35,688 | No |
| 3 | 480 | 1,585,142 | 2,305,646 | 360,252 | 2,304,822 | 29,280 | No |
| 4 | 779 | 30 | 1,985,804 | 992,887 | 1,983,149 | 38,160 | No |
| 5 | 715 | 22 | 1,981,411 | 990,695 | 1,979,378 | 48,516 | No |
| 6 | 968 | 51 | 1,985,607 | 992,778 | 1,984,547 | 37,068 | No |
| 7 | 887 | 42 | 1,982,890 | 991,424 | 1,981,970 | 43,716 | No |

The median prefix is 916.5, the minimum is 480, and the maximum is 999. Seed 3 repeatedly reconstructs values that are then displaced before the main calculation can progress. Those recoveries are usually cheap memo hits, but every request and memo access is charged, so the case terminates deterministically. The high recovered-miss count is evidence of cache thrashing, not useful progress.

## Interpretation and limits

The result rejects the idea that the four-value bundle policy has demonstrated a general improvement. Under the more complete work accounting, it does not beat the prior 999-step record. It does establish a reproducible stopping rule and completes the holdout that the replay-only experiment could not finish.

The time-memory gate remains open. Logical arena bytes are accounted, but the physical call stack, Python and C++ allocator overhead, process peak resident memory, throughput, energy, GPUs, FPGAs, and ASICs are not measured. No claim of production memory hardness or mining decentralization follows from this result.

The machine-readable method and full holdout are [`operation_bounded_dependency_bundle_regeneration_v0.json`](../contrib/pow_research_v1/operation_bounded_dependency_bundle_regeneration_v0.json). Small fixed vectors are [`operation_bounded_dependency_bundle_regeneration_v0.json`](../contrib/pow_research_v1/vectors/operation_bounded_dependency_bundle_regeneration_v0.json), with independent Python/C++ comparison in CI.
