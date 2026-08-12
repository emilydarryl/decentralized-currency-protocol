# Soveroot Research Results

This directory preserves raw, versioned measurements and their human-readable reports. Results are evidence about a particular implementation, source revision, machine, compiler, and method. They are not consensus parameters or claims of production readiness.

## Adversarial screens

- [`2026-08-12-github-ubuntu-v1-dependency-batch.md`](2026-08-12-github-ubuntu-v1-dependency-batch.md) — exact full-memory dependency trace and sequential batch screen on shared GitHub runner `31633897277`. The median offline live set reached 56.96% of the scratchpad and a simulated half-capacity LRU missed 45.81% of materialized reads. Batch 4,096 reduced inclusive cost 12.52x versus batch one, while evaluation-only cost improved 1.04x. Neither mandatory gate passed because cache misses do not produce proofs and hardware occupancy was not established.
- [`2026-08-12-github-ubuntu-v1-dependency-trace.json`](2026-08-12-github-ubuntu-v1-dependency-trace.json) — raw per-seed dependency summaries and trace commitments. SHA3-384: `229c92b18944ebea4461bc5dc860ef550006399b2bba712ece9328867bb7af7042a64d28958d9bd021a78d05693616b9`.
- [`2026-08-12-github-ubuntu-v1-batch-amortization-summary.json`](2026-08-12-github-ubuntu-v1-batch-amortization-summary.json) — compact structured summary of batches through 4,096 attempts. The complete 5,594,524-byte timing matrix is workflow artifact `pow-v1-dependency-batch-31633897277` from run `31633897277`; SHA3-384: `83a1b7a61d936359528a9b1da34d9ff1eb8da5989317ab8af38bb65688ec458fef3411126f31de8a26e2752b09dada90`.
- [`2026-08-12-github-ubuntu-v1-half-memory-spill.md`](2026-08-12-github-ubuntu-v1-half-memory-spill.md) — first exact-output half-scratchpad storage attack on shared GitHub runner `31628959519`. All 24 paired attempts matched; the deliberately simple spill backend retained 3.91% of normal throughput. External storage, unmeasured OS cache and resident memory, and the absence of recomputation make the result informational only; the mandatory time-memory gate remains open.
- [`2026-08-12-github-ubuntu-v1-half-memory-spill.json`](2026-08-12-github-ubuntu-v1-half-memory-spill.json) — complete paired raw samples and spill-access counts. SHA3-384: `6693f66826146bb27e0be0351a3919165358a483b92077f7b706c6944a5032ade715de3aa4c94136c90cec66a2e68370`.

## CPU baselines

- [`2026-08-12-github-ubuntu-v1-standard.md`](2026-08-12-github-ubuntu-v1-standard.md) — first standard-profile v1 screen on shared GitHub runner `31623410165`. Every assessable predeclared workload-balance screen met its advance bound; no mandatory PoW gate passed.
- [`2026-08-12-github-ubuntu-v1-standard.json`](2026-08-12-github-ubuntu-v1-standard.json) — exact raw v1 matrix with every total-attempt and per-phase sample. SHA3-384: `94fbe136d7bba036b633c8f1ead712f166cb6f0c28482f09b74e2324979ea4d597c40fa59ce9ea71c6595de85535c352`.
- [`2026-08-12-github-ubuntu-phase-standard.md`](2026-08-12-github-ubuntu-phase-standard.md) — instrumented standard-profile run on shared GitHub runner `31616375003`. Phase measurements show that v0 is dominated by scratchpad initialization and finalization, so the candidate requires redesign before specialization testing.
- [`2026-08-12-github-ubuntu-phase-standard.json`](2026-08-12-github-ubuntu-phase-standard.json) — exact raw matrix from that run, including every total-attempt and per-phase timing sample. SHA3-384: `6a8bc34daa45a9ec2a0149a0406481c5543590ced202272aacbab9a12adafac4abd3b9c0e502d0b446c87f95e23a5d08`.
- [`2026-08-12-github-ubuntu-standard.md`](2026-08-12-github-ubuntu-standard.md) — first informational standard-profile run on a shared GitHub Ubuntu runner. No proof-of-work gate passed.
- [`2026-08-12-github-ubuntu-standard.json`](2026-08-12-github-ubuntu-standard.json) — complete raw matrix for that report, including every recorded timing sample.

The governing thresholds are frozen in [`../pow-evaluation-gates.md`](../pow-evaluation-gates.md). The v0 phase findings and predeclared v1 screens are documented in [`../pow-v1-workload-objectives.md`](../pow-v1-workload-objectives.md). The v1 result advances the candidate only to controlled-hardware screening; it does not justify consensus integration or specialization claims. Reports must state which gates lack sufficient evidence and must preserve unfavorable observations.
