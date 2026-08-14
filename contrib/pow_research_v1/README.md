# Soveroot PoW v1 Research Candidate

This package implements the v1 workload described by [pow-v1-candidate-spec.md](../../docs/pow-v1-candidate-spec.md). It is isolated from v0 and from all node consensus and mining code.

> **NON-CONSENSUS:** This candidate is an experiment. Passing its vectors establishes deterministic agreement only; it does not establish memory hardness, specialization resistance, quantum resistance, profitability, or decentralization.

The design makes five deliberate changes from v0:

- fixed work proportional to scratchpad words and pass count;
- a balanced, seed-derived operation schedule with no variable instruction-count parameter;
- one dependent dataset read, two dependent scratchpad reads, and two writes per mixing iteration;
- zero-initialized scratch allocation instead of cryptographic expansion; and
- fixed-size finalization instead of hashing the entire scratchpad.

Run the Python tests and regenerate vectors from the repository root:

```bash
python3 -m unittest discover -s test/pow_research -p 'test_*.py'
python3 -m contrib.pow_research_v1.generate_vectors
```

The fixed-size memory commitment is not proof that retaining the declared scratchpad is optimal. That claim requires the time-memory-tradeoff experiments frozen in [pow-evaluation-gates.md](../../docs/pow-evaluation-gates.md).

The machine-readable copy of the predeclared v1 workload screens is [`screening_v0.json`](screening_v0.json). It is consumed by the standalone v1 report renderer; changing it requires the same versioned justification as changing the human-readable objectives.

Adversarial methods are versioned separately. The no-spill exact-output replay baseline is documented in [`recomputation_baseline_v0.json`](recomputation_baseline_v0.json) and [the corresponding method note](../../docs/pow-v1-recomputation-baseline.md). Its 150% peak scratch allocation makes it explicitly ineligible for the half-memory gate.

The metadata-aware cache lower-bound method is frozen in [`budgeted_cache_screen_v0.json`](budgeted_cache_screen_v0.json) and [its method note](../../docs/pow-v1-budgeted-cache-screen.md). It compares online LRU with an offline-optimal oracle under an explicit half-scratch byte budget; misses remain diagnostic rather than valid proofs.

Bounded-pebbling Stage A is implemented by [`versioned_graph.py`](versioned_graph.py) and the independent C++ `graph` mode. The byte-level method is frozen in [`versioned_graph_v0.json`](versioned_graph_v0.json), and fixed canonical, smoke, and standard commitments are under [`vectors/`](vectors/). The graph identifies exact scratch write generations but is a full-memory offline diagnostic, never an executable reduced-memory attack.

Stage B's optimistic cut-set planner is implemented by [`pebbling_lower_bound.py`](pebbling_lower_bound.py). Its frozen method is [`pebbling_lower_bound_v0.json`](pebbling_lower_bound_v0.json), with fixed results in [`vectors/pebbling_lower_bound_v0.json`](vectors/pebbling_lower_bound_v0.json). It provides a floor on future replay work under free future knowledge and control state; it is not an executable schedule or time-memory gate assessment.

Stage B's concrete graph-only schedule is implemented by [`offline_pebbling_schedule.py`](offline_pebbling_schedule.py). Its frozen method is [`offline_pebbling_schedule_v0.json`](offline_pebbling_schedule_v0.json), with fixed commitments in [`vectors/offline_pebbling_schedule_v0.json`](vectors/offline_pebbling_schedule_v0.json). It emits recursive producer postorders and reports schedule bytes, but cannot execute the historical v1 VM state and is not a reduced-memory miner or gate assessment.

Stage C begins with the fail-closed [`bounded_probe.py`](bounded_probe.py) and independent C++ `bounded-probe` mode. The frozen method is [`bounded_probe_v0.json`](bounded_probe_v0.json), with fixed refusal boundaries in [`vectors/bounded_probe_v0.json`](vectors/bounded_probe_v0.json). It executes exact online prefixes inside a logically admitted arena and emits no digest after a materialized miss; it has no reconstruction engine and does not assess a gate.

The first reconstruction step is implemented by [`bounded_reconstruction.py`](bounded_reconstruction.py) and independent C++ `bounded-reconstruct-one` mode. Its frozen method is [`bounded_reconstruction_v0.json`](bounded_reconstruction_v0.json), with fixed cross-implementation results in [`vectors/bounded_reconstruction_v0.json`](vectors/bounded_reconstruction_v0.json). It exactly replays and validates one missing value inside the preallocated arena, then refuses at the next miss without an output.

Repeated reconstruction is implemented by [`repeated_reconstruction.py`](repeated_reconstruction.py) and independent C++ `bounded-reconstruct-repeated` mode. Its frozen method is [`repeated_reconstruction_v0.json`](repeated_reconstruction_v0.json), with fixed cross-implementation results in [`vectors/repeated_reconstruction_v0.json`](vectors/repeated_reconstruction_v0.json). It repeats exact recovery until the sparse replay table fills, then refuses without an output.

The packed checkpoint experiment is implemented by [`packed_reconstruction.py`](packed_reconstruction.py) and independent C++ `bounded-reconstruct-packed` mode. Its frozen method is [`packed_reconstruction_v0.json`](packed_reconstruction_v0.json), with fixed results in [`vectors/packed_reconstruction_v0.json`](vectors/packed_reconstruction_v0.json). Bitmap rank more than doubles replay-value capacity, while explicitly charging the large byte movement caused by sorted insertion.

