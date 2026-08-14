# Soveroot PoW v1 Exact Bounded-Pebbling Plan

Status: **PREDECLARED NON-CONSENSUS ATTACK PLAN; NOT AN IMPLEMENTATION OR RESULT**

This plan defines the next adversarial milestone for the v1 proof-of-work candidate. Its purpose is to determine whether an exact miner can trade half the declared scratch memory for an acceptable amount of recomputation without hiding state in external storage or uncounted process memory.

## Research question

Can an executable attacker reproduce every canonical v1 output while keeping its entire attack-specific state within 50% of the declared scratchpad bytes, and what fraction of ordinary throughput does it retain on controlled physical hardware?

At the standard profile, the declared scratchpad is 262,144 bytes. The attack-state ceiling is therefore 131,072 bytes. Dataset and epoch context are reported separately because they are shared by ordinary and attacking evaluators; both incremental attack memory and whole-process peak resident memory must be measured.

## Why another attack is required

The no-spill pilot used half a scratchpad for retained words but temporarily allocated a complete replay scratchpad, producing 150% peak scratch allocation. The budgeted-cache screen accounted for value metadata but did not regenerate values after a miss. Neither executes an exact proof within the half-memory ceiling.

Addresses in v1 depend on evolving values, so a register-only checkpoint cannot resume the computation. A complete scratchpad checkpoint exceeds the entire attack budget. The executable construction must instead use a bounded pebbling or recursive replay schedule over exact, versioned data dependencies.

## Required components

1. **Exact dynamic dependency graph.** Each materialized read identifies the precise write generation that produced its value. The graph extractor commits to the trace but is not part of the timed attacker.
2. **Reference planner.** An offline planner explores checkpoint and eviction schedules under explicit byte costs. It may establish a lower bound or select schedules, but future knowledge and planner memory must be disclosed and cannot be counted as executable evidence.
3. **Online bounded evaluator.** The timed attacker executes without a trace file, spill file, memory-mapped backing store, hidden full scratchpad, or network service.
4. **Exact replay engine.** A missing value is regenerated from an earlier admissible state or recursively regenerated dependencies. It must not allocate an ordinary full scratchpad.
5. **Independent oracle.** The ordinary evaluator supplies expected digests, final registers, and memory commitments. Every attacked output must match.
6. **Memory instrumentation.** The harness records logical budget use, allocator-requested bytes, high-water resident set size, shared dataset bytes, stack limits, mapped files, and temporary-file activity.

## Budget accounting

The attack-specific ceiling includes, at minimum:

- retained 64-bit values;
- word indices, write generations, and validity tags;
- replacement or schedule metadata;
- checkpoint registers, accumulators, iteration positions, and address state;
- recursion frames, work queues, dependency stacks, and cycle guards;
- allocator headers, alignment loss, and container capacity not currently occupied;
- any compressed state after charging its actual stored bytes.

Executable code and the read-only epoch dataset are reported but are not charged against the scratch-specific half-memory ceiling because the ordinary evaluator uses them too. Any extra dataset copy, generated trace, lookup table, page cache, or process used only by the attacker is attack state and must be charged.

## Development stages

### Stage A: graph and byte model

- Extend the existing trace with exact read-from version edges.
- Publish graph commitments for the fixed smoke and standard seeds.
- Define packed and conservative byte layouts and test their size assumptions.
- Verify that the graph alone is never presented as a valid attack result.

Implementation status: **complete as a deterministic diagnostic**. The Python and C++ extractors, canonical encoding, fixed commitments, and logical byte layouts are documented in [the versioned scratch-dependency graph note](pow-v1-versioned-graph.md). This does not complete or partially pass the time-memory gate.

### Stage B: offline pebbling lower bound

- Search schedules under the 50% byte ceiling.
- Count recomputed nodes, dependency depth, peak live values, and schedule bytes.
- Report future knowledge and planner resources separately.
- Use the result only to bound what an online evaluator might achieve.

Implementation status: **complete as an offline graph study**. The initial floor is documented in [the offline pebbling lower-bound note](pow-v1-pebbling-lower-bound.md). The subsequent [offline pebbling schedule note](pow-v1-offline-pebbling-schedule.md) records concrete recursive action streams, replay work, dependency depth, retained and transient values, and explicit schedule bytes. Neither result is an executable attacker, throughput estimate, or gate result.

### Stage C: exact online attacker

- Execute the selected bounded schedule without reading the offline trace.
- Reject startup if its configured structures can exceed the byte ceiling.
- Fail the test on any digest, register, or memory-commitment mismatch.
- Detect file-backed mappings, temporary files, and helper processes.

Implementation status: **fail-closed execution scaffold implemented; exact attacker incomplete**. The [online bounded-probe note](pow-v1-online-bounded-probe.md) documents a one-arena half-scratch layout and independently matched exact-prefix refusal boundaries. It does not yet reconstruct a missing value, emit an exact proof, measure actual peak memory, or assess the gate.

The subsequent [bounded first-reconstruction result](pow-v1-bounded-first-reconstruction.md) exactly reconstructs one missing value and matching historical machine state within that arena, retries the interrupted iteration, and refuses at the next miss. Repeated reconstruction, exact final outputs, and physical memory measurement remain incomplete.

The [bounded repeated-reconstruction result](pow-v1-bounded-repeated-reconstruction.md) recovers 109–137 missing values across the fixed standard cases before its sparse replay table fills. It reports cumulative work and the precise fail-closed exhaustion boundary. Checkpointed or recursive recovery, exact final outputs, and physical memory measurement remain incomplete.

