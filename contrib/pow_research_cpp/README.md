# Standalone C++ PoW Research Implementation

This directory contains an independent C++20 implementation of the non-consensus Soveroot PoW research VM. It exists to detect underspecified behavior and cross-language divergence in the canonical Python research harness.

> **NON-CONSENSUS:** This executable is not linked into `sovrd`, the CMake build, block validation, mining RPCs, or labnet. Matching these vectors does not make the algorithm suitable for deployment.

Build and compare it with the checked-in vectors from the repository root:

```bash
mkdir -p build
c++ -std=c++20 -O2 -Wall -Wextra -Werror \
  contrib/pow_research_cpp/powvm.cpp -o build/powvm_cpp
python3 test/pow_research/run_cpp_vectors.py --binary build/powvm_cpp
```

The implementation includes its own SHA3-384 and SHAKE-256 sponge rather than calling Python or wrapping the reference interpreter. The differential driver loads the same `v0.json` vectors used by the Python tests and compares every digest and final register.

This version is designed for correctness review. It is not an optimized miner or a meaningful CPU/GPU/ASIC benchmark.
