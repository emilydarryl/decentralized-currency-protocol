# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Repeated exact recursive value regeneration inside the v1 half-memory arena."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct

from .bounded_reconstruction import _MaterializedMiss, _boundary_commitment, _initial_machine_state, _mix_step
from .powvm import (
    DOMAIN_COMMITMENT,
    DOMAIN_RESULT,
    FINAL_SAMPLE_WORDS,
    MASK64,
    EpochContext,
    ExecutionResult,
    _rol64,
    _u64,
    _validate_header,
    _validate_seed,
)
from .recursive_regeneration import (
    DEFAULT_WORK_LIMIT,
    RecursiveBoundary,
    _RecursiveArena,
    _RecursiveRegenerator,
    _RegenerationExhausted,
)


DOMAIN_REPEATED_RECURSIVE_REGENERATION = (
    b"Soveroot/PowResearch/RepeatedRecursiveRegeneration/v1\x00"
)
DEFAULT_REPEATED_WORK_LIMIT = DEFAULT_WORK_LIMIT


@dataclass(frozen=True)
class RepeatedRecursiveExhaustion:
    reason: str
    consumer: int
    slot: int
    word: int
    stop_iteration: int
    attempted_depth: int
    regeneration_iterations: int
    state_commitment: str


@dataclass(frozen=True)
class RepeatedRecursiveRegenerationResult:
    status: str
    layout: object
    primary_numerator: int
    primary_denominator: int
    work_limit: int
    completed_iterations: int
    canonical_reads: int
    cache_hits: int
    initial_zero_reads: int
    materialized_misses: int
    writes: int
    evictions: int
    reconstruction_attempts: int
    reconstructed_misses: int
    regeneration_calls: int
    regeneration_cache_hits: int
    regeneration_completed_values: int
    regeneration_iterations: int
    maximum_depth: int
    memo_peak_entries: int
    memo_evictions: int
    memo_probes: int
    memo_shifted_bytes: int
    first_reconstruction: RecursiveBoundary | None
    last_reconstruction: RecursiveBoundary | None
    exhaustion: RepeatedRecursiveExhaustion | None
    transcript_commitment: str
    execution_result: ExecutionResult | None

    def to_dict(self) -> dict[str, object]:
        document = asdict(self)
        document["execution_result"] = (
            None if self.execution_result is None else self.execution_result.to_dict()
        )
        return document


