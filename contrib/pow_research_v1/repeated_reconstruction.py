# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Repeated sparse reconstruction inside the non-consensus v1 half-memory arena."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct

from .bounded_reconstruction import (
    DOMAIN_RECONSTRUCTION,
    _MaterializedMiss,
    _OneArena,
    _ReplayExhausted,
    _SparseReplay,
    _boundary_commitment,
    _initial_machine_state,
    _mix_step,
)
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


DOMAIN_REPEATED_TRANSCRIPT = b"Soveroot/PowResearch/RepeatedReconstruction/v1\x00"


@dataclass(frozen=True)
class ReconstructionBoundary:
    consumer: int
    slot: int
    word: int
    value: int
    replayed_iterations: int
    replay_peak_entries: int
    replay_hash_probes: int
    commitment: str


@dataclass(frozen=True)
class ReplayExhaustionBoundary:
    consumer: int
    slot: int
    word: int
    replay_completed_iterations: int
    replay_peak_entries: int
    replay_hash_probes: int
    state_commitment: str


@dataclass(frozen=True)
class RepeatedReconstructionResult:
    status: str
    layout: object
    completed_iterations: int
    canonical_reads: int
    cache_hits: int
    initial_zero_reads: int
    materialized_misses: int
    writes: int
    evictions: int
    reconstruction_attempts: int
    reconstructed_misses: int
    successful_replayed_iterations: int
    attempted_replay_iterations: int
    cumulative_replay_hash_probes: int
    max_replay_peak_entries: int
    max_reconstruction_depth: int
    all_replay_states_matched: bool
    transcript_commitment: str
    first_reconstruction: ReconstructionBoundary | None
    last_reconstruction: ReconstructionBoundary | None
    exhaustion: ReplayExhaustionBoundary | None
    execution_result: ExecutionResult | None

    def to_dict(self) -> dict[str, object]:
        document = asdict(self)
        document["execution_result"] = (
            None if self.execution_result is None else self.execution_result.to_dict()
        )
        return document


def reconstruct_repeatedly(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
) -> RepeatedReconstructionResult:
    """Reconstruct every encountered miss until exact completion or arena exhaustion."""

    _validate_seed(context.seed)
    context.params.validate()
    _validate_header(header)
    if not 0 <= nonce <= MASK64:
        raise ValueError("nonce must be an unsigned 64-bit integer")
    budget = context.params.scratchpad_bytes // 2 if budget_bytes is None else budget_bytes
    if budget <= 0 or budget > context.params.scratchpad_bytes:
        raise ValueError("budget_bytes must be in (0, scratchpad_bytes]")
    header_digest = hashlib.sha3_384(header).digest()
    nonce_bytes = struct.pack("<Q", nonce)
    registers, accumulator = _initial_machine_state(context, header_digest, nonce_bytes)
    word_count = context.params.scratchpad_bytes // 8
    total_iterations = word_count * context.params.passes
    arena = _OneArena(context.params.scratchpad_bytes, budget)
    completed = 0
    attempts = 0
    successful = 0
    successful_replayed = 0
    attempted_replayed = 0
    cumulative_probes = 0
    max_peak = 0
    all_states_matched = True
    first: ReconstructionBoundary | None = None
    last: ReconstructionBoundary | None = None
    exhaustion: ReplayExhaustionBoundary | None = None
    transcript = hashlib.sha3_384(DOMAIN_REPEATED_TRANSCRIPT)

    def state_commitment(miss: _MaterializedMiss) -> str:
        return _boundary_commitment(
            DOMAIN_RECONSTRUCTION,
            context,
            header_digest,
            nonce_bytes,
            registers,
            accumulator,
            miss.consumer,
            miss.slot,
            miss.word,
        )

    def perform_reconstruction(miss: _MaterializedMiss) -> bool:
        nonlocal attempts, successful, successful_replayed, attempted_replayed
        nonlocal cumulative_probes, max_peak, all_states_matched, first, last, exhaustion
        attempts += 1
        replay = _SparseReplay(arena)
        replay_registers, replay_accumulator = _initial_machine_state(
            context, header_digest, nonce_bytes
        )
        replay_completed = 0
        replay_limit = min(miss.consumer, total_iterations)
        try:
            for replay_iteration in range(replay_limit):
                replay_accumulator = _mix_step(
                    context,
                    replay,
                    replay_registers,
                    replay_accumulator,
                    replay_iteration,
                )
                replay_completed += 1
        except _ReplayExhausted:
            attempted_replayed += replay_completed
            cumulative_probes += replay.hash_probes
            max_peak = max(max_peak, replay.peak_entries)
            exhaustion = ReplayExhaustionBoundary(
                consumer=miss.consumer,
                slot=miss.slot,
                word=miss.word,
                replay_completed_iterations=replay_completed,
                replay_peak_entries=replay.peak_entries,
                replay_hash_probes=replay.hash_probes,
                state_commitment=state_commitment(miss),
            )
            return False
        attempted_replayed += replay_completed
        successful_replayed += replay_completed
        max_peak = max(max_peak, replay.peak_entries)
        state_matched = (
            replay_registers == registers and replay_accumulator == accumulator
        )
        all_states_matched = all_states_matched and state_matched
        if not state_matched:
            raise RuntimeError("replayed machine state does not match the live prefix")
        value = replay.read_exact_word(miss.word)
        cumulative_probes += replay.hash_probes
        commitment = _boundary_commitment(
            DOMAIN_RECONSTRUCTION,
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
        boundary = ReconstructionBoundary(
            consumer=miss.consumer,
            slot=miss.slot,
            word=miss.word,
            value=value,
            replayed_iterations=replay_completed,
            replay_peak_entries=replay.peak_entries,
            replay_hash_probes=replay.hash_probes,
            commitment=commitment,
        )
        transcript.update(bytes.fromhex(commitment))
        first = boundary if first is None else first
        last = boundary
        successful += 1
        arena.retain_reconstructed(miss.word, value)
        return True

    class _PrimaryView:
        def read(self, selector: int, consumer: int, slot: int) -> int:
            return arena.read(selector, consumer, slot)

        def write(self, selector: int, value: int) -> None:
            arena.write(selector, value)

    primary = _PrimaryView()
    execution_result: ExecutionResult | None = None
    status = "refused_replay_workspace_exhausted"
    stopped = False
    for iteration in range(total_iterations):
        while True:
            try:
                accumulator = _mix_step(context, primary, registers, accumulator, iteration)
                break
            except _MaterializedMiss as miss:
                if not perform_reconstruction(miss):
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
                    if not perform_reconstruction(miss):
                        stopped = True
                        break
            if stopped:
                break
            samples.append(sampled)
            selector = _u64(selector ^ sampled)

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

    return RepeatedReconstructionResult(
        status=status,
        layout=arena.layout,
        completed_iterations=completed,
        canonical_reads=arena.canonical_reads,
        cache_hits=arena.cache_hits,
        initial_zero_reads=arena.initial_zero_reads,
        materialized_misses=arena.materialized_misses,
        writes=arena.writes,
        evictions=arena.evictions,
        reconstruction_attempts=attempts,
        reconstructed_misses=successful,
        successful_replayed_iterations=successful_replayed,
        attempted_replay_iterations=attempted_replayed,
        cumulative_replay_hash_probes=cumulative_probes,
        max_replay_peak_entries=max_peak,
        max_reconstruction_depth=1 if attempts else 0,
        all_replay_states_matched=all_states_matched,
        transcript_commitment=transcript.hexdigest(),
        first_reconstruction=first,
        last_reconstruction=last,
        exhaustion=exhaustion,
        execution_result=execution_result,
    )
