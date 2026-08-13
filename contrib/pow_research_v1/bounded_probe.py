# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Fail-closed online half-memory probe for the non-consensus v1 candidate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct

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


DOMAIN_BOUNDED_STATE = b"Soveroot/PowResearch/BoundedProbeState/v1\x00"
FIXED_STATE_RESERVE_BYTES = 512
CACHE_ENTRY_BYTES = 16
EMPTY_TAG = MASK64


@dataclass(frozen=True)
class ProbeLayout:
    budget_bytes: int
    fixed_state_reserve_bytes: int
    arena_bytes: int
    write_bitmap_bytes: int
    cache_entry_bytes: int
    cache_capacity: int
    cache_payload_bytes: int
    unused_arena_bytes: int
    admitted_bytes: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class BoundedProbeResult:
    status: str
    layout: ProbeLayout
    completed_iterations: int
    reads: int
    cache_hits: int
    initial_zero_reads: int
    materialized_misses: int
    writes: int
    evictions: int
    miss_consumer_kind: int | None
    miss_consumer: int | None
    miss_slot: int | None
    miss_word: int | None
    state_commitment: str | None
    execution_result: ExecutionResult | None

    def to_dict(self) -> dict[str, object]:
        document = asdict(self)
        result = document.pop("execution_result")
        document["execution_result"] = None if result is None else self.execution_result.to_dict()
        return document


class _BoundedMiss(Exception):
    def __init__(self, consumer_kind: int, consumer: int, slot: int, word: int) -> None:
        super().__init__("bounded probe encountered a materialized cache miss")
        self.consumer_kind = consumer_kind
        self.consumer = consumer
        self.slot = slot
        self.word = word


