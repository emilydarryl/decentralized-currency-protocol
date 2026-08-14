# PoW v1 Physical-Memory Diagnostic — GitHub Ubuntu

Status: **SHARED-RUNNER DIAGNOSTIC; NO GATE ASSESSED**

This report preserves the first Linux execution of the physically accounted dependency-bundle attacker. It was produced by GitHub Actions run [`31821645159`](https://github.com/emilydarryl/decentralized-currency-protocol/actions/runs/31821645159) from source revision `1ec1090ea8e277ae2e7283d7fd14ed53ca140432` on `Linux-6.17.0-1022-azure-x86_64-with-glibc2.39`.

## Result

GCC classified `RecursiveRegenerator::ValueAt` as `dynamic,bounded` and reported a 352-byte frame. The frozen model conservatively reserves 2,048 bytes for each of twenty possible frames, or 40,960 bytes total. The compiler-specific check passed.

All eight standard-profile attack cases consumed exactly 5,000,000 charged operations, reached iterations 641 through 853, and refused without emitting a canonical proof. The C++ refusal boundaries matched the independently implemented Python vectors.

| Measurement | Ordinary evaluator | Physically accounted attacker |
| --- | ---: | ---: |
| Minimum peak whole-process RSS | 7,782,400 bytes | 7,794,688 bytes |
| Median peak whole-process RSS | 7,806,976 bytes | 7,897,088 bytes |
| Maximum peak whole-process RSS | 7,917,568 bytes | 7,962,624 bytes |

The median paired attacker-minus-ordinary difference was 28,672 bytes. Two pairs reported the attacker 20,480 bytes below the ordinary run, illustrating page-level and shared-runner noise.

## Interpretation

Whole-process RSS is much larger than the 131,072-byte attack budget because it includes the executable, runtime, 2 MiB epoch dataset, and other state also needed by an ordinary evaluator. It is therefore not a direct measurement of attack-specific memory and cannot prove compliance with the half-scratch gate.

The useful evidence is narrower: the measurement path executes successfully, there is no recovery-dependent transcript growth, the compiler reports bounded recursion well inside the conservative reserve, and the attack's whole-process footprint stays in the same range as ordinary evaluation across this small shared-runner sample. Controlled physical hosts, implementation-level allocator accounting, a second attack model, and canonical attack proofs remain absent.

## Preserved files

- [`2026-08-14-github-ubuntu-v1-physical-memory.json`](2026-08-14-github-ubuntu-v1-physical-memory.json) — eight paired peak-RSS and page-fault records. SHA3-384: `01475683603d96efae496a94ef291d2ac4d1d523a4089b5e0ba595c9d0585a0187138320bfb4ac599ef666389f02107b`.
- [`2026-08-14-github-ubuntu-v1-recursive-stack-usage.json`](2026-08-14-github-ubuntu-v1-recursive-stack-usage.json) — GCC frame classification and byte bound. SHA3-384: `589bba25ef33003d263abaf1785c4ee3d00c0eecb9ef1d83c4f3216a0f61406abf94ae0f17f86ad425c0fe8fab640b0a`.

The governing method is [`../pow-v1-physical-memory-accounting.md`](../pow-v1-physical-memory-accounting.md). Its time-memory gate remains **NOT ASSESSED**.
