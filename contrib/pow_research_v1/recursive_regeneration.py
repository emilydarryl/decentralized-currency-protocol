# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""First exact recursive value regeneration inside the v1 half-memory arena."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct

from .bounded_probe import CACHE_ENTRY_BYTES, FIXED_STATE_RESERVE_BYTES
from .bounded_reconstruction import (
    DOMAIN_RECONSTRUCTION,
    EMPTY_TAG,
    _MaterializedMiss,
    _boundary_commitment,
    _initial_machine_state,
    _mix_step,
)
from .powvm import (
    MASK64,
    EpochContext,
    _execute_operation,
    _read_u64,
    _rol64,
    _u64,
    _validate_header,
    _validate_seed,
)


DOMAIN_RECURSIVE_REGENERATION = b"Soveroot/PowResearch/RecursiveRegeneration/v1\x00"
FRAME_BYTES = 104
MEMO_ENTRY_BYTES = 12
MEMO_WAYS = 4
MEMO_WORD_BITS = 15
EMPTY_MEMO_KEY = 0xFFFFFFFF
PRIMARY_NUMERATOR = 1
PRIMARY_DENOMINATOR = 64
DEFAULT_WORK_LIMIT = 1_000_000
MAXIMUM_FRAME_CAPACITY = 20


@dataclass(frozen=True)
class RecursiveLayout:
    budget_bytes: int
    fixed_state_reserve_bytes: int
    arena_bytes: int
    write_bitmap_bytes: int
    primary_cache_capacity: int
    primary_cache_bytes: int
    frame_bytes: int
    frame_capacity: int
    frame_reserve_bytes: int
    memo_entry_bytes: int
    memo_capacity: int
    memo_bytes: int
    unused_arena_bytes: int
    admitted_bytes: int


@dataclass(frozen=True)
class RecursiveBoundary:
    consumer: int
    slot: int
    word: int
    value: int
    regeneration_calls: int
    regeneration_cache_hits: int
    regeneration_completed_values: int
    regeneration_iterations: int
    maximum_depth: int
    memo_peak_entries: int
    memo_evictions: int
    memo_probes: int
    memo_shifted_bytes: int
    commitment: str


@dataclass(frozen=True)
class RecursiveExhaustion:
    reason: str
    stop_iteration: int
    word: int
    attempted_depth: int
    regeneration_iterations: int