The paged-gap experiment is implemented by [`paged_gap_reconstruction.py`](paged_gap_reconstruction.py) and independent C++ `bounded-reconstruct-paged` mode. Its frozen method is [`paged_gap_reconstruction_v0.json`](paged_gap_reconstruction_v0.json), with fixed results in [`vectors/paged_gap_reconstruction_v0.json`](vectors/paged_gap_reconstruction_v0.json). Fixed-size pages reduce charged insertion movement by roughly three orders of magnitude on the standard seed-zero pilot, while exposing fragmentation and linear page lookup as the next constraints.

The indexed-gap experiment is implemented by [`indexed_gap_reconstruction.py`](indexed_gap_reconstruction.py) and independent C++ `bounded-reconstruct-indexed-gap` mode. Its frozen method is [`indexed_gap_reconstruction_v0.json`](indexed_gap_reconstruction_v0.json), with fixed results in [`vectors/indexed_gap_reconstruction_v0.json`](vectors/indexed_gap_reconstruction_v0.json). A page-count Fenwick index and bounded neighbor borrowing raise standard page utilization to 90.8% and extend the exact prefix, but still exhaust before producing a proof.

The first recursive-regeneration experiment is implemented by [`recursive_regeneration.py`](recursive_regeneration.py) and independent C++ `recursive-regenerate-first` mode. Its frozen method is [`recursive_regeneration_v0.json`](recursive_regeneration_v0.json), with fixed results in [`vectors/recursive_regeneration_v0.json`](vectors/recursive_regeneration_v0.json). It reconstructs one exact historical value by recursively replaying missing dependencies inside the logical half-scratch arena, retries primary execution, and then refuses without a proof at the next miss.

Repeated recursive regeneration is implemented by [`repeated_recursive_regeneration.py`](repeated_recursive_regeneration.py) and independent C++ `recursive-regenerate-repeated` mode. Its frozen method is [`repeated_recursive_regeneration_v0.json`](repeated_recursive_regeneration_v0.json), with fixed results in [`vectors/repeated_recursive_regeneration_v0.json`](vectors/repeated_recursive_regeneration_v0.json). Persistent memo reuse recovers 51 successive standard seed-zero misses under a one-million-iteration replay limit, while a five-point allocation screen shows that primary and memo capacity interact non-monotonically. Every case refuses without a proof.

Checkpoint-assisted recursion is implemented by [`checkpoint_recursive_regeneration.py`](checkpoint_recursive_regeneration.py) and independent C++ `recursive-regenerate-checkpoint` mode. Its frozen rejection record is [`checkpoint_recursive_regeneration_v0.json`](checkpoint_recursive_regeneration_v0.json), with fixed results in [`vectors/checkpoint_recursive_regeneration_v0.json`](vectors/checkpoint_recursive_regeneration_v0.json). The best screened checkpoint allocation reaches iteration 892 versus 999 without checkpoints, so this policy is rejected rather than promoted.

Target-aware checkpoints use the same module and independent C++ `recursive-regenerate-target-checkpoint` mode. The frozen method is [`target_checkpoint_regeneration_v0.json`](target_checkpoint_regeneration_v0.json), with fixed results in [`vectors/target_checkpoint_regeneration_v0.json`](vectors/target_checkpoint_regeneration_v0.json). Each 88-byte entry binds machine state to one exact target value, raising the 1/128 allocation from iteration 719 to 999 without increasing recursion depth. It ties rather than exceeds the global record and produces no proof.

Direct-dependency bundles use the same module and independent C++ `recursive-regenerate-dependency-bundle` mode. The frozen method is [`dependency_bundle_regeneration_v0.json`](dependency_bundle_regeneration_v0.json), with fixed results in [`vectors/dependency_bundle_regeneration_v0.json`](vectors/dependency_bundle_regeneration_v0.json). Each 120-byte entry carries four tagged values already present in one exact replay step. Twelve entries raise the standard seed-zero prefix from the prior 999 record to 1,006, but the partial holdout is mixed, one later seed exposes unbounded call/probe time beyond the replay counter, and no proof is produced.

Total-operation-bounded bundles use `reconstruct_repeatedly_with_operation_bounded_dependency_bundles` and independent C++ `recursive-regenerate-operation-bounded-bundle` mode. The frozen method and eight-seed holdout are [`operation_bounded_dependency_bundle_regeneration_v0.json`](operation_bounded_dependency_bundle_regeneration_v0.json), with fixed results in [`vectors/operation_bounded_dependency_bundle_regeneration_v0.json`](vectors/operation_bounded_dependency_bundle_regeneration_v0.json). One five-million-unit ceiling charges recursive calls, replay iterations, memo probes, and checkpoint-entry probes. All eight cases stop exactly at the ceiling without a proof; prefixes range from 480 to 999, so the earlier seed-zero bundle advantage does not survive the combined accounting.

Physically accounted bundles use `reconstruct_repeatedly_with_physically_accounted_dependency_bundles` and independent C++ `recursive-regenerate-physically-accounted-bundle` mode. The frozen method and holdout are [`physically_accounted_dependency_bundle_regeneration_v0.json`](physically_accounted_dependency_bundle_regeneration_v0.json), with fixed results in [`vectors/physically_accounted_dependency_bundle_regeneration_v0.json`](vectors/physically_accounted_dependency_bundle_regeneration_v0.json). Native stack and allocator allowances reduce the arena to 85,504 bytes, and a rolling 48-byte transcript removes recovery-dependent growth. Eight standard prefixes range from 641 to 853; every case refuses without a proof.
