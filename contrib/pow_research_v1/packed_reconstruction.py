# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Repeated reconstruction with a bitmap-ranked packed replay checkpoint."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct

from .bounded_probe import CACHE_ENTRY_BYTES, FIXED_STATE_RESERVE_BYTES
from .bounded_reconstruction import (
    EMPTY_TAG,
    _MaterializedMiss,
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


DOMAIN_PACKED_RECONSTRUCTION = b"Soveroot/PowResearch/PackedReconstruction/v1\x00"
DOMAIN_PACKED_TRANSCRIPT = b"Soveroot/PowResearch/PackedTranscript/v1\x00"
RANK_CHUNK_WORDS = 256
PRIMARY_NUMERATOR = 1
PRIMARY_DENOMINATOR = 4


@dataclass(frozen=True)
class PackedLayout:
    budget_bytes: int
    fixed_state_reserve_bytes: int
    arena_bytes: int
    canonical_write_bitmap_bytes: int
    primary_cache_capacity: int
    primary_cache_bytes: int
    replay_bitmap_bytes: int
    rank_directory_bytes: int
    replay_value_capacity: int
    replay_value_bytes: int
    unused_arena_bytes: int
    admitted_bytes: int


@dataclass(frozen=True)
class PackedBoundary:
    consumer: int
    slot: int
    word: int
    value: int
    replayed_iterations: int
    replay_peak_entries: int
    replay_rank_probes: int
    replay_shifted_bytes: int
    commitment: str


@dataclass(frozen=True)
class PackedExhaustion:
    consumer: int
    slot: int
    word: int
    replay_completed_iterations: int
    replay_peak_entries: int
    replay_rank_probes: int
    replay_shifted_bytes: int
    state_commitment: str


@dataclass(frozen=True)
class PackedReconstructionResult:
    status: str
    layout: PackedLayout
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
    cumulative_rank_probes: int
    cumulative_shifted_bytes: int
    max_replay_peak_entries: int
    max_reconstruction_depth: int
    all_replay_states_matched: bool
    transcript_commitment: str
    first_reconstruction: PackedBoundary | None
    last_reconstruction: PackedBoundary | None
    exhaustion: PackedExhaustion | None
    execution_result: ExecutionResult | None

    def to_dict(self) -> dict[str, object]:
        document = asdict(self)
        document["execution_result"] = (
            None if self.execution_result is None else self.execution_result.to_dict()
        )
        return document


class _PackedExhausted(Exception):
    pass


class _PackedArena:
    def __init__(self, scratchpad_bytes: int, budget_bytes: int) -> None:
        self.word_count = scratchpad_bytes // 8
        bitmap_bytes = (self.word_count + 7) // 8
        arena_bytes = budget_bytes - FIXED_STATE_RESERVE_BYTES
        rank_chunks = (self.word_count + RANK_CHUNK_WORDS - 1) // RANK_CHUNK_WORDS
        rank_bytes = (rank_chunks + 1) * 2
        available = arena_bytes - bitmap_bytes * 2 - rank_bytes
        if available <= CACHE_ENTRY_BYTES + 8:
            raise ValueError("budget cannot hold packed replay and primary cache")
        primary_bytes = (available * PRIMARY_NUMERATOR // PRIMARY_DENOMINATOR)
        primary_bytes -= primary_bytes % CACHE_ENTRY_BYTES
        primary_capacity = primary_bytes // CACHE_ENTRY_BYTES
        replay_bytes = available - primary_bytes
        replay_capacity = replay_bytes // 8
        replay_value_bytes = replay_capacity * 8
        unused = replay_bytes - replay_value_bytes
        if primary_capacity == 0 or replay_capacity == 0:
            raise ValueError("budget cannot split packed replay and primary cache")
        self.layout = PackedLayout(
            budget_bytes=budget_bytes,
            fixed_state_reserve_bytes=FIXED_STATE_RESERVE_BYTES,
            arena_bytes=arena_bytes,
            canonical_write_bitmap_bytes=bitmap_bytes,
            primary_cache_capacity=primary_capacity,
            primary_cache_bytes=primary_bytes,
            replay_bitmap_bytes=bitmap_bytes,
            rank_directory_bytes=rank_bytes,
            replay_value_capacity=replay_capacity,
            replay_value_bytes=replay_value_bytes,
            unused_arena_bytes=unused,
            admitted_bytes=budget_bytes,
        )
        self.arena = bytearray(arena_bytes)
        self.primary_offset = bitmap_bytes
        self.replay_bitmap_offset = self.primary_offset + primary_bytes
        self.rank_offset = self.replay_bitmap_offset + bitmap_bytes
        self.values_offset = self.rank_offset + rank_bytes
        self.rank_chunks = rank_chunks
        for slot in range(primary_capacity):
            struct.pack_into("<Q", self.arena, self._primary_entry(slot), EMPTY_TAG)
        self.canonical_reads = 0
        self.cache_hits = 0
        self.initial_zero_reads = 0
        self.materialized_misses = 0
        self.writes = 0
        self.evictions = 0

    def _primary_entry(self, slot: int) -> int:
        return self.primary_offset + slot * CACHE_ENTRY_BYTES

    def _written(self, word: int) -> bool:
        return bool(self.arena[word // 8] & (1 << (word & 7)))

    def _mark_written(self, word: int) -> None:
        self.arena[word // 8] |= 1 << (word & 7)

    def read(self, selector: int, consumer: int, slot: int) -> int:
        word = selector & (self.word_count - 1)
        self.canonical_reads += 1
        offset = self._primary_entry(word % self.layout.primary_cache_capacity)
        if struct.unpack_from("<Q", self.arena, offset)[0] == word:
            self.cache_hits += 1
            return struct.unpack_from("<Q", self.arena, offset + 8)[0]
        if not self._written(word):
            self.initial_zero_reads += 1
            return 0
        self.materialized_misses += 1
        raise _MaterializedMiss(consumer, slot, word)

    def write(self, selector: int, value: int) -> None:
        word = selector & (self.word_count - 1)
        offset = self._primary_entry(word % self.layout.primary_cache_capacity)
        previous = struct.unpack_from("<Q", self.arena, offset)[0]
        if previous != EMPTY_TAG and previous != word:
            self.evictions += 1
        struct.pack_into("<QQ", self.arena, offset, word, value & MASK64)
        self._mark_written(word)
        self.writes += 1

    def retain(self, word: int, value: int) -> None:
        offset = self._primary_entry(word % self.layout.primary_cache_capacity)
        previous = struct.unpack_from("<Q", self.arena, offset)[0]
        if previous != EMPTY_TAG and previous != word:
            self.evictions += 1
        struct.pack_into("<QQ", self.arena, offset, word, value & MASK64)


class _PackedReplay:
    def __init__(self, owner: _PackedArena) -> None:
        self.owner = owner
        start = owner.replay_bitmap_offset
        end = owner.values_offset
        owner.arena[start:end] = b"\x00" * (end - start)
        self.distinct = 0
        self.peak_entries = 0
        self.rank_probes = 0
        self.shifted_bytes = 0

    def _present(self, word: int) -> bool:
        offset = self.owner.replay_bitmap_offset + word // 8
        return bool(self.owner.arena[offset] & (1 << (word & 7)))

    def _set_present(self, word: int) -> None:
        offset = self.owner.replay_bitmap_offset + word // 8
        self.owner.arena[offset] |= 1 << (word & 7)

    def _fenwick_prefix(self, chunk: int) -> int:
        total = 0
        index = chunk
        while index > 0:
            total += struct.unpack_from("<H", self.owner.arena, self.owner.rank_offset + index * 2)[0]
            self.rank_probes += 1
            index -= index & -index
        return total

    def _fenwick_add(self, chunk: int) -> None:
        index = chunk + 1
        while index <= self.owner.rank_chunks:
            offset = self.owner.rank_offset + index * 2
            value = struct.unpack_from("<H", self.owner.arena, offset)[0]
            struct.pack_into("<H", self.owner.arena, offset, value + 1)
            self.rank_probes += 1
            index += index & -index

    def _rank(self, word: int) -> int:
        chunk = word // RANK_CHUNK_WORDS
        total = self._fenwick_prefix(chunk)
        first_byte = (chunk * RANK_CHUNK_WORDS) // 8
        final_byte = word // 8
        for byte_index in range(first_byte, final_byte):
            total += self.owner.arena[self.owner.replay_bitmap_offset + byte_index].bit_count()
            self.rank_probes += 1
        partial = self.owner.arena[self.owner.replay_bitmap_offset + final_byte]
        total += (partial & ((1 << (word & 7)) - 1)).bit_count()
        self.rank_probes += 1
        return total

    def read(self, selector: int, _consumer: int, _slot: int) -> int:
        word = selector & (self.owner.word_count - 1)
        if not self._present(word):
            return 0
        rank = self._rank(word)
        return struct.unpack_from("<Q", self.owner.arena, self.owner.values_offset + rank * 8)[0]

    def read_exact_word(self, word: int) -> int:
        if not self._present(word):
            raise RuntimeError("materialized word is absent from the packed replay state")
        rank = self._rank(word)
        return struct.unpack_from("<Q", self.owner.arena, self.owner.values_offset + rank * 8)[0]

    def write(self, selector: int, value: int) -> None:
        word = selector & (self.owner.word_count - 1)
        present = self._present(word)
        rank = self._rank(word)
        if present:
            struct.pack_into("<Q", self.owner.arena, self.owner.values_offset + rank * 8, value & MASK64)
            return
        if self.distinct == self.owner.layout.replay_value_capacity:
            raise _PackedExhausted("packed replay value area is full")
        move_bytes = (self.distinct - rank) * 8
        if move_bytes:
            start = self.owner.values_offset + rank * 8
            self.owner.arena[start + 8:start + 8 + move_bytes] = self.owner.arena[start:start + move_bytes]
            self.shifted_bytes += move_bytes
        struct.pack_into("<Q", self.owner.arena, self.owner.values_offset + rank * 8, value & MASK64)
        self._set_present(word)
        self._fenwick_add(word // RANK_CHUNK_WORDS)
        self.distinct += 1
        self.peak_entries = max(self.peak_entries, self.distinct)


def reconstruct_with_packed_checkpoints(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
) -> PackedReconstructionResult:
    """Repeat exact reconstruction until the packed replay checkpoint fills."""

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
    arena = _PackedArena(context.params.scratchpad_bytes, budget)
    completed = attempts = successful = 0
    successful_replayed = attempted_replayed = 0
    cumulative_rank_probes = cumulative_shifted_bytes = 0
    max_peak = 0
    all_states_matched = True
    first: PackedBoundary | None = None
    last: PackedBoundary | None = None
    exhaustion: PackedExhaustion | None = None
    transcript = hashlib.sha3_384(DOMAIN_PACKED_TRANSCRIPT)

    def perform(miss: _MaterializedMiss) -> bool:
        nonlocal attempts, successful, successful_replayed, attempted_replayed
        nonlocal cumulative_rank_probes, cumulative_shifted_bytes, max_peak
        nonlocal all_states_matched, first, last, exhaustion
        attempts += 1
        replay = _PackedReplay(arena)
        replay_registers, replay_accumulator = _initial_machine_state(
            context, header_digest, nonce_bytes
        )
        replay_completed = 0
        try:
            for replay_iteration in range(min(miss.consumer, total_iterations)):
                replay_accumulator = _mix_step(
                    context, replay, replay_registers, replay_accumulator, replay_iteration
                )
                replay_completed += 1
        except _PackedExhausted:
            attempted_replayed += replay_completed
            cumulative_rank_probes += replay.rank_probes
            cumulative_shifted_bytes += replay.shifted_bytes
            max_peak = max(max_peak, replay.peak_entries)
            exhaustion = PackedExhaustion(
                consumer=miss.consumer,
                slot=miss.slot,
                word=miss.word,
                replay_completed_iterations=replay_completed,
                replay_peak_entries=replay.peak_entries,
                replay_rank_probes=replay.rank_probes,
                replay_shifted_bytes=replay.shifted_bytes,
                state_commitment=_boundary_commitment(
                    DOMAIN_PACKED_RECONSTRUCTION, context, header_digest, nonce_bytes,
                    registers, accumulator, miss.consumer, miss.slot, miss.word
                ),
            )
            return False
        attempted_replayed += replay_completed
        successful_replayed += replay_completed
        state_matched = replay_registers == registers and replay_accumulator == accumulator
        all_states_matched = all_states_matched and state_matched
        if not state_matched:
            raise RuntimeError("packed replay machine state does not match the live prefix")
        value = replay.read_exact_word(miss.word)
        cumulative_rank_probes += replay.rank_probes
        cumulative_shifted_bytes += replay.shifted_bytes
        max_peak = max(max_peak, replay.peak_entries)
        commitment = _boundary_commitment(
            DOMAIN_PACKED_RECONSTRUCTION, context, header_digest, nonce_bytes,
            registers, accumulator, miss.consumer, miss.slot, miss.word, value
        )
        boundary = PackedBoundary(
            consumer=miss.consumer,
            slot=miss.slot,
            word=miss.word,
            value=value,
            replayed_iterations=replay_completed,
            replay_peak_entries=replay.peak_entries,
            replay_rank_probes=replay.rank_probes,
            replay_shifted_bytes=replay.shifted_bytes,
            commitment=commitment,
        )
        transcript.update(bytes.fromhex(commitment))
        first = boundary if first is None else first
        last = boundary
        successful += 1
        arena.retain(miss.word, value)
        return True

    class _Primary:
        def read(self, selector: int, consumer: int, slot: int) -> int:
            return arena.read(selector, consumer, slot)

        def write(self, selector: int, value: int) -> None:
            arena.write(selector, value)

    primary = _Primary()
    stopped = False
    for iteration in range(total_iterations):
        while True:
            try:
                accumulator = _mix_step(context, primary, registers, accumulator, iteration)
                break
            except _MaterializedMiss as miss:
                if not perform(miss):
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
                + 0x9E3779B97F4A7C15 + sample_index
            )
            while True:
                try:
                    sampled = arena.read(selector, total_iterations + sample_index, 0)
                    break
                except _MaterializedMiss as miss:
                    if not perform(miss):
                        stopped = True
                        break
            if stopped:
                break
            samples.append(sampled)
            selector = _u64(selector ^ sampled)

    execution_result: ExecutionResult | None = None
    status = "refused_packed_checkpoint_exhausted"
    if not stopped:
        params_bytes = context.params.encode()
        encoded_registers = struct.pack("<8Q", *registers)
        encoded_accumulator = struct.pack("<Q", accumulator)
        encoded_samples = struct.pack(f"<{FINAL_SAMPLE_WORDS}Q", *samples)
        memory_commitment = hashlib.sha3_384(
            DOMAIN_COMMITMENT + params_bytes + encoded_registers
            + encoded_accumulator + encoded_samples
        ).digest()
        digest = hashlib.sha3_384(
            DOMAIN_RESULT + context.seed + header_digest + nonce_bytes + params_bytes
            + context.schedule_digest + context.dataset_digest + encoded_registers
            + encoded_accumulator + memory_commitment
        ).digest()
        execution_result = ExecutionResult(
            digest=digest,
            registers=tuple(registers),
            schedule_digest=context.schedule_digest,
            dataset_digest=context.dataset_digest,
            memory_commitment=memory_commitment,
        )
        status = "exact_complete"

    return PackedReconstructionResult(
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
        cumulative_rank_probes=cumulative_rank_probes,
        cumulative_shifted_bytes=cumulative_shifted_bytes,
        max_replay_peak_entries=max_peak,
        max_reconstruction_depth=1 if attempts else 0,
        all_replay_states_matched=all_states_matched,
        transcript_commitment=transcript.hexdigest(),
        first_reconstruction=first,
        last_reconstruction=last,
        exhaustion=exhaustion,
        execution_result=execution_result,
    )
