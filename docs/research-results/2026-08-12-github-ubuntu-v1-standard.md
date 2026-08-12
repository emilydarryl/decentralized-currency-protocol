# Soveroot PoW v1 CPU Screening: GitHub Ubuntu shared runner 31623410165

Status: **INFORMATIONAL V1 SCREEN -- NO POW GATE PASSED**

Raw matrix SHA3-384: `94fbe136d7bba036b633c8f1ead712f166cb6f0c28482f09b74e2324979ea4d597c40fa59ce9ea71c6595de85535c352`
Source revision: `aaa0d9632511bc5e0c35d0c3e2689710f47888b0`
Profile: `standard`
Screening policy: `soveroot-pow-v1-screening-objectives-v0` version `0.1`

## Host and method

- Platform: `Linux-6.17.0-1020-azure-x86_64-with-glibc2.39`
- Machine: `x86_64`
- CPU model: `AMD EPYC 7763 64-Core Processor`
- Logical CPUs visible: `4`
- Runner image: `ubuntu24`
- Clock: C++ `std::chrono::steady_clock`
- Thermal state, package energy, and memory traffic were not measured.

## Results

| Configuration | Dataset KiB | Scratch KiB | Passes | Working set KiB | Prepare median ms | Attempt median ms | Seed spread |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 2048 | 256 | 3 | 2304.6 | 65.145 | 4.918 | 2.92% |
| dataset-64k | 64 | 256 | 3 | 320.6 | 2.076 | 3.527 | 1.92% |
| dataset-1024k | 1024 | 256 | 3 | 1280.6 | 32.658 | 4.701 | 2.63% |
| dataset-4096k | 4096 | 256 | 3 | 4352.6 | 128.403 | 4.872 | 7.52% |
| scratch-8k | 2048 | 8 | 3 | 2056.6 | 64.930 | 0.198 | 64.91% |
| scratch-128k | 2048 | 128 | 3 | 2176.6 | 64.663 | 2.184 | 1.93% |
| scratch-512k | 2048 | 512 | 3 | 2560.6 | 64.573 | 11.297 | 2.36% |
| passes-1 | 2048 | 256 | 1 | 2304.6 | 64.371 | 1.654 | 2.88% |
| passes-16 | 2048 | 256 | 16 | 2304.6 | 64.524 | 26.184 | 2.14% |

## Median phase shares

Phase medians are summarized independently across seeds, so percentages may not total exactly 100%.

| Configuration | Input setup | Zero allocation | Mixing | Finalization |
|---|---:|---:|---:|---:|
| baseline | 0.1% | 0.1% | 99.5% | 0.3% |
| dataset-64k | 0.2% | 0.1% | 99.3% | 0.4% |
| dataset-1024k | 0.1% | 0.1% | 99.5% | 0.3% |
| dataset-4096k | 0.1% | 0.1% | 99.5% | 0.3% |
| scratch-8k | 3.0% | 0.1% | 90.0% | 6.8% |
| scratch-128k | 0.3% | 0.1% | 98.9% | 0.6% |
| scratch-512k | 0.1% | 0.1% | 99.7% | 0.1% |
| passes-1 | 0.4% | 0.2% | 98.6% | 0.8% |
| passes-16 | 0.0% | 0.0% | 99.9% | 0.1% |

## Predeclared v1 software screens

| Screen | Observation | Outcome |
|---|---:|---|
| Baseline mixing share | 99.5% | **ADVANCE** |
| Baseline zero-allocation share | 0.1% | **ADVANCE** |
| Baseline fixed-finalization share | 0.3% | **ADVANCE** |
| 16x pass-count response | 15.83x | **ADVANCE** |
| 64x scratchpad response | 57.05x | **ADVANCE** |
| 64x dataset response | 1.38x | **UNASSESSED ON SHARED RUNNER** |

Shared-runner outcome: **ADVANCE SOFTWARE SCREEN ONLY: all assessable shared-runner screens met their advance bounds; the controlled dataset-cache screen and all mandatory gates remain open.**

## Gate interpretation

The seed-variance gate requires at least 1,024 seeds per controlled device; this run used 8. The measurements are a workload-balance screen, not a pass or failure of that gate.

This run cannot evaluate energy efficiency, memory recomputation, large-batch amortization, optimized GPU advantage, FPGA or ASIC advantage, quantum advantage, or mining-template autonomy.

## Reproduction requirements

Preserve the raw JSON with this report. Repeat the same source revision and profile on declared low-cost, midrange, and high-end physical systems while recording compiler flags, operating system, power mode, package energy, temperature, memory traffic, and background load.
