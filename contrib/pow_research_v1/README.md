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
