# Soveroot CPU Research Baseline: GitHub Ubuntu shared runner 31616375003

Status: **INFORMATIONAL ONLY -- NO POW GATE PASSED**

Raw matrix SHA3-384: `6a8bc34daa45a9ec2a0149a0406481c5543590ced202272aacbab9a12adafac4abd3b9c0e502d0b446c87f95e23a5d08`
Source revision: `277f86b32d246e560a0abe25b2802a997567d8d1`
Profile: `standard`

## Host and method

- Platform: `Linux-6.17.0-1020-azure-x86_64-with-glibc2.39`
- Machine: `x86_64`
- CPU model: `AMD EPYC 9V74 80-Core Processor`
- Logical CPUs visible: `4`
- Runner image: `ubuntu24`
- Clock: C++ `std::chrono::steady_clock`
- Thermal state and package energy were not measured.

## Results

| Configuration | Dataset KiB | Scratch KiB | Instructions | Passes | Working set KiB | Prepare median ms | Attempt median ms | Seed spread |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 256 | 64 | 64 | 4 | 320.8 | 9.066 | 2.262 | 0.27% |
| dataset-64k | 64 | 64 | 64 | 4 | 128.8 | 2.276 | 2.261 | 2.01% |
| dataset-1024k | 1024 | 64 | 64 | 4 | 1088.8 | 36.224 | 2.265 | 7.88% |
| dataset-4096k | 4096 | 64 | 64 | 4 | 4160.8 | 140.181 | 2.260 | 14.31% |
| scratch-8k | 256 | 8 | 64 | 4 | 264.8 | 9.032 | 0.362 | 39.24% |
| scratch-128k | 256 | 128 | 64 | 4 | 384.8 | 9.057 | 4.418 | 0.52% |
| scratch-512k | 256 | 512 | 64 | 4 | 768.8 | 9.047 | 17.422 | 2.55% |
| instructions-16 | 256 | 64 | 16 | 4 | 320.2 | 9.083 | 2.203 | 0.86% |
| instructions-256 | 256 | 64 | 256 | 4 | 322.8 | 9.172 | 2.484 | 0.69% |
| passes-1 | 256 | 64 | 64 | 1 | 320.8 | 9.070 | 2.206 | 0.56% |
| passes-16 | 256 | 64 | 64 | 16 | 320.8 | 9.093 | 2.488 | 2.35% |

## Median phase shares

Phase medians are summarized independently across seeds, so percentages may not total exactly 100%.

| Configuration | Input setup | Scratchpad init | VM execution | Finalization |
|---|---:|---:|---:|---:|
| baseline | 0.3% | 42.2% | 3.3% | 54.1% |
| dataset-64k | 0.3% | 42.3% | 3.3% | 54.1% |
| dataset-1024k | 0.3% | 42.2% | 3.3% | 54.0% |
| dataset-4096k | 0.3% | 42.2% | 3.4% | 54.1% |
| scratch-8k | 1.7% | 33.6% | 20.1% | 43.9% |
| scratch-128k | 0.1% | 43.1% | 1.7% | 55.0% |
| scratch-512k | 0.0% | 43.8% | 0.4% | 55.7% |
| instructions-16 | 0.3% | 43.3% | 0.9% | 55.5% |
| instructions-256 | 0.3% | 38.4% | 11.9% | 49.2% |
| passes-1 | 0.3% | 43.3% | 0.9% | 55.4% |
| passes-16 | 0.3% | 38.4% | 11.9% | 49.2% |

## Screening observations

- Increasing the dataset 64x (64 KiB to 4 MiB) changed median attempt time by 1.00x.
- Increasing the scratchpad 64x (8 KiB to 512 KiB) changed median attempt time by 48.12x.
- Increasing the instruction count 16x changed median attempt time by 1.13x.
- Increasing passes 16x changed median attempt time by 1.13x.

These shared-runner results suggest that per-attempt scratchpad expansion and final hashing dominate the current prototype while dataset access and variable VM execution contribute too little. This is a screening inference, not a hardware gate result. The observational phase shares quantify which stages dominate; workload redesign should precede GPU, FPGA, or ASIC comparisons.

## Gate interpretation

The seed-variance gate requires at least 1,024 seeds per controlled device; this run used 8. The measurements are therefore a pipeline screening signal, not a pass or failure.

This run cannot evaluate energy efficiency, retail-price performance, memory recomputation, large-batch amortization, GPU advantage, FPGA or ASIC advantage, quantum advantage, or mining-template autonomy.

## Reproduction requirements

Preserve the raw JSON with this report. Repeat the same source revision and profile on declared low-cost, midrange, and high-end physical systems while recording compiler flags, operating system, power mode, package energy, temperature, and background load.
