# Soveroot PoW v1 Research Candidate Specification

Version: 0.1

Status: Deterministic non-consensus research specification

This document defines the byte-level v1 candidate used for differential implementation and workload screening. It does not select a production proof of work or modify block validation. Any semantic change requires a new version, new domain separators, and new vectors.

## Integer and byte rules

- U8 is one unsigned byte.
- U64LE is an unsigned 64-bit integer encoded least-significant byte first.
- All arithmetic is modulo 2^64.
- ROTL64(value, shift) rotates a 64-bit value left by shift AND 63 bits.
- SHA3-384 returns 48 bytes.
- SHAKE-256(input, length) returns exactly length bytes.
- Concatenation is written as two vertical bars.
- Every domain below includes its terminating zero byte.

Memory is an array of U64LE words and every allowed byte length is a power of two divisible by eight. READ(memory, selector) returns word selector AND (word_count - 1). WRITE uses the same mapping.

## Parameters and bounds

The parameter encoding is:

    U64LE(dataset_bytes) || U64LE(scratchpad_bytes) || U64LE(passes)

The research envelope is:

| Parameter | Minimum | Maximum |
|---|---:|---:|
| Dataset bytes | 64 KiB | 64 MiB |
| Scratchpad bytes | 8 KiB | 8 MiB |
| Passes | 1 | 16 |

Both memory sizes must be powers of two. The seed is exactly 48 bytes, the header is 1 through 4,096 bytes, and the nonce is a U64.

## Domain separators

| Purpose | ASCII bytes before the terminating zero |
|---|---|
| Schedule | Soveroot/PowResearch/Schedule/v1 |
| Dataset | Soveroot/PowResearch/Dataset/v1 |
| Initial registers | Soveroot/PowResearch/Registers/v1 |
| Memory commitment | Soveroot/PowResearch/Commitment/v1 |
| Result | Soveroot/PowResearch/Result/v1 |

These domains are distinct from all v0 domains.

## Epoch preparation

The schedule always contains 64 entries. Derive 638 bytes as:

    raw = SHAKE-256(schedule_domain || seed || parameter_encoding, 638)

Initialize opcode[i] to i modulo 8. For i from 63 down to 1, read the next U16LE beginning at raw offset 512, select j = value modulo (i + 1), and swap opcode[i] with opcode[j]. Entry i is opcode[i] followed by U64LE(raw[8*i : 8*i+8]). This guarantees exactly eight occurrences of every opcode while allowing the seed and parameter set to choose their order and immediates.

The encoded schedule is the concatenation of all U8 opcode and U64LE immediate entries. Its digest is SHA3-384(encoded_schedule).

The dataset is:

    SHAKE-256(dataset_domain || seed || parameter_encoding, dataset_bytes)

Its digest is SHA3-384(dataset). The schedule and dataset may be shared across nonce attempts, so neither is treated as proof of per-attempt work.

## Nonce evaluation

Compute header_digest = SHA3-384(header) and nonce_bytes = U64LE(nonce). Derive 72 initial-state bytes as:

    SHAKE-256(register_domain || seed || header_digest || nonce_bytes ||
              parameter_encoding, 72)

The first eight U64LE words are registers R0 through R7 and the ninth is accumulator A. Allocate a zero-filled scratchpad of scratchpad_bytes. This allocation is not a cryptographic expansion phase.

For each pass p from zero through passes - 1 and each scratchpad word w from zero through scratchpad_word_count - 1:

1. Set iteration n = p * scratchpad_word_count + w, lane l = n AND 7, and entry E = schedule[n AND 63].
2. Set x = R[l], y = R[(l+1) AND 7], and z = R[(l+3) AND 7].
3. s1_index = x XOR ROTL64(y, n) XOR A XOR E.immediate.
4. s1 = READ(scratchpad, s1_index).
5. dataset_index = s1 XOR z XOR ROTL64(A, l+p) XOR n.
6. d = READ(dataset, dataset_index).
7. s2_index = d XOR R[(l+5) AND 7] XOR ROTL64(s1+A, E.immediate).
8. s2 = READ(scratchpad, s2_index).
9. Compute mixed m with the opcode table below.
10. A = ROTL64(A XOR m XOR d, s1 XOR s2 XOR E.immediate) + s1 + E.immediate + n.
11. WRITE(scratchpad, w, m XOR A XOR s2).
12. WRITE(scratchpad, s2_index, s2 XOR ROTL64(m+A, d)).
13. R[l] = m + A + s1.
14. R[(l+2) AND 7] = R[(l+2) AND 7] XOR ROTL64(d+s1, s2).

The first iteration uses nonce-derived initial state. Every later iteration incorporates state produced by a prior iteration. Loop counts never depend on the seed, header, nonce, or memory contents.

## Opcode table

All results use the integer and rotation rules above.

| Opcode | mixed value |
|---:|---|
| 0 | x + y + d + immediate |
| 1 | x XOR ROTL64(y+d, immediate) XOR s1 |
| 2 | (x OR 1) * ((d XOR s2 XOR immediate) OR 1) |
| 3 | ROTL64(x XOR s1 XOR d, y XOR s2 XOR immediate) |
| 4 | (x+s1) XOR (d+s2+immediate) |
| 5 | ROTL64(x+d+immediate, s1) * (y OR 1) |
| 6 | (x XOR s2) + ROTL64(d XOR immediate, s1 XOR y) |
| 7 | ROTL64(((x OR 1) * (y OR 1)) + s1 + s2, d XOR immediate) |

## Fixed-size finalization

Set selector = A XOR R0 XOR R4. For sample index i from zero through 15:

1. selector = ROTL64(selector XOR R[i AND 7], i+1) + hexadecimal 9E3779B97F4A7C15 + i.
2. sample[i] = READ(scratchpad, selector).
3. selector = selector XOR sample[i].

Encode all eight registers, A, and the 16 samples as U64LE. The memory commitment is:

    SHA3-384(commitment_domain || parameter_encoding || registers ||
             accumulator || samples)

No full-scratchpad or full-dataset scan occurs during finalization. The final digest is:

    SHA3-384(result_domain || seed || header_digest || nonce_bytes ||
             parameter_encoding || schedule_digest || dataset_digest ||
             registers || accumulator || memory_commitment)

The reported result contains the final digest, registers, schedule digest, dataset digest, and memory commitment.

## Research limitations

The access counts and fixed finalization are structural properties, not security proofs. A specialist may compress, recompute, pipeline, or otherwise avoid the intended cost. v1 must pass independent vector agreement, controlled phase timing, time-memory-tradeoff testing, batch-amortization testing, optimized CPU and GPU comparisons, reviewed FPGA and ASIC estimates, and the quantum and mining-autonomy gates before it can advance.