@dataclass(frozen=True)
class RecursiveRegenerationResult:
    status: str
    layout: RecursiveLayout
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
    refusal_consumer: int | None
    refusal_slot: int | None
    refusal_word: int | None
    refusal_state_commitment: str | None
    exhaustion: RecursiveExhaustion | None
    transcript_commitment: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class _RegenerationExhausted(Exception):
    def __init__(self, reason: str, stop: int, word: int, depth: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.stop = stop
        self.word = word
        self.depth = depth


class _RecursiveArena:
    def __init__(self, scratchpad_bytes: int, budget_bytes: int) -> None:
        self.word_count = scratchpad_bytes // 8
        bitmap_bytes = (self.word_count + 7) // 8
        arena_bytes = budget_bytes - FIXED_STATE_RESERVE_BYTES
        if arena_bytes <= bitmap_bytes + CACHE_ENTRY_BYTES + FRAME_BYTES + MEMO_ENTRY_BYTES:
            raise ValueError("budget cannot hold recursive regeneration structures")
        total_primary_slots = (arena_bytes - bitmap_bytes) // CACHE_ENTRY_BYTES
        primary_capacity = total_primary_slots * PRIMARY_NUMERATOR // PRIMARY_DENOMINATOR
        primary_bytes = primary_capacity * CACHE_ENTRY_BYTES
        auxiliary_bytes = arena_bytes - bitmap_bytes - primary_bytes
        frame_capacity = min(
            MAXIMUM_FRAME_CAPACITY,
            (auxiliary_bytes - MEMO_ENTRY_BYTES) // FRAME_BYTES,
        )
        if frame_capacity == 0:
            raise ValueError("budget cannot hold one regeneration frame")
        frame_reserve_bytes = frame_capacity * FRAME_BYTES
        memo_capacity = (
            (auxiliary_bytes - frame_reserve_bytes) // MEMO_ENTRY_BYTES // MEMO_WAYS
        ) * MEMO_WAYS
        if memo_capacity == 0:
            raise ValueError("budget cannot hold one regeneration memo entry")
        memo_bytes = memo_capacity * MEMO_ENTRY_BYTES
        unused = auxiliary_bytes - frame_reserve_bytes - memo_bytes
        self.layout = RecursiveLayout(
            budget_bytes, FIXED_STATE_RESERVE_BYTES, arena_bytes, bitmap_bytes,
            primary_capacity, primary_bytes, FRAME_BYTES, frame_capacity,
            frame_reserve_bytes, MEMO_ENTRY_BYTES, memo_capacity, memo_bytes,
            unused, budget_bytes,
        )
        self.arena = bytearray(arena_bytes)
        self.primary_offset = bitmap_bytes
        self.frame_offset = self.primary_offset + primary_bytes
        self.memo_offset = self.frame_offset + frame_reserve_bytes
        for slot in range(primary_capacity):
            struct.pack_into("<Q", self.arena, self.primary_offset + slot * CACHE_ENTRY_BYTES, EMPTY_TAG)
        for slot in range(memo_capacity):
            struct.pack_into("<I", self.arena, self.memo_offset + slot * MEMO_ENTRY_BYTES, EMPTY_MEMO_KEY)
        self.canonical_reads = self.cache_hits = self.initial_zero_reads = 0
        self.materialized_misses = self.writes = self.evictions = 0

    def _written(self, word: int) -> bool:
        return bool(self.arena[word // 8] & (1 << (word & 7)))

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
        self.arena[word // 8] |= 1 << (word & 7)
        self.writes += 1

    def retain(self, word: int, value: int) -> None:
        offset = self._primary_entry(word)
        previous = struct.unpack_from("<Q", self.arena, offset)[0]
        if previous != EMPTY_TAG and previous != word:
            self.evictions += 1
        struct.pack_into("<QQ", self.arena, offset, word, value & MASK64)


class _RecursiveRegenerator:
    def __init__(
        self,
        owner: _RecursiveArena,
        context: EpochContext,
        header_digest: bytes,
        nonce_bytes: bytes,
        work_limit: int,
    ) -> None:
        self.owner = owner
        self.context = context
        self.header_digest = header_digest
        self.nonce_bytes = nonce_bytes
        self.work_limit = work_limit
        self.calls = self.cache_hits = self.completed_values = self.iterations = 0
        self.maximum_depth = self.memo_entries = self.memo_peak_entries = self.memo_evictions = 0
        self.memo_probes = self.memo_shifted_bytes = 0

    def _memo_key(self, stop: int, word: int) -> int:
        if stop >= (1 << (32 - MEMO_WORD_BITS)) or word >= (1 << MEMO_WORD_BITS):
            raise ValueError("recursive memo key exceeds the packed v1 range")
        return (stop << MEMO_WORD_BITS) | word

    def _memo_set(self, key: int) -> int:
        sets = self.owner.layout.memo_capacity // MEMO_WAYS
        return ((key * 0x9E3779B1) & 0xFFFFFFFF) % sets

    def _memo_offset(self, set_index: int, way: int) -> int:
        slot = set_index * MEMO_WAYS + way
        return self.owner.memo_offset + slot * MEMO_ENTRY_BYTES

    def _memo_get(self, stop: int, word: int) -> int | None:
        self.memo_probes += 1
        key = self._memo_key(stop, word)
        set_index = self._memo_set(key)
        for way in range(MEMO_WAYS):
            offset = self._memo_offset(set_index, way)
            stored_key, value = struct.unpack_from("<IQ", self.owner.arena, offset)
            if stored_key == key:
                self.cache_hits += 1
                return value
        return None

    def _memo_put(self, stop: int, word: int, value: int) -> None:
        self.memo_probes += 1
        key = self._memo_key(stop, word)
        set_index = self._memo_set(key)
        selected_way: int | None = None
        for way in range(MEMO_WAYS):
            offset = self._memo_offset(set_index, way)
            stored_key = struct.unpack_from("<I", self.owner.arena, offset)[0]
            if stored_key == key:
                selected_way = way
                break
            if stored_key == EMPTY_MEMO_KEY and selected_way is None:
                selected_way = way
        if selected_way is None:
            selected_way = ((key >> 16) ^ key) & (MEMO_WAYS - 1)
            self.memo_evictions += 1
        offset = self._memo_offset(set_index, selected_way)
        stored_key = struct.unpack_from("<I", self.owner.arena, offset)[0]
        if stored_key == EMPTY_MEMO_KEY:
            self.memo_entries += 1
            self.memo_peak_entries = max(self.memo_peak_entries, self.memo_entries)
        struct.pack_into("<IQ", self.owner.arena, offset, key, value & MASK64)

    def value_at(self, target_word: int, stop: int, depth: int = 1) -> int:
        self.calls += 1
        if stop == 0:
            self.completed_values += 1
            return 0
        self.maximum_depth = max(self.maximum_depth, depth)
        if depth > self.owner.layout.frame_capacity:
            raise _RegenerationExhausted("frame_capacity", stop, target_word, depth)
        cached = self._memo_get(stop, target_word)
        if cached is not None:
            return cached
        registers, accumulator = _initial_machine_state(
            self.context, self.header_digest, self.nonce_bytes
        )
        target_value = 0
        word_count = self.owner.word_count
        for iteration in range(stop):
            if self.iterations >= self.work_limit:
                raise _RegenerationExhausted("work_limit", stop, target_word, depth)
            self.iterations += 1
            pass_index = iteration // word_count
            word_index = iteration & (word_count - 1)
            lane = iteration & 7
            entry = self.context.schedule[iteration & 63]
            x = registers[lane]
            y = registers[(lane + 1) & 7]
            z = registers[(lane + 3) & 7]
            first_selector = x ^ _rol64(y, iteration) ^ accumulator ^ entry.immediate
            first_word = first_selector & (word_count - 1)
            first_scratch = self.value_at(first_word, iteration, depth + 1)
            dataset_selector = first_scratch ^ z ^ _rol64(accumulator, lane + pass_index) ^ iteration
            dataset_word = _read_u64(self.context.dataset, dataset_selector)
            second_selector = (
                dataset_word
                ^ registers[(lane + 5) & 7]
                ^ _rol64(_u64(first_scratch + accumulator), entry.immediate)
            )
            second_word = second_selector & (word_count - 1)
            second_scratch = self.value_at(second_word, iteration, depth + 1)
            mixed = _execute_operation(
                entry.opcode, x, y, first_scratch, second_scratch,
                dataset_word, entry.immediate,
            )
            accumulator = _u64(
                _rol64(
                    accumulator ^ mixed ^ dataset_word,
                    first_scratch ^ second_scratch ^ entry.immediate,
                )
                + first_scratch + entry.immediate + iteration
            )
            first_write = mixed ^ accumulator ^ second_scratch
            second_write = second_scratch ^ _rol64(_u64(mixed + accumulator), dataset_word)
            if word_index == target_word:
                target_value = first_write & MASK64
            if second_word == target_word:
                target_value = second_write & MASK64
            registers[lane] = _u64(mixed + accumulator + first_scratch)
            neighbor = (lane + 2) & 7
            registers[neighbor] = _u64(
                registers[neighbor] ^ _rol64(_u64(dataset_word + first_scratch), second_scratch)
            )
        self._memo_put(stop, target_word, target_value)
        self.completed_values += 1
        return target_value


def reconstruct_first_recursively(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
    work_limit: int = DEFAULT_WORK_LIMIT,
) -> RecursiveRegenerationResult:
    """Regenerate the first primary miss recursively, then refuse at the next miss."""

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
    total_iterations = context.params.passes * (context.params.scratchpad_bytes // 8)
    arena = _RecursiveArena(context.params.scratchpad_bytes, budget)
    regenerator = _RecursiveRegenerator(arena, context, header_digest, nonce_bytes, work_limit)
    completed = attempts = successful = 0
    first: RecursiveBoundary | None = None
    refusal: tuple[int, int, int, str] | None = None
    exhaustion: RecursiveExhaustion | None = None
    transcript = hashlib.sha3_384(DOMAIN_RECURSIVE_REGENERATION)

    class _PrimaryView:
        def read(self, selector: int, consumer: int, slot: int) -> int:
            return arena.read(selector, consumer, slot)

        def write(self, selector: int, value: int) -> None:
            arena.write(selector, value)

    primary = _PrimaryView()
    stopped = False
    for iteration in range(total_iterations):
        while True:
            try:
                accumulator = _mix_step(context, primary, registers, accumulator, iteration)
                break
            except _MaterializedMiss as miss:
                attempts += 1
                if successful:
                    refusal = (
                        miss.consumer, miss.slot, miss.word,
                        _boundary_commitment(
                            DOMAIN_RECONSTRUCTION, context, header_digest, nonce_bytes,
                            registers, accumulator, miss.consumer, miss.slot, miss.word,
                        ),
                    )
                    stopped = True
                    break
                try:
                    value = regenerator.value_at(miss.word, miss.consumer)
                except _RegenerationExhausted as error:
                    exhaustion = RecursiveExhaustion(
                        error.reason, error.stop, error.word, error.depth, regenerator.iterations
                    )
                    stopped = True
                    break
                commitment = _boundary_commitment(
                    DOMAIN_RECURSIVE_REGENERATION, context, header_digest, nonce_bytes,
                    registers, accumulator, miss.consumer, miss.slot, miss.word, value,
                )
                first = RecursiveBoundary(
                    miss.consumer, miss.slot, miss.word, value, regenerator.calls,
                    regenerator.cache_hits, regenerator.completed_values,
                    regenerator.iterations, regenerator.maximum_depth,
                    regenerator.memo_peak_entries, regenerator.memo_evictions,
                    regenerator.memo_probes, regenerator.memo_shifted_bytes, commitment,
                )
                transcript.update(bytes.fromhex(commitment))
                arena.retain(miss.word, value)
                successful = 1
        if stopped:
            break
        completed += 1

    if exhaustion is not None:
        status = "refused_recursive_regeneration_exhausted"
    elif refusal is not None:
        status = "refused_after_first_recursive_regeneration"
    else:
        status = "refused_unexpected_completion"
    return RecursiveRegenerationResult(
        status, arena.layout, work_limit, completed, arena.canonical_reads,
        arena.cache_hits, arena.initial_zero_reads, arena.materialized_misses,
        arena.writes, arena.evictions, attempts, successful, regenerator.calls,
        regenerator.cache_hits, regenerator.completed_values, regenerator.iterations,
        regenerator.maximum_depth, regenerator.memo_peak_entries,
        regenerator.memo_evictions, regenerator.memo_probes,
        regenerator.memo_shifted_bytes, first,
        None if refusal is None else refusal[0],
        None if refusal is None else refusal[1],
        None if refusal is None else refusal[2],
        None if refusal is None else refusal[3],
        exhaustion, transcript.hexdigest(),
    )