class _BoundedArena:
    def __init__(self, scratchpad_bytes: int, budget_bytes: int, total_iterations: int) -> None:
        word_count = scratchpad_bytes // 8
        bitmap_bytes = (word_count + 7) // 8
        arena_bytes = budget_bytes - FIXED_STATE_RESERVE_BYTES
        if arena_bytes <= bitmap_bytes:
            raise ValueError("budget cannot hold the fixed reserve, write bitmap, and one cache entry")
        capacity = (arena_bytes - bitmap_bytes) // CACHE_ENTRY_BYTES
        if capacity == 0:
            raise ValueError("budget cannot hold one cache entry")
        payload_bytes = capacity * CACHE_ENTRY_BYTES
        unused = arena_bytes - bitmap_bytes - payload_bytes
        self.layout = ProbeLayout(
            budget_bytes=budget_bytes,
            fixed_state_reserve_bytes=FIXED_STATE_RESERVE_BYTES,
            arena_bytes=arena_bytes,
            write_bitmap_bytes=bitmap_bytes,
            cache_entry_bytes=CACHE_ENTRY_BYTES,
            cache_capacity=capacity,
            cache_payload_bytes=payload_bytes,
            unused_arena_bytes=unused,
            admitted_bytes=FIXED_STATE_RESERVE_BYTES + arena_bytes,
        )
        self.word_count = word_count
        self.total_iterations = total_iterations
        self.arena = bytearray(arena_bytes)
        self.bitmap_offset = 0
        self.cache_offset = bitmap_bytes
        for slot in range(capacity):
            struct.pack_into("<Q", self.arena, self.cache_offset + slot * CACHE_ENTRY_BYTES, EMPTY_TAG)
        self.reads = 0
        self.cache_hits = 0
        self.initial_zero_reads = 0
        self.materialized_misses = 0
        self.writes = 0
        self.evictions = 0

    def _was_written(self, word: int) -> bool:
        return bool(self.arena[self.bitmap_offset + word // 8] & (1 << (word & 7)))

    def _mark_written(self, word: int) -> None:
        self.arena[self.bitmap_offset + word // 8] |= 1 << (word & 7)

    def _entry_offset(self, word: int) -> int:
        return self.cache_offset + (word % self.layout.cache_capacity) * CACHE_ENTRY_BYTES

    def read(self, selector: int) -> int:
        word = selector & (self.word_count - 1)
        read_ordinal = self.reads
        self.reads += 1
        offset = self._entry_offset(word)
        tag = struct.unpack_from("<Q", self.arena, offset)[0]
        if tag == word:
            self.cache_hits += 1
            return struct.unpack_from("<Q", self.arena, offset + 8)[0]
        if not self._was_written(word):
            self.initial_zero_reads += 1
            return 0

        self.materialized_misses += 1
        if read_ordinal < self.total_iterations * 2:
            raise _BoundedMiss(0, read_ordinal // 2, read_ordinal & 1, word)
        raise _BoundedMiss(1, read_ordinal - self.total_iterations * 2, 0, word)

    def write(self, selector: int, value: int) -> None:
        word = selector & (self.word_count - 1)
        offset = self._entry_offset(word)
        previous = struct.unpack_from("<Q", self.arena, offset)[0]
        if previous != EMPTY_TAG and previous != word:
            self.evictions += 1
        struct.pack_into("<QQ", self.arena, offset, word, value & MASK64)
        self._mark_written(word)
        self.writes += 1


def _state_commitment(
    context: EpochContext,
    header_digest: bytes,
    nonce_bytes: bytes,
    registers: list[int],
    accumulator: int,
    miss: _BoundedMiss,
) -> str:
    encoded = (
        DOMAIN_BOUNDED_STATE
        + context.seed
        + header_digest
        + nonce_bytes
        + context.params.encode()
        + struct.pack("<QBQ", miss.consumer, miss.slot, miss.word)
        + bytes((miss.consumer_kind,))
        + struct.pack("<8QQ", *registers, accumulator)
    )
    return hashlib.sha3_384(encoded).hexdigest()


def probe_bounded_evaluator(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
) -> BoundedProbeResult:
    """Execute exactly until a bounded direct-mapped cache cannot answer a read.

    The probe never substitutes a value after a materialized miss. Its 512-byte
    fixed-state reservation is a declared logical allowance, not an RSS proof.
    """

    _validate_seed(context.seed)
    context.params.validate()
    _validate_header(header)
    if not 0 <= nonce <= MASK64:
        raise ValueError("nonce must be an unsigned 64-bit integer")
    budget = context.params.scratchpad_bytes // 2 if budget_bytes is None else budget_bytes
    if budget <= 0 or budget > context.params.scratchpad_bytes:
        raise ValueError("budget_bytes must be in (0, scratchpad_bytes]")

    params_bytes = context.params.encode()
    nonce_bytes = struct.pack("<Q", nonce)
    header_digest = hashlib.sha3_384(header).digest()
    initial_state = hashlib.shake_256(
        DOMAIN_REGISTERS + context.seed + header_digest + nonce_bytes + params_bytes
    ).digest(REGISTER_COUNT * 8 + 8)
    registers = list(struct.unpack("<8Q", initial_state[: REGISTER_COUNT * 8]))
    accumulator = struct.unpack_from("<Q", initial_state, REGISTER_COUNT * 8)[0]
    word_count = context.params.scratchpad_bytes // 8
    total_iterations = word_count * context.params.passes
    scratch = _BoundedArena(context.params.scratchpad_bytes, budget, total_iterations)

    completed = 0
    try:
        for iteration in range(total_iterations):
            pass_index = iteration // word_count
            word_index = iteration & (word_count - 1)
            lane = iteration & (REGISTER_COUNT - 1)
            entry = context.schedule[iteration & 63]
            x = registers[lane]
            y = registers[(lane + 1) & 7]
            z = registers[(lane + 3) & 7]
            first_selector = x ^ _rol64(y, iteration) ^ accumulator ^ entry.immediate
            first_scratch = scratch.read(first_selector)
            dataset_selector = first_scratch ^ z ^ _rol64(accumulator, lane + pass_index) ^ iteration
            dataset_word = _read_u64(context.dataset, dataset_selector)
            second_selector = (
                dataset_word
                ^ registers[(lane + 5) & 7]
                ^ _rol64(_u64(first_scratch + accumulator), entry.immediate)
            )
            second_scratch = scratch.read(second_selector)
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
                registers[neighbor]
                ^ _rol64(_u64(dataset_word + first_scratch), second_scratch)
            )
            completed += 1

        samples: list[int] = []
        selector = accumulator ^ registers[0] ^ registers[4]
        for sample_index in range(FINAL_SAMPLE_WORDS):
            selector = _u64(
                _rol64(selector ^ registers[sample_index & 7], sample_index + 1)
                + 0x9E3779B97F4A7C15
                + sample_index
            )
            sampled = scratch.read(selector)
            samples.append(sampled)
            selector = _u64(selector ^ sampled)
    except _BoundedMiss as miss:
        return BoundedProbeResult(
            status="refused_materialized_miss",
            layout=scratch.layout,
            completed_iterations=completed,
            reads=scratch.reads,
            cache_hits=scratch.cache_hits,
            initial_zero_reads=scratch.initial_zero_reads,
            materialized_misses=scratch.materialized_misses,
            writes=scratch.writes,
            evictions=scratch.evictions,
            miss_consumer_kind=miss.consumer_kind,
            miss_consumer=miss.consumer,
            miss_slot=miss.slot,
            miss_word=miss.word,
            state_commitment=_state_commitment(
                context, header_digest, nonce_bytes, registers, accumulator, miss
            ),
            execution_result=None,
        )

    encoded_registers = struct.pack("<8Q", *registers)
    encoded_accumulator = struct.pack("<Q", accumulator)
    encoded_samples = struct.pack(f"<{FINAL_SAMPLE_WORDS}Q", *samples)
    commitment_input = (
        DOMAIN_COMMITMENT + params_bytes + encoded_registers + encoded_accumulator + encoded_samples
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
    return BoundedProbeResult(
        status="exact_complete",
        layout=scratch.layout,
        completed_iterations=completed,
        reads=scratch.reads,
        cache_hits=scratch.cache_hits,
        initial_zero_reads=scratch.initial_zero_reads,
        materialized_misses=scratch.materialized_misses,
        writes=scratch.writes,
        evictions=scratch.evictions,
        miss_consumer_kind=None,
        miss_consumer=None,
        miss_slot=None,
        miss_word=None,
        state_commitment=None,
        execution_result=execution_result,
    )
