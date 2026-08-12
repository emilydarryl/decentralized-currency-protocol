# Soveroot PoW v1 Half-Memory Attack Method

Status: **NON-CONSENSUS, INFORMATIONAL ATTACK HARNESS**

This milestone asks a narrow adversarial question: can an implementation reproduce valid PoW v1 outputs while retaining only half of the declared scratchpad in its explicit in-process byte array? It does not modify the v1 candidate, node validation, mining, or labnet.

The machine-readable method is [`contrib/pow_research_v1/half_memory_attack_v0.json`](../contrib/pow_research_v1/half_memory_attack_v0.json). It was frozen before collecting standard-profile results.

## Attack model

The `static-even-words-half-spill` backend preserves exact v1 semantics:

- even logical scratchpad words are retained in an in-process byte array;
- odd logical words are stored in a temporary random-access file;
- the retained byte array is exactly half the declared scratchpad size;
- the backing file is recreated for every nonce attempt and deleted afterward;
- every result is compared with the normal backend using a SHA3-384 commitment to the ordered result digests plus the existing 64-bit digest xor;
- canonical vectors must match through both backends before an attack matrix runs.

Benchmark order alternates by seed index so the normal backend does not always receive the same first- or second-run position. The standard experiment uses the existing 2 MiB dataset, 256 KiB scratchpad, three-pass profile with eight deterministic seeds and three attempts per seed.

## What the measurement means

The harness produces a valid exact-output storage tradeoff baseline. If it retains a surprisingly large fraction of normal throughput, v1 deserves immediate redesign because an extremely simple attacker is already effective.

A large slowdown is only motivation for a stronger attack. It does not establish memory hardness. This implementation makes one seek for each access to an omitted word and is intentionally easy to audit, not optimized.

## Why it cannot decide the gate

The mandatory time-memory-tradeoff gate requires a strongest-known implementation using half the declared memory. This experiment is ineligible to pass or reject that gate because:

- the operating system can retain backing-file pages in its page cache;
- process resident memory and system cache memory are not bounded or measured;
- omitted state is stored externally instead of recomputed;
- per-word file access is not an optimized attack strategy;
- shared GitHub runners do not provide controlled storage, memory bandwidth, power, or thermal conditions.

The report may show where the observed throughput falls relative to the frozen 40% pass ceiling and 65% rejection boundary, but that is numerical context only. It must always state that the gate remains open.

## Next adversarial steps

1. Add address-trace and reuse-distance evidence to identify useful checkpoint and cache strategies.
2. Implement exact bounded-memory recomputation without external storage.
3. Have the attack and memory accounting reviewed independently.
4. Measure resident memory, memory traffic, power, and temperature on controlled physical hosts.
5. Compare the strongest CPU attack with optimized GPU, FPGA, and ASIC models before making any decentralization claim.