The [packed checkpoint pilot](pow-v1-packed-checkpoint-reconstruction.md) replaces per-value tags with bitmap rank, raising standard replay capacity from 4,940 to 11,449 values and extending seed zero to iteration 6,615. It also exposes 180.8 GB of charged insertion movement, motivating a block-gap or indexed layout.

The [paged-gap pilot](pow-v1-paged-gap-reconstruction.md) replaces global shifts with 32-value physical pages and a logical page directory. On standard seed zero it reduces charged movement to 183.3 MB, approximately 986 times less, but fragmented pages exhaust at 6,667 occupied values and linear lookup charges 489.8 million directory probes. The next construction must index page counts and rebalance gaps without exceeding the same byte ceiling.

The [indexed-gap pilot](pow-v1-indexed-gap-reconstruction.md) adds a byte-accounted page-count Fenwick tree and bounded adjacent-page borrowing. It raises standard seed-zero utilization from 59.2% to 90.8% and advances the exact prefix from iteration 3,599 to 5,759. It still exhausts without a proof after 5.13 million attempted replay iterations, so the next construction should add byte-accounted time checkpoints or hierarchical replay rather than continue optimizing value layout alone.

The [time-checkpoint feasibility screen](pow-v1-time-checkpoint-screen.md) evaluates 17 cuts using full snapshots, immutable snapshot-plus-delta storage, and an optimistic one-store staged model with exact future knowledge. On standard seed zero, every optimistic cut requires 155,490 bytes, 18.63% above the 131,072-byte ceiling; every naive cut also fails. A single no-regeneration checkpoint therefore does not solve the capacity failure. The next Stage C implementation must recursively regenerate exact values with its cache, identity metadata, work stack, transient values, and control state charged inside one preallocated arena.

The [first recursive-regeneration pilot](pow-v1-recursive-regeneration.md) now performs that core operation: an exact missing value is reconstructed through recursively requested earlier dependencies using a packed memo and a logical 20-frame reserve inside one half-scratch arena. The standard seed-zero run recovers its first miss after 25,281 replay iterations at depth 3 and then deliberately refuses without a digest at the next miss. Repeated recursive recovery, final exact outputs, allocation tuning, actual stack accounting, and physical-memory measurement remain incomplete.

The [repeated recursive-regeneration pilot](pow-v1-repeated-recursive-regeneration.md) persists that memo across successive misses and screens five primary-cache allocations under a one-million-iteration replay ceiling. The 1/64 baseline recovers 51 misses and reaches iteration 983; the 1/32 split reaches the longest screened prefix at iteration 999. Every allocation exhausts the work ceiling without a digest. Hierarchical replay, exact final outputs, explicit physical stack accounting, and controlled memory measurement remain incomplete.

The [total-operation-bounded bundle pilot](pow-v1-operation-bounded-dependency-bundle-regeneration.md) closes a later control gap by charging recursive calls, replay iterations, memo probes, and checkpoint-entry probes against one five-million-unit ceiling. All eight standard seeds terminate exactly at the bound without a proof. Prefixes range from 480 to 999, so the earlier replay-only seed-zero bundle record of 1,006 does not survive the combined accounting. Explicit physical stack, allocator, and resident-memory accounting remain incomplete.

The [physical-memory accounting pilot](pow-v1-physical-memory-accounting.md) deducts a 40,960-byte native-stack reserve and 4,096-byte allocator allowance before sizing the attack arena, replaces a recovery-dependent C++ transcript vector with a fixed rolling digest, validates compiler-reported recursive frame size, and records whole-process Linux RSS. The complete eight-seed prefixes range from 641 to 853 and no proof is produced. Shared-runner RSS is diagnostic only; a preallocated iterative work stack, exact final outputs, and controlled physical-host measurements remain incomplete.

The next predeclared pilot replaces recursive calls with twenty packed 104-byte frames stored in the existing arena frame reserve. It removes the native-stack reserve, retains the allocator allowance, and freezes nonce zero for eight standard holdout seeds plus three short cross-language vectors in [`iterative_work_stack_regeneration_v0.json`](../contrib/pow_research_v1/iterative_work_stack_regeneration_v0.json) before execution.

That iterative pilot is complete. The next independently structured screen replaces its twelve-entry linear checkpoint scan with a directly addressed four-level ladder. Sixty-four target-aware entries are split across strides 8, 64, 512, and 4,096; every lookup charges exactly four probes, all bytes remain in the same arena, and the fixed vectors and eight nonce-zero holdout seeds are frozen in [`hierarchical_checkpoint_ladder_v0.json`](../contrib/pow_research_v1/hierarchical_checkpoint_ladder_v0.json) before execution.

### Stage D: controlled measurement

- Measure ordinary and attacking implementations on at least three declared physical systems.
- Randomize paired run order and publish raw samples, compiler details, power settings, thermals, and OS configuration.
- Run at least two independently reviewed attack models as required by the gate policy.
- Report the median accepted-work throughput ratio and confidence interval without rounding across a threshold.

## Acceptance and interpretation

The implementation milestone is complete only when all fixed test vectors match and the attack demonstrates, rather than estimates, its byte ceiling. That milestone still does not pass the time-memory gate.

Under the frozen policy:

- throughput at half memory of at most 40% is a pass result;
- more than 40% and at most 65% requires redesign;
- more than 65% rejects the candidate's memory-hardness claim.

Those classifications require the policy's minimum evidence, independent review, and controlled hosts. Until then the public state remains `OPEN` and `NOT ASSESSED`.

## Failure conditions

The run is invalid if it relies on an external spill store, uncharged cache, unbounded planner state during timed execution, full transient replay scratchpad, hidden worker process, or an output weaker than the canonical proof. An implementation that cannot fit the half-memory ceiling is still useful negative evidence and must be preserved.
