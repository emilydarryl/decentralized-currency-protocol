# Standalone C++ PoW Research Implementation

This directory contains an independent C++20 implementation of the non-consensus Soveroot PoW research VM. It exists to detect underspecified behavior and cross-language divergence in the canonical Python research harness.

> **NON-CONSENSUS:** This executable is not linked into `sovrd`, the CMake build, block validation, mining RPCs, or labnet. Matching these vectors does not make the algorithm suitable for deployment.

Build and compare it with the checked-in vectors from the repository root:

```bash
mkdir -p build
c++ -std=c++20 -O2 -Wall -Wextra -Werror \
  contrib/pow_research_cpp/powvm.cpp -o build/powvm_cpp
python3 test/pow_research/run_cpp_vectors.py --binary build/powvm_cpp
python3 contrib/pow_research_cpp/benchmark_matrix.py \
  --binary build/powvm_cpp --profile standard --output pow-matrix.json
```

The implementation includes its own SHA3-384 and SHAKE-256 sponge rather than calling Python or wrapping the reference interpreter. The differential driver loads the same `v0.json` vectors used by the Python tests and compares every digest and final register.

This version is designed for correctness review. It is not an optimized miner or a meaningful CPU/GPU/ASIC benchmark.

The separate `powvm_v1.cpp` executable independently implements the byte-level v1 candidate specification. It does not call, import, or link the Python candidate or the v0 C++ VM. Build and compare it with:

```bash
c++ -std=c++20 -O2 -Wall -Wextra -Werror \
  contrib/pow_research_cpp/powvm_v1.cpp -o build/powvm_v1_cpp
python3 test/pow_research/run_cpp_vectors_v1.py --binary build/powvm_v1_cpp
```

Agreement on the v1 vectors establishes deterministic interoperability only. Phase timing and parameter sweeps must be added and evaluated against the predeclared v1 workload objectives before hardware-comparison work begins.

The v1 executable now has an observational benchmark mode that separates input setup, zero-filled scratchpad allocation, mixing, and fixed-size finalization without changing output semantics. Run its bounded smoke matrix and renderer with:

```bash
python3 contrib/pow_research_cpp/benchmark_matrix_v1.py \
  --binary build/powvm_v1_cpp --profile smoke --output build/pow-v1-matrix.json
python3 contrib/pow_research_cpp/render_report_v1.py \
  --matrix build/pow-v1-matrix.json \
  --gates contrib/pow_research/gates_v0.json \
  --screening contrib/pow_research_v1/screening_v0.json \
  --label "local smoke" --output build/pow-v1-report.md
```

The manual `PoW v1 CPU research benchmark` workflow runs the standard profile and preserves raw samples plus the rendered informational report for 14 days.

The separate half-memory attack harness compares the normal backend with an exact-output backend that retains even scratchpad words in process and spills odd words to a temporary file:

```bash
python3 test/pow_research/run_cpp_half_memory_vectors_v1.py --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/half_memory_attack_v1.py \
  --binary build/powvm_v1_cpp --profile smoke \
  --output build/pow-v1-half-memory-matrix.json
python3 contrib/pow_research_cpp/render_half_memory_report_v1.py \
  --matrix build/pow-v1-half-memory-matrix.json \
  --gates contrib/pow_research/gates_v0.json \
  --method contrib/pow_research_v1/half_memory_attack_v0.json \
  --label "local smoke" --output build/pow-v1-half-memory-report.md
```

This backend retains exactly half the logical scratchpad byte array and must reproduce every canonical output. It uses external storage, does not bound the operating system page cache, does not measure physical peak memory, and is not optimized. It is therefore an attack-development baseline, not a result of the mandatory time-memory-tradeoff gate. The manual `PoW v1 half-memory attack benchmark` workflow preserves its paired raw samples and report.

Trace mode records the exact dynamic scratchpad access stream without changing the canonical digest or memory commitment. The dependency matrix summarizes cold reads, materialized reads, offline live-value pressure, and simulated half- and quarter-capacity LRU misses. The paired batch harness separately measures sequential batches through 4,096 attempts:

