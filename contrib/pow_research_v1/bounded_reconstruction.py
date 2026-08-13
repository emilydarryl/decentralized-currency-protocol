# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""One-miss sparse reconstruction inside the non-consensus v1 half-memory arena."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct

from .bounded_probe import CACHE_ENTRY_BYTES, DOMAIN_BOUNDED_STATE, FIXED_STATE_RESERVE_BYTES
from .powvm import (
    DOMAIN_COMMITMENT,
    DOMAIN_REGISTERS,
    DOMAIN_RESULT,
    FINAL_SAMPLE_WORDS,
    MASK64,
    REGISTER_COUNT,
    EpochContext,
    ExecutionResult,
    _execute_operation,
    _read_u64,
    _rol64,
    _u64,
    _validate_header,
    _validate_seed,
)


DOMAIN_RECONSTRUCTION = b"Soveroot/PowResearch/BoundedReconstruction/v1\x00"
EMPTY_TAG = MASK64
REPLAY_NUMERATOR = 5
REPLAY_DENOMINATOR = 8


@dataclass(frozen=True)
class ReconstructionLayout:
    budget_bytes: int
    fixed_state_reserve_bytes: int
    arena_bytes: int
    write_bitmap_bytes: int
    cache_entry_bytes: int
    primary_cache_capacity: int
    primary_cache_bytes: int
    replay_capacity: int
    replay_workspace_bytes: int
    unused_arena_bytes: int
    admitted_bytes: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class ReconstructionResult:
    status: str
    layout: ReconstructionLayout
    completed_iterations: int
    canonical_reads: int
    cache_hits: int
    initial_zero_reads: int
    materialized_misses: int
    writes: int
    evictions: int
    reconstructed_misses: int
    replayed_iterations: int
    replay_peak_entries: int
    replay_hash_probes: int
    reconstruction_consumer: int | None
    reconstruction_slot: int | None
    reconstruction_word: int | None
    reconstruction_value: int | None
    reconstruction_commitment: str | None
    replay_state_matched: bool
    refusal_consumer: int | None
    refusal_slot: int | None
    refusal_word: int | None
    refusal_state_commitment: str | None
    execution_result: ExecutionResult | None

    def to_dict(self) -> dict[str, object]:
        document = asdict(self)
        document["execution_result"] = (
            None if self.execution_result is None else self.execution_result.to_dict()
        )
        return document


class _MaterializedMiss(Exception):
    def __init__(self, consumer: int, slot: int, word: int) -> None:
        super().__init__("materialized value is absent from the primary cache")
        self.consumer = consumer
        self.slot = slot
        self.word = word


class _ReplayExhausted(Exception):
    pass


class _StopAfterRefusal(Exception):
    pass


def _initial_machine_state(
    context: EpochContext,
    header_digest: bytes,
    nonce_bytes: bytes,
) -> tuple[list[int], int]:
    raw = hashlib.shake_256(
        DOMAIN_REGISTERS
        + context.seed
        + header_digest
        + nonce_bytes
        + context.params.encode()
    ).digest(REGISTER_COUNT * 8 + 8)
    return list(struct.unpack("<8Q", raw[:64])), struct.unpack_from("<Q", raw, 64)[0]


