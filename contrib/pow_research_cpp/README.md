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

The standard matrix changes one parameter family at a time around a named baseline and measures eight deterministic seeds. It preserves raw per-attempt nanosecond samples, separates epoch preparation from nonce evaluation, reports an explicit working-set estimate, and summarizes cross-seed spread in parts per million. Published comparisons must use the same source revision, profile, compiler flags, power mode, and thermal conditions.

Each C++ attempt also reports four observational phases: input/register setup, scratchpad initialization, VM execution, and final hashing. These timers do not alter v0 semantics or outputs. Their purpose is to detect when setup or finalization masks the workload the experiment intends to study.

The matrix measures software behavior on a particular host. It cannot by itself measure energy, memory bandwidth, GPU performance, FPGA/ASIC cost, pool concentration, or quantum advantage.

The manual `PoW CPU research benchmark` GitHub workflow runs only when explicitly dispatched. It compiles the standalone executable, verifies the canonical vectors, produces raw JSON plus an informational Markdown report, and retains the artifact for 14 days. It deliberately does not run the full Bitcoin-derived node build or claim a gate result.
