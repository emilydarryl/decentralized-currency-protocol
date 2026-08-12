# Soveroot CPU Research Baseline: GitHub Ubuntu shared runner 31611191529

Status: **INFORMATIONAL ONLY -- NO POW GATE PASSED**

Raw matrix SHA3-384: `f9eb7df0cec2fcbca248cca0a65f141998f7e250a631fbe663c60534a9dfe998c439d02d1b6aae3f5908c01579a65148`
Source revision: `9e7e0b7e4a6b7cede4f39e105b5b1b375f316a0d`
Profile: `standard`

## Host and method

- Platform: `Linux-6.17.0-1020-azure-x86_64-with-glibc2.39`
- Machine: `x86_64`
- CPU model: `x86_64`
- Logical CPUs visible: `4`
- Runner image: `ubuntu24`
- Clock: C++ `std::chrono::steady_clock`
- Thermal state and package energy were not measured.

## Results

| Configuration | Dataset KiB | Scratch KiB | Instructions | Passes | Working set KiB | Prepare median ms | Attempt median ms | Seed spread |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 256 | 64 | 64 | 4 | 320.8 | 8.295 | 2.055 | 1.12% |
| dataset-64k | 64 | 64 | 64 | 4 | 128.8 | 2.080 | 2.056 | 3.32% |
| dataset-1024k | 1024 | 64 | 64 | 4 | 1088.8 | 32.669 | 2.051 | 3.15% |
| dataset-4096k | 4096 | 64 | 64 | 4 | 4160.8 | 127.495 | 2.048 | 2.98% |
| scratch-8k | 256 | 8 | 64 | 4 | 264.8 | 8.226 | 0.330 | 67.92% |
| scratch-128k | 256 | 128 | 64 | 4 | 384.8 | 8.272 | 4.018 | 0.74% |
| scratch-512k | 256 | 512 | 64 | 4 | 768.8 | 8.227 | 15.794 | 0.39% |
| instructions-16 | 256 | 64 | 16 | 4 | 320.2 | 8.269 | 1.998 | 0.55% |
| instructions-256 | 256 | 64 | 256 | 4 | 322.8 | 8.320 | 2.264 | 3.19% |
| passes-1 | 256 | 64 | 64 | 1 | 320.8 | 8.208 | 2.003 | 10.41% |
| passes-16 | 256 | 64 | 64 | 16 | 320.8 | 8.185 | 2.264 | 0.53% |

## Screening observations

- Increasing the dataset 64x (64 KiB to 4 MiB) changed median attempt time by 1.00x.
- Increasing the scratchpad 64x (8 KiB to 512 KiB) changed median attempt time by 47.90x.
- Increasing the instruction count 16x changed median attempt time by 1.13x.
- Increasing passes 16x changed median attempt time by 1.13x.

These shared-runner results suggest that per-attempt scratchpad expansion and final hashing dominate the current prototype while dataset access and variable VM execution contribute too little. This is a screening inference, not a hardware gate result. Phase-level instrumentation and workload redesign should precede GPU, FPGA, or ASIC comparisons.

## Gate interpretation

The seed-variance gate requires at least 1,024 seeds per controlled device; this run used 8. The measurements are therefore a pipeline screening signal, not a pass or failure.

This run cannot evaluate energy efficiency, retail-price performance, memory recomputation, large-batch amortization, GPU advantage, FPGA or ASIC advantage, quantum advantage, or mining-template autonomy.

## Reproduction requirements

Preserve the raw JSON with this report. Repeat the same source revision and profile on declared low-cost, midrange, and high-end physical systems while recording compiler flags, operating system, power mode, package energy, temperature, and background load.