def reconstruct_repeatedly_recursively(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
    work_limit: int = DEFAULT_REPEATED_WORK_LIMIT,
    primary_numerator: int = 1,
    primary_denominator: int = 64,
) -> RepeatedRecursiveRegenerationResult:
    """Recursively recover every encountered miss until completion or exhaustion."""

    _validate_seed(context.seed)
    context.params.validate()
    _validate_header(header)
    if not 0 <= nonce <= MASK64:
        raise ValueError("nonce must be an unsigned 64-bit integer")
    if work_limit <= 0:
        raise ValueError("work_limit must be positive")
    budget = context.params.scratchpad_bytes // 2 if budget_bytes is None else budget_bytes
    if budget <= 0 or budget > context.params.scratchpad_bytes:
        raise ValueError("budget_bytes must be in (0, scratchpad_bytes]")
    header_digest = hashlib.sha3_384(header).digest()
    nonce_bytes = struct.pack("<Q", nonce)
    registers, accumulator = _initial_machine_state(context, header_digest, nonce_bytes)
    word_count = context.params.scratchpad_bytes // 8
    total_iterations = word_count * context.params.passes
    arena = _RecursiveArena(
        context.params.scratchpad_bytes,
        budget,
        primary_numerator,
        primary_denominator,
    )
    regenerator = _RecursiveRegenerator(
        arena, context, header_digest, nonce_bytes, work_limit
    )
    completed = attempts = successful = 0
    first: RecursiveBoundary | None = None
    last: RecursiveBoundary | None = None
    exhaustion: RepeatedRecursiveExhaustion | None = None
    transcript = hashlib.sha3_384(DOMAIN_REPEATED_RECURSIVE_REGENERATION)

    def recover(miss: _MaterializedMiss) -> bool:
        nonlocal attempts, successful, first, last, exhaustion
        attempts += 1
        state_commitment = _boundary_commitment(
            DOMAIN_REPEATED_RECURSIVE_REGENERATION,
            context,
            header_digest,
            nonce_bytes,
            registers,
            accumulator,
            miss.consumer,
            miss.slot,
            miss.word,
        )
        try:
            value = regenerator.value_at(miss.word, miss.consumer)
        except _RegenerationExhausted as error:
            exhaustion = RepeatedRecursiveExhaustion(
                error.reason,
                miss.consumer,
                miss.slot,
                miss.word,
                error.stop,
                error.depth,
                regenerator.iterations,
                state_commitment,
            )
            return False
        commitment = _boundary_commitment(
            DOMAIN_REPEATED_RECURSIVE_REGENERATION,
            context,
            header_digest,
            nonce_bytes,
            registers,
            accumulator,
            miss.consumer,
            miss.slot,
            miss.word,
            value,
        )
        boundary = RecursiveBoundary(
            miss.consumer,
            miss.slot,
            miss.word,
            value,
            regenerator.calls,
            regenerator.cache_hits,
            regenerator.completed_values,
            regenerator.iterations,
            regenerator.maximum_depth,
            regenerator.memo_peak_entries,
            regenerator.memo_evictions,
            regenerator.memo_probes,
            regenerator.memo_shifted_bytes,
            commitment,
        )
        transcript.update(bytes.fromhex(commitment))
        first = boundary if first is None else first
        last = boundary
        arena.retain(miss.word, value)
        successful += 1
        return True

    class _PrimaryView:
        def read(self, selector: int, consumer: int, slot: int) -> int:
            return arena.read(selector, consumer, slot)

        def write(self, selector: int, value: int) -> None:
            arena.write(selector, value)

    primary = _PrimaryView()
    execution_result: ExecutionResult | None = None
    stopped = False
    for iteration in range(total_iterations):
        while True:
            try:
                accumulator = _mix_step(context, primary, registers, accumulator, iteration)
                break
            except _MaterializedMiss as miss:
                if not recover(miss):
                    stopped = True
                    break
        if stopped:
            break
        completed += 1

    samples: list[int] = []
    if not stopped:
        selector = accumulator ^ registers[0] ^ registers[4]
        for sample_index in range(FINAL_SAMPLE_WORDS):
            selector = _u64(
                _rol64(selector ^ registers[sample_index & 7], sample_index + 1)
                + 0x9E3779B97F4A7C15
                + sample_index
            )
            while True:
                try:
                    sampled = arena.read(selector, total_iterations + sample_index, 0)
                    break
                except _MaterializedMiss as miss:
                    if not recover(miss):
                        stopped = True
                        break
            if stopped:
                break
            samples.append(sampled)
            selector = _u64(selector ^ sampled)

    status = "refused_recursive_regeneration_exhausted"
    if not stopped:
        params_bytes = context.params.encode()
        encoded_registers = struct.pack("<8Q", *registers)
        encoded_accumulator = struct.pack("<Q", accumulator)
        encoded_samples = struct.pack(f"<{FINAL_SAMPLE_WORDS}Q", *samples)
        memory_commitment = hashlib.sha3_384(
            DOMAIN_COMMITMENT
            + params_bytes
            + encoded_registers
            + encoded_accumulator
            + encoded_samples
        ).digest()
        digest = hashlib.sha3_384(
            DOMAIN_RESULT
            + context.seed
            + header_digest
            + nonce_bytes
            + params_bytes
            + context.schedule_digest
            + context.dataset_digest
            + encoded_registers
            + encoded_accumulator
            + memory_commitment
        ).digest()
        execution_result = ExecutionResult(
            digest=digest,
            registers=tuple(registers),
            schedule_digest=context.schedule_digest,
            dataset_digest=context.dataset_digest,
            memory_commitment=memory_commitment,
        )
        status = "exact_complete"

    return RepeatedRecursiveRegenerationResult(
        status,
        arena.layout,
        primary_numerator,
        primary_denominator,
        work_limit,
        completed,
        arena.canonical_reads,
        arena.cache_hits,
        arena.initial_zero_reads,
        arena.materialized_misses,
        arena.writes,
        arena.evictions,
        attempts,
        successful,
        regenerator.calls,
        regenerator.cache_hits,
        regenerator.completed_values,
        regenerator.iterations,
        regenerator.maximum_depth,
        regenerator.memo_peak_entries,
        regenerator.memo_evictions,
        regenerator.memo_probes,
        regenerator.memo_shifted_bytes,
        first,
        last,
        exhaustion,
        transcript.hexdigest(),
        execution_result,
    )