def _mix_step(
    context: EpochContext,
    scratch: object,
    registers: list[int],
    accumulator: int,
    iteration: int,
) -> int:
    word_count = context.params.scratchpad_bytes // 8
    pass_index = iteration // word_count
    word_index = iteration & (word_count - 1)
    lane = iteration & 7
    entry = context.schedule[iteration & 63]
    x = registers[lane]
    y = registers[(lane + 1) & 7]
    z = registers[(lane + 3) & 7]
    first_selector = x ^ _rol64(y, iteration) ^ accumulator ^ entry.immediate
    first_scratch = scratch.read(first_selector, iteration, 0)
    dataset_selector = first_scratch ^ z ^ _rol64(accumulator, lane + pass_index) ^ iteration
    dataset_word = _read_u64(context.dataset, dataset_selector)
    second_selector = (
        dataset_word
        ^ registers[(lane + 5) & 7]
        ^ _rol64(_u64(first_scratch + accumulator), entry.immediate)
    )
    second_scratch = scratch.read(second_selector, iteration, 1)
    mixed = _execute_operation(
        entry.opcode,
        x,
        y,
        first_scratch,
        second_scratch,
        dataset_word,
        entry.immediate,
    )
    accumulator = _u64(
        _rol64(
            accumulator ^ mixed ^ dataset_word,
            first_scratch ^ second_scratch ^ entry.immediate,
        )
        + first_scratch
        + entry.immediate
        + iteration
    )
    scratch.write(word_index, mixed ^ accumulator ^ second_scratch)
    scratch.write(
        second_selector,
        second_scratch ^ _rol64(_u64(mixed + accumulator), dataset_word),
    )
    registers[lane] = _u64(mixed + accumulator + first_scratch)
    neighbor = (lane + 2) & 7
    registers[neighbor] = _u64(
        registers[neighbor] ^ _rol64(_u64(dataset_word + first_scratch), second_scratch)
    )
    return accumulator


