# Soveroot Research Results

This directory preserves raw, versioned measurements and their human-readable reports. Results are evidence about a particular implementation, source revision, machine, compiler, and method. They are not consensus parameters or claims of production readiness.

## CPU baselines

- [`2026-08-12-github-ubuntu-v1-standard.md`](2026-08-12-github-ubuntu-v1-standard.md) — first standard-profile v1 screen on shared GitHub runner `31623410165`. Every assessable predeclared workload-balance screen met its advance bound; no mandatory PoW gate passed.
- [`2026-08-12-github-ubuntu-v1-standard.json`](2026-08-12-github-ubuntu-v1-standard.json) — exact raw v1 matrix with every total-attempt and per-phase sample. SHA3-384: `94fbe136d7bba036b633c8f1ead712f166cb6f0c28482f09b74e2324979ea4d597c40fa59ce9ea71c6595de85535c352`.
- [`2026-08-12-github-ubuntu-phase-standard.md`](2026-08-12-github-ubuntu-phase-standard.md) — instrumented standard-profile run on shared GitHub runner `31616375003`. Phase measurements show that v0 is dominated by scratchpad initialization and finalization, so the candidate requires redesign before specialization testing.
- [`2026-08-12-github-ubuntu-phase-standard.json`](2026-08-12-github-ubuntu-phase-standard.json) — exact raw matrix from that run, including every total-attempt and per-phase timing sample. SHA3-384: `6a8bc34daa45a9ec2a0149a0406481c5543590ced202272aacbab9a12adafac4abd3b9c0e502d0b446c87f95e23a5d08`.
- [`2026-08-12-github-ubuntu-standard.md`](2026-08-12-github-ubuntu-standard.md) — first informational standard-profile run on a shared GitHub Ubuntu runner. No proof-of-work gate passed.
- [`2026-08-12-github-ubuntu-standard.json`](2026-08-12-github-ubuntu-standard.json) — complete raw matrix for that report, including every recorded timing sample.

The governing thresholds are frozen in [`../pow-evaluation-gates.md`](../pow-evaluation-gates.md). The v0 phase findings and predeclared v1 screens are documented in [`../pow-v1-workload-objectives.md`](../pow-v1-workload-objectives.md). The v1 result advances the candidate only to controlled-hardware screening; it does not justify consensus integration or specialization claims. Reports must state which gates lack sufficient evidence and must preserve unfavorable observations.
