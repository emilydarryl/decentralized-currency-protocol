# Soveroot PoW Research Harness

This package is a deterministic measurement harness for the candidate direction in [`docs/pow-vm-research.md`](../../docs/pow-vm-research.md).

> **NON-CONSENSUS:** This is not Soveroot's selected proof of work. Its VM, constants, encodings, vectors, and outputs may change or be rejected. Do not use it to validate blocks, build mining hardware, estimate profitability, or represent mainnet readiness.

## What it provides

- a canonical, integer-only Python interpreter;
- seed-derived programs and memory datasets;
- a balanced opcode multiset so every generated program performs a minimum number of dataset reads, scratchpad reads, and scratchpad writes;
- per-attempt scratchpad mutation;
- SHA3-384 and SHAKE-256 domain-separated research primitives;
- reproducible vectors checked in CI;
- JSON benchmark output; and
- parameter sweeps for comparing trends.

The current implementation prioritizes clarity and differential testing. Python timing is not evidence of CPU/GPU competitiveness, memory hardness, ASIC resistance, or quantum safety.

## Commands

Run from the repository root:

```bash
python3 -m unittest discover -s test/pow_research -p 'test_*.py'
python3 -m contrib.pow_research.generate_vectors
python3 -m contrib.pow_research.benchmark --attempts 5
python3 -m contrib.pow_research.sweep --dataset-kib 64 1024 --scratchpad-kib 8 128
```

`prepare_epoch()` creates the seed-dependent program and dataset once. `evaluate()` then tests individual header/nonce attempts with isolated scratchpad state. This separation makes dataset initialization and per-attempt execution costs visible instead of combining them into one misleading number.

## Interpretation rules

- Compare parameter trends only on the same machine and software revision.
- Preserve raw JSON, platform information, commit ID, compiler/runtime versions, and thermal conditions for published results.
- Do not extrapolate Python ratios into ASIC economics.
- Treat a fast or slow seed as a potential program-generation flaw and preserve it for analysis.
- Any change to semantics requires regenerating the vector file and explaining the incompatibility.

The independent C++ implementation in [`../pow_research_cpp/`](../pow_research_cpp/) consumes the same vectors without binding to this interpreter. Both implementations remain research-only.