class _OneArena:
    def __init__(self, scratchpad_bytes: int, budget_bytes: int) -> None:
        self.word_count = scratchpad_bytes // 8
        bitmap_bytes = (self.word_count + 7) // 8
        arena_bytes = budget_bytes - FIXED_STATE_RESERVE_BYTES
        if arena_bytes <= bitmap_bytes + CACHE_ENTRY_BYTES * 2:
            raise ValueError("budget cannot hold primary and replay entries")
        total_slots = (arena_bytes - bitmap_bytes) // CACHE_ENTRY_BYTES
        replay_capacity = total_slots * REPLAY_NUMERATOR // REPLAY_DENOMINATOR
        primary_capacity = total_slots - replay_capacity
        if replay_capacity == 0 or primary_capacity == 0:
            raise ValueError("budget cannot split primary and replay capacities")
        primary_bytes = primary_capacity * CACHE_ENTRY_BYTES
        replay_bytes = replay_capacity * CACHE_ENTRY_BYTES
        unused = arena_bytes - bitmap_bytes - primary_bytes - replay_bytes
        self.layout = ReconstructionLayout(
            budget_bytes=budget_bytes,
            fixed_state_reserve_bytes=FIXED_STATE_RESERVE_BYTES,
            arena_bytes=arena_bytes,
            write_bitmap_bytes=bitmap_bytes,
            cache_entry_bytes=CACHE_ENTRY_BYTES,
            primary_cache_capacity=primary_capacity,
            primary_cache_bytes=primary_bytes,
            replay_capacity=replay_capacity,
            replay_workspace_bytes=replay_bytes,
            unused_arena_bytes=unused,
            admitted_bytes=FIXED_STATE_RESERVE_BYTES + arena_bytes,
        )
        self.arena = bytearray(arena_bytes)
        self.primary_offset = bitmap_bytes
        self.replay_offset = bitmap_bytes + primary_bytes
        for slot in range(primary_capacity):
            struct.pack_into("<Q", self.arena, self.primary_offset + slot * CACHE_ENTRY_BYTES, EMPTY_TAG)
        self.canonical_reads = 0
        self.cache_hits = 0
        self.initial_zero_reads = 0
        self.materialized_misses = 0
        self.writes = 0
        self.evictions = 0

    def _written(self, word: int) -> bool:
        return bool(self.arena[word // 8] & (1 << (word & 7)))

    def _mark_written(self, word: int) -> None:
        self.arena[word // 8] |= 1 << (word & 7)

    def _primary_entry(self, word: int) -> int:
        return self.primary_offset + (word % self.layout.primary_cache_capacity) * CACHE_ENTRY_BYTES

    def read(self, selector: int, consumer: int, slot: int) -> int:
        word = selector & (self.word_count - 1)
        self.canonical_reads += 1
        offset = self._primary_entry(word)
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
        offset = self._primary_entry(word)
        previous = struct.unpack_from("<Q", self.arena, offset)[0]
        if previous != EMPTY_TAG and previous != word:
            self.evictions += 1
        struct.pack_into("<QQ", self.arena, offset, word, value & MASK64)
        self._mark_written(word)
        self.writes += 1

    def retain_reconstructed(self, word: int, value: int) -> None:
        offset = self._primary_entry(word)
        previous = struct.unpack_from("<Q", self.arena, offset)[0]
        if previous != EMPTY_TAG and previous != word:
            self.evictions += 1
        struct.pack_into("<QQ", self.arena, offset, word, value & MASK64)


class _SparseReplay:
    def __init__(self, owner: _OneArena) -> None:
        self.owner = owner
        self.capacity = owner.layout.replay_capacity
        self.offset = owner.replay_offset
        self.distinct = 0
        self.peak_entries = 0
        self.hash_probes = 0
        for slot in range(self.capacity):
            struct.pack_into("<Q", owner.arena, self.offset + slot * CACHE_ENTRY_BYTES, EMPTY_TAG)

    def _find(self, word: int, for_write: bool) -> int | None:
        start = ((word * 0x9E3779B97F4A7C15) & MASK64) % self.capacity
        for distance in range(self.capacity):
            self.hash_probes += 1
            slot = (start + distance) % self.capacity
            offset = self.offset + slot * CACHE_ENTRY_BYTES
            tag = struct.unpack_from("<Q", self.owner.arena, offset)[0]
            if tag == word:
                return offset
            if tag == EMPTY_TAG:
                return offset if for_write else None
        if for_write:
            raise _ReplayExhausted("sparse replay workspace is full")
        return None

    def read(self, selector: int, _consumer: int, _slot: int) -> int:
        word = selector & (self.owner.word_count - 1)
        offset = self._find(word, False)
        return 0 if offset is None else struct.unpack_from("<Q", self.owner.arena, offset + 8)[0]

    def write(self, selector: int, value: int) -> None:
        word = selector & (self.owner.word_count - 1)
        offset = self._find(word, True)
        if offset is None:
            raise _ReplayExhausted("sparse replay lookup failed")
        if struct.unpack_from("<Q", self.owner.arena, offset)[0] == EMPTY_TAG:
            self.distinct += 1
            self.peak_entries = max(self.peak_entries, self.distinct)
        struct.pack_into("<QQ", self.owner.arena, offset, word, value & MASK64)


def _boundary_commitment(
    domain: bytes,
    context: EpochContext,
    header_digest: bytes,
    nonce_bytes: bytes,
    registers: list[int],
    accumulator: int,
    consumer: int,
    slot: int,
    word: int,
    value: int | None = None,
) -> str:
    encoded = (
        domain
        + context.seed
        + header_digest
        + nonce_bytes
        + context.params.encode()
        + struct.pack("<QBQ", consumer, slot, word)
        + struct.pack("<8QQ", *registers, accumulator)
    )
    if value is not None:
        encoded += struct.pack("<Q", value)
    return hashlib.sha3_384(encoded).hexdigest()


def reconstruct_first_miss(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
) -> ReconstructionResult:
    """Reconstruct one missing word exactly, continue, then fail closed again."""

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
    reconstructed = 0
    replayed_iterations = 0
    replay_peak = 0
    replay_probes = 0
    reconstruction: tuple[int, int, int, int, str] | None = None
    refusal: tuple[int, int, int, str] | None = None
    replay_state_matched = False

    def perform_reconstruction(miss: _MaterializedMiss) -> None:
        nonlocal reconstructed, replayed_iterations, replay_peak, replay_probes
        nonlocal reconstruction, replay_state_matched
        replay = _SparseReplay(arena)
        replay_registers, replay_accumulator = _initial_machine_state(
            context, header_digest, nonce_bytes
        )
        for replay_iteration in range(miss.consumer):
            replay_accumulator = _mix_step(
                context,
                replay,
                replay_registers,
                replay_accumulator,
                replay_iteration,
            )
        replayed_iterations += miss.consumer
        replay_peak = replay.peak_entries
        replay_state_matched = (
            replay_registers == registers and replay_accumulator == accumulator
        )
        if not replay_state_matched:
            raise RuntimeError("replayed machine state does not match the live prefix")
        value = replay.read(miss.word, miss.consumer, miss.slot)
        replay_probes = replay.hash_probes
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
        reconstruction = (miss.consumer, miss.slot, miss.word, value, commitment)
        reconstructed = 1
        arena.retain_reconstructed(miss.word, value)

    def record_refusal(miss: _MaterializedMiss) -> None:
        nonlocal refusal
        refusal = (
            miss.consumer,
            miss.slot,
            miss.word,
            _boundary_commitment(
                DOMAIN_BOUNDED_STATE,
                context,
                header_digest,
                nonce_bytes,
                registers,
                accumulator,
                miss.consumer,
                miss.slot,
                miss.word,
            ),
        )
        raise _StopAfterRefusal

    class _PrimaryView:
        def read(self, selector: int, consumer: int, slot: int) -> int:
            return arena.read(selector, consumer, slot)

        def write(self, selector: int, value: int) -> None:
            arena.write(selector, value)

    primary = _PrimaryView()
    try:
        for iteration in range(total_iterations):
            while True:
                try:
                    accumulator = _mix_step(context, primary, registers, accumulator, iteration)
                    break
                except _MaterializedMiss as miss:
                    if reconstructed:
                        record_refusal(miss)
                    perform_reconstruction(miss)
            completed += 1
        samples: list[int] = []
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
                    if reconstructed:
                        record_refusal(miss)
                    perform_reconstruction(miss)
            samples.append(sampled)
            selector = _u64(selector ^ sampled)
    except _StopAfterRefusal:
        execution_result = None
        status = "refused_after_one_reconstruction"
    except _ReplayExhausted:
        execution_result = None
        status = "refused_replay_workspace_exhausted"
    else:
        params_bytes = context.params.encode()
        encoded_registers = struct.pack("<8Q", *registers)
        encoded_accumulator = struct.pack("<Q", accumulator)
        encoded_samples = struct.pack(f"<{FINAL_SAMPLE_WORDS}Q", *samples)
        commitment_input = (
            DOMAIN_COMMITMENT
            + params_bytes
            + encoded_registers
            + encoded_accumulator
            + encoded_samples
        )
        memory_commitment = hashlib.sha3_384(commitment_input).digest()
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

    return ReconstructionResult(
        status=status,
        layout=arena.layout,
        completed_iterations=completed,
        canonical_reads=arena.canonical_reads,
        cache_hits=arena.cache_hits,
        initial_zero_reads=arena.initial_zero_reads,
        materialized_misses=arena.materialized_misses,
        writes=arena.writes,
        evictions=arena.evictions,
        reconstructed_misses=reconstructed,
        replayed_iterations=replayed_iterations,
        replay_peak_entries=replay_peak,
        replay_hash_probes=replay_probes,
        reconstruction_consumer=None if reconstruction is None else reconstruction[0],
        reconstruction_slot=None if reconstruction is None else reconstruction[1],
        reconstruction_word=None if reconstruction is None else reconstruction[2],
        reconstruction_value=None if reconstruction is None else reconstruction[3],
        reconstruction_commitment=None if reconstruction is None else reconstruction[4],
        replay_state_matched=replay_state_matched,
        refusal_consumer=None if refusal is None else refusal[0],
        refusal_slot=None if refusal is None else refusal[1],
        refusal_word=None if refusal is None else refusal[2],
        refusal_state_commitment=None if refusal is None else refusal[3],
        execution_result=execution_result,
    )