```bash
python3 test/pow_research/run_cpp_trace_vectors_v1.py --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/dependency_trace_v1.py \
  --binary build/powvm_v1_cpp --profile smoke --output build/pow-v1-dependency.json
python3 contrib/pow_research_cpp/batch_amortization_v1.py \
  --binary build/powvm_v1_cpp --profile smoke --output build/pow-v1-batch.json
```

These are diagnostics for designing a no-spill recomputation attack and controlled facility testing. A full-memory trace, cache simulation, or sequential shared-runner batch cannot decide either mandatory gate.

The `graph` mode upgrades word-address traces into exact read-from identities. Every read names the last write generation for its word, and every write names the generation it replaces. Python and C++ commitments are checked against fixed vectors:

```bash
python3 test/pow_research/run_cpp_versioned_graph_vectors_v1.py --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/versioned_graph_v1.py \
  --profile standard --output build/pow-v1-versioned-graph.json
```

The graph uses the full ordinary scratchpad and is much larger than the attack budget. It is deterministic input for offline planning, not a valid reduced-memory proof or gate result.

The Stage B cut-set lower bound scans that graph under compact and conservative value-entry costs:

```bash
python3 contrib/pow_research_cpp/pebbling_lower_bound_v1.py \
  --profile standard --output build/pow-v1-pebbling-lower-bound.json
python3 contrib/pow_research_cpp/render_pebbling_lower_bound_report_v1.py \
  --matrix build/pow-v1-pebbling-lower-bound.json \
  --method contrib/pow_research_v1/pebbling_lower_bound_v0.json \
  --label "local" --output build/pow-v1-pebbling-lower-bound.md

python3 contrib/pow_research_cpp/offline_pebbling_schedule_v1.py \
  --profile standard --output build/pow-v1-offline-pebbling-schedule.json
python3 contrib/pow_research_cpp/render_offline_pebbling_schedule_report_v1.py \
  --matrix build/pow-v1-offline-pebbling-schedule.json \
  --method contrib/pow_research_v1/offline_pebbling_schedule_v0.json \
  --label "local" --output build/pow-v1-offline-pebbling-schedule.md

python3 test/pow_research/run_cpp_bounded_probe_vectors_v1.py \
  --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/bounded_probe_v1.py \
  --profile standard --output build/pow-v1-online-bounded-probe.json
python3 contrib/pow_research_cpp/render_bounded_probe_report_v1.py \
  --matrix build/pow-v1-online-bounded-probe.json \
  --method contrib/pow_research_v1/bounded_probe_v0.json \
  --label "local" --output build/pow-v1-online-bounded-probe.md

python3 test/pow_research/run_cpp_bounded_reconstruction_vectors_v1.py \
  --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/bounded_reconstruction_v1.py \
  --profile standard --output build/pow-v1-bounded-first-reconstruction.json
python3 contrib/pow_research_cpp/render_bounded_reconstruction_report_v1.py \
  --matrix build/pow-v1-bounded-first-reconstruction.json \
  --method contrib/pow_research_v1/bounded_reconstruction_v0.json \
  --label "local" --output build/pow-v1-bounded-first-reconstruction.md

python3 test/pow_research/run_cpp_repeated_reconstruction_vectors_v1.py \
  --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/repeated_reconstruction_v1.py \
  --profile standard --output build/pow-v1-bounded-repeated-reconstruction.json
python3 contrib/pow_research_cpp/render_repeated_reconstruction_report_v1.py \
  --matrix build/pow-v1-bounded-repeated-reconstruction.json \
  --method contrib/pow_research_v1/repeated_reconstruction_v0.json \
  --label "local" --output build/pow-v1-bounded-repeated-reconstruction.md

python3 test/pow_research/run_cpp_packed_reconstruction_vectors_v1.py \
  --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/packed_reconstruction_v1.py \
  --profile standard --seeds 1 --output build/pow-v1-packed-checkpoint-reconstruction.json
python3 contrib/pow_research_cpp/render_packed_reconstruction_report_v1.py \
  --matrix build/pow-v1-packed-checkpoint-reconstruction.json \
  --method contrib/pow_research_v1/packed_reconstruction_v0.json \
  --label "local" --output build/pow-v1-packed-checkpoint-reconstruction.md

python3 test/pow_research/run_cpp_paged_gap_reconstruction_vectors_v1.py \
  --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/paged_gap_reconstruction_v1.py \
  --profile standard --seeds 1 --output build/pow-v1-paged-gap-reconstruction.json
python3 contrib/pow_research_cpp/render_paged_gap_reconstruction_report_v1.py \
  --matrix build/pow-v1-paged-gap-reconstruction.json \
  --method contrib/pow_research_v1/paged_gap_reconstruction_v0.json \
  --label "local" --output build/pow-v1-paged-gap-reconstruction.md

python3 test/pow_research/run_cpp_indexed_gap_reconstruction_vectors_v1.py \
  --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/indexed_gap_reconstruction_v1.py \
  --profile standard --seeds 1 --output build/pow-v1-indexed-gap-reconstruction.json
python3 contrib/pow_research_cpp/render_indexed_gap_reconstruction_report_v1.py \
  --matrix build/pow-v1-indexed-gap-reconstruction.json \
  --method contrib/pow_research_v1/indexed_gap_reconstruction_v0.json \
  --label "local" --output build/pow-v1-indexed-gap-reconstruction.md

python3 test/pow_research/run_cpp_time_checkpoint_screen_vectors_v1.py \
  --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/time_checkpoint_screen_v1.py \
  --profile standard --seeds 1 --output build/pow-v1-time-checkpoint-screen.json
python3 contrib/pow_research_cpp/render_time_checkpoint_screen_report_v1.py \
  --matrix build/pow-v1-time-checkpoint-screen.json \
  --method contrib/pow_research_v1/time_checkpoint_screen_v0.json \
  --label "local" --output build/pow-v1-time-checkpoint-screen.md

python3 test/pow_research/run_cpp_recursive_regeneration_vectors_v1.py \
  --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/recursive_regeneration_v1.py \
  --profile standard --seeds 1 --output build/pow-v1-recursive-regeneration.json
python3 contrib/pow_research_cpp/render_recursive_regeneration_report_v1.py \
  --matrix build/pow-v1-recursive-regeneration.json \
  --method contrib/pow_research_v1/recursive_regeneration_v0.json \
  --label "local" --output build/pow-v1-recursive-regeneration.md

python3 test/pow_research/run_cpp_repeated_recursive_regeneration_vectors_v1.py \
  --binary build/powvm_v1_cpp
python3 test/pow_research/run_cpp_checkpoint_recursive_regeneration_vectors_v1.py \
  --binary build/powvm_v1_cpp
python3 contrib/pow_research_cpp/repeated_recursive_regeneration_v1.py \
  --profile standard --seeds 1 --output build/pow-v1-repeated-recursive-regeneration.json
python3 contrib/pow_research_cpp/render_repeated_recursive_regeneration_report_v1.py \
  --matrix build/pow-v1-repeated-recursive-regeneration.json \
  --method contrib/pow_research_v1/repeated_recursive_regeneration_v0.json \
  --label "local" --output build/pow-v1-repeated-recursive-regeneration.md
```

The planner is deliberately more powerful than any executable miner: it sees the full future graph and charges zero bytes for its schedule and control state. Its result is only a lower bound on replay work.

The standard matrix changes one parameter family at a time around a named baseline and measures eight deterministic seeds. It preserves raw per-attempt nanosecond samples, separates epoch preparation from nonce evaluation, reports an explicit working-set estimate, and summarizes cross-seed spread in parts per million. Published comparisons must use the same source revision, profile, compiler flags, power mode, and thermal conditions.

Each C++ attempt also reports four observational phases: input/register setup, scratchpad initialization, VM execution, and final hashing. These timers do not alter v0 semantics or outputs. Their purpose is to detect when setup or finalization masks the workload the experiment intends to study.

The matrix measures software behavior on a particular host. It cannot by itself measure energy, memory bandwidth, GPU performance, FPGA/ASIC cost, pool concentration, or quantum advantage.

The manual `PoW CPU research benchmark` GitHub workflow runs only when explicitly dispatched. It compiles the standalone executable, verifies the canonical vectors, produces raw JSON plus an informational Markdown report, and retains the artifact for 14 days. It deliberately does not run the full Bitcoin-derived node build or claim a gate result.
