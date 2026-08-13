# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Repeated reconstruction with indexed pages and bounded neighbor gaps."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct

from .bounded_probe import CACHE_ENTRY_BYTES, FIXED_STATE_RESERVE_BYTES
from .bounded_reconstruction import EMPTY_TAG, _MaterializedMiss, _boundary_commitment, _initial_machine_state, _mix_step
from .packed_reconstruction import RANK_CHUNK_WORDS
from .paged_gap_reconstruction import PAGE_BYTES, PAGE_METADATA_BYTES, PAGE_SLOTS
from .powvm import DOMAIN_COMMITMENT, DOMAIN_RESULT, FINAL_SAMPLE_WORDS, MASK64, EpochContext, ExecutionResult, _rol64, _u64, _validate_header, _validate_seed


DOMAIN_INDEXED_GAP_RECONSTRUCTION = b"Soveroot/PowResearch/IndexedGapReconstruction/v1\x00"
DOMAIN_INDEXED_GAP_TRANSCRIPT = b"Soveroot/PowResearch/IndexedGapTranscript/v1\x00"
PRIMARY_NUMERATOR = 1
PRIMARY_DENOMINATOR = 4


@dataclass(frozen=True)
class IndexedGapLayout:
    budget_bytes: int
    fixed_state_reserve_bytes: int
    arena_bytes: int
    canonical_write_bitmap_bytes: int
    primary_cache_capacity: int
    primary_cache_bytes: int
    replay_bitmap_bytes: int
    rank_directory_bytes: int
    page_slots: int
    max_pages: int
    page_directory_bytes: int
    page_count_bytes: int
    page_index_bytes: int
    replay_value_slots: int
    replay_value_bytes: int
    unused_arena_bytes: int
    admitted_bytes: int


@dataclass(frozen=True)
class IndexedGapBoundary:
    consumer: int
    slot: int
    word: int
    value: int
    replayed_iterations: int
    replay_peak_values: int
    replay_peak_pages: int
    replay_rank_probes: int
    replay_index_probes: int
    replay_directory_probes: int
    replay_rebalances: int
    replay_shifted_bytes: int
    commitment: str


@dataclass(frozen=True)
class IndexedGapExhaustion:
    consumer: int
    slot: int
    word: int
    replay_completed_iterations: int
    replay_occupied_values: int
    replay_allocated_pages: int
    replay_rank_probes: int
    replay_index_probes: int
    replay_directory_probes: int
    replay_rebalances: int
    replay_shifted_bytes: int
    state_commitment: str


@dataclass(frozen=True)
class IndexedGapReconstructionResult:
    status: str
    layout: IndexedGapLayout
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
    cumulative_index_probes: int
    cumulative_directory_probes: int
    cumulative_rebalances: int
    cumulative_shifted_bytes: int
    max_replay_peak_values: int
    max_replay_peak_pages: int
    max_reconstruction_depth: int
    all_replay_states_matched: bool
    transcript_commitment: str
    first_reconstruction: IndexedGapBoundary | None
    last_reconstruction: IndexedGapBoundary | None
    exhaustion: IndexedGapExhaustion | None
    execution_result: ExecutionResult | None

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["execution_result"] = None if self.execution_result is None else self.execution_result.to_dict()
        return result


class _IndexedGapExhausted(Exception):
    pass


class _IndexedGapArena:
    def __init__(self, scratchpad_bytes: int, budget_bytes: int) -> None:
        self.word_count = scratchpad_bytes // 8
        bitmap_bytes = (self.word_count + 7) // 8
        rank_chunks = (self.word_count + RANK_CHUNK_WORDS - 1) // RANK_CHUNK_WORDS
        rank_bytes = (rank_chunks + 1) * 2
        arena_bytes = budget_bytes - FIXED_STATE_RESERVE_BYTES
        base = arena_bytes - bitmap_bytes * 2 - rank_bytes
        primary_bytes = base * PRIMARY_NUMERATOR // PRIMARY_DENOMINATOR
        primary_bytes -= primary_bytes % CACHE_ENTRY_BYTES
        primary_capacity = primary_bytes // CACHE_ENTRY_BYTES
        replay_budget = base - primary_bytes
        max_pages = (replay_budget - 2) // (PAGE_BYTES + PAGE_METADATA_BYTES + 2)
        directory_bytes = max_pages * 2
        count_bytes = max_pages * 2
        index_bytes = (max_pages + 1) * 2
        value_bytes = max_pages * PAGE_BYTES
        unused = replay_budget - directory_bytes - count_bytes - index_bytes - value_bytes
        if primary_capacity == 0 or max_pages == 0:
            raise ValueError("budget cannot hold indexed-gap replay and primary cache")
        self.layout = IndexedGapLayout(
            budget_bytes, FIXED_STATE_RESERVE_BYTES, arena_bytes, bitmap_bytes,
            primary_capacity, primary_bytes, bitmap_bytes, rank_bytes, PAGE_SLOTS,
            max_pages, directory_bytes, count_bytes, index_bytes, max_pages * PAGE_SLOTS,
            value_bytes, unused, budget_bytes,
        )
        self.rank_chunks = rank_chunks
        self.arena = bytearray(arena_bytes)
        self.primary_offset = bitmap_bytes
        self.replay_bitmap_offset = self.primary_offset + primary_bytes
        self.rank_offset = self.replay_bitmap_offset + bitmap_bytes
        self.order_offset = self.rank_offset + rank_bytes
        self.count_offset = self.order_offset + directory_bytes
        self.index_offset = self.count_offset + count_bytes
        self.values_offset = self.index_offset + index_bytes
        for slot in range(primary_capacity):
            struct.pack_into("<Q", self.arena, self.primary_offset + slot * CACHE_ENTRY_BYTES, EMPTY_TAG)
        self.canonical_reads = self.cache_hits = self.initial_zero_reads = 0
        self.materialized_misses = self.writes = self.evictions = 0

    def _written(self, word: int) -> bool:
        return bool(self.arena[word // 8] & (1 << (word & 7)))

    def _primary_offset(self, word: int) -> int:
        return self.primary_offset + (word % self.layout.primary_cache_capacity) * CACHE_ENTRY_BYTES

    def read(self, selector: int, consumer: int, slot: int) -> int:
        word = selector & (self.word_count - 1)
        self.canonical_reads += 1
        offset = self._primary_offset(word)
        if struct.unpack_from("<Q", self.arena, offset)[0] == word:
            self.cache_hits += 1
            return struct.unpack_from("<Q", self.arena, offset + 8)[0]
        if not self._written(word):
            self.initial_zero_reads += 1
            return 0
        self.materialized_misses += 1
        raise _MaterializedMiss(consumer, slot, word)

    def _store_primary(self, word: int, value: int) -> None:
        offset = self._primary_offset(word)
        previous = struct.unpack_from("<Q", self.arena, offset)[0]
        if previous != EMPTY_TAG and previous != word:
            self.evictions += 1
        struct.pack_into("<QQ", self.arena, offset, word, value & MASK64)

    def write(self, selector: int, value: int) -> None:
        word = selector & (self.word_count - 1)
        self._store_primary(word, value)
        self.arena[word // 8] |= 1 << (word & 7)
        self.writes += 1

    def retain(self, word: int, value: int) -> None:
        self._store_primary(word, value)


class _IndexedGapReplay:
    def __init__(self, owner: _IndexedGapArena) -> None:
        self.owner = owner
        owner.arena[owner.replay_bitmap_offset:owner.values_offset] = b"\x00" * (owner.values_offset - owner.replay_bitmap_offset)
        self.logical_pages = self.allocated_pages = self.distinct = 0
        self.peak_values = self.peak_pages = 0
        self.rank_probes = self.index_probes = self.directory_probes = 0
        self.rebalances = self.shifted_bytes = 0

    def _u16(self, offset: int) -> int:
        return struct.unpack_from("<H", self.owner.arena, offset)[0]

    def _set_u16(self, offset: int, value: int) -> None:
        struct.pack_into("<H", self.owner.arena, offset, value)

    def _order(self, position: int) -> int:
        self.directory_probes += 1
        return self._u16(self.owner.order_offset + position * 2)

    def _count(self, page: int) -> int:
        self.directory_probes += 1
        return self._u16(self.owner.count_offset + page * 2)

    def _set_count(self, page: int, count: int) -> None:
        self._set_u16(self.owner.count_offset + page * 2, count)

    def _index_add(self, position: int, delta: int) -> None:
        index = position + 1
        while index <= self.owner.layout.max_pages:
            offset = self.owner.index_offset + index * 2
            self._set_u16(offset, self._u16(offset) + delta)
            self.index_probes += 1
            index += index & -index

    def _change_count(self, position: int, page: int, count: int) -> None:
        previous = self._count(page)
        self._set_count(page, count)
        self._index_add(position, count - previous)

    def _rebuild_index(self) -> None:
        start = self.owner.index_offset
        self.owner.arena[start:start + self.owner.layout.page_index_bytes] = b"\x00" * self.owner.layout.page_index_bytes
        for position in range(self.logical_pages):
            page = self._order(position)
            self._index_add(position, self._count(page))

    def _present(self, word: int) -> bool:
        return bool(self.owner.arena[self.owner.replay_bitmap_offset + word // 8] & (1 << (word & 7)))

    def _rank(self, word: int) -> int:
        chunk = word // RANK_CHUNK_WORDS
        total = 0
        index = chunk
        while index > 0:
            total += self._u16(self.owner.rank_offset + index * 2)
            self.rank_probes += 1
            index -= index & -index
        first_byte = chunk * RANK_CHUNK_WORDS // 8
        final_byte = word // 8
        for byte_index in range(first_byte, final_byte):
            total += self.owner.arena[self.owner.replay_bitmap_offset + byte_index].bit_count()
            self.rank_probes += 1
        partial = self.owner.arena[self.owner.replay_bitmap_offset + final_byte]
        total += (partial & ((1 << (word & 7)) - 1)).bit_count()
        self.rank_probes += 1
        return total

    def _rank_add(self, word: int) -> None:
        index = word // RANK_CHUNK_WORDS + 1
        while index <= self.owner.rank_chunks:
            offset = self.owner.rank_offset + index * 2
            self._set_u16(offset, self._u16(offset) + 1)
            self.rank_probes += 1
            index += index & -index

    def _locate(self, rank: int, for_insert: bool) -> tuple[int, int, int]:
        if for_insert and self.logical_pages and rank == self.distinct:
            position = self.logical_pages - 1
            page = self._order(position)
            return position, page, self._count(page)
        index = total = 0
        step = 1 << (self.owner.layout.max_pages.bit_length() - 1)
        while step:
            candidate = index + step
            if candidate <= self.logical_pages:
                value = self._u16(self.owner.index_offset + candidate * 2)
                self.index_probes += 1
                if total + value <= rank:
                    index = candidate
                    total += value
            step >>= 1
        if index >= self.logical_pages:
            raise RuntimeError("indexed-gap rank is outside occupied values")
        page = self._order(index)
        return index, page, rank - total

    def _page_offset(self, page: int, slot: int = 0) -> int:
        return self.owner.values_offset + (page * PAGE_SLOTS + slot) * 8

    def read(self, selector: int, _consumer: int, _slot: int) -> int:
        word = selector & (self.owner.word_count - 1)
        if not self._present(word):
            return 0
        _, page, local = self._locate(self._rank(word), False)
        return struct.unpack_from("<Q", self.owner.arena, self._page_offset(page, local))[0]

    def read_exact_word(self, word: int) -> int:
        if not self._present(word):
            raise RuntimeError("materialized word is absent from indexed-gap replay state")
        _, page, local = self._locate(self._rank(word), False)
        return struct.unpack_from("<Q", self.owner.arena, self._page_offset(page, local))[0]

    def _allocate_first(self) -> tuple[int, int, int]:
        if self.allocated_pages == self.owner.layout.max_pages:
            raise _IndexedGapExhausted("indexed-gap replay has no free physical page")
        page = self.allocated_pages
        self.allocated_pages += 1
        self.logical_pages = 1
        self._set_u16(self.owner.order_offset, page)
        self._set_count(page, 0)
        self.peak_pages = max(self.peak_pages, self.allocated_pages)
        return 0, page, 0

    def _split(self, position: int, page: int, local: int) -> tuple[int, int, int]:
        if self.allocated_pages == self.owner.layout.max_pages:
            raise _IndexedGapExhausted("indexed-gap replay has no free physical page")
        new_page = self.allocated_pages
        self.allocated_pages += 1
        split = PAGE_SLOTS // 2
        moved = PAGE_SLOTS - split
        source = self._page_offset(page, split)
        target = self._page_offset(new_page)
        self.owner.arena[target:target + moved * 8] = self.owner.arena[source:source + moved * 8]
        self.shifted_bytes += moved * 8
        self._set_count(page, split)
        self._set_count(new_page, moved)
        insert_position = position + 1
        directory_move = (self.logical_pages - insert_position) * 2
        if directory_move:
            start = self.owner.order_offset + insert_position * 2
            self.owner.arena[start + 2:start + 2 + directory_move] = self.owner.arena[start:start + directory_move]
            self.shifted_bytes += directory_move
        self._set_u16(self.owner.order_offset + insert_position * 2, new_page)
        self.logical_pages += 1
        self.peak_pages = max(self.peak_pages, self.allocated_pages)
        self._rebuild_index()
        if local >= split:
            return insert_position, new_page, local - split
        return position, page, local

    def _rebalance(self, position: int, page: int, local: int, value: int) -> bool:
        right = None
        left = None
        if position + 1 < self.logical_pages:
            right_page = self._order(position + 1)
            right = (right_page, self._count(right_page))
        if position > 0:
            left_page = self._order(position - 1)
            left = (left_page, self._count(left_page))
        right_free = 0 if right is None else PAGE_SLOTS - right[1]
        left_free = 0 if left is None else PAGE_SLOTS - left[1]
        if right_free == 0 and left_free == 0:
            return False
        self.rebalances += 1
        if right_free >= left_free:
            assert right is not None
            neighbor, count = right
            if count:
                start = self._page_offset(neighbor)
                self.owner.arena[start + 8:start + 8 + count * 8] = self.owner.arena[start:start + count * 8]
                self.shifted_bytes += count * 8
            if local == PAGE_SLOTS:
                struct.pack_into("<Q", self.owner.arena, self._page_offset(neighbor), value & MASK64)
            else:
                ejected = struct.unpack_from("<Q", self.owner.arena, self._page_offset(page, PAGE_SLOTS - 1))[0]
                struct.pack_into("<Q", self.owner.arena, self._page_offset(neighbor), ejected)
                self.shifted_bytes += 8
                move = (PAGE_SLOTS - 1 - local) * 8
                if move:
                    start = self._page_offset(page, local)
                    self.owner.arena[start + 8:start + 8 + move] = self.owner.arena[start:start + move]
                    self.shifted_bytes += move
                struct.pack_into("<Q", self.owner.arena, self._page_offset(page, local), value & MASK64)
            self._change_count(position + 1, neighbor, count + 1)
            return True
        assert left is not None
        neighbor, count = left
        if local == 0:
            struct.pack_into("<Q", self.owner.arena, self._page_offset(neighbor, count), value & MASK64)
        else:
            ejected = struct.unpack_from("<Q", self.owner.arena, self._page_offset(page))[0]
            struct.pack_into("<Q", self.owner.arena, self._page_offset(neighbor, count), ejected)
            self.shifted_bytes += 8
            move = (local - 1) * 8
            if move:
                source = self._page_offset(page, 1)
                self.owner.arena[self._page_offset(page):self._page_offset(page) + move] = self.owner.arena[source:source + move]
                self.shifted_bytes += move
            struct.pack_into("<Q", self.owner.arena, self._page_offset(page, local - 1), value & MASK64)
        self._change_count(position - 1, neighbor, count + 1)
        return True

    def write(self, selector: int, value: int) -> None:
        word = selector & (self.owner.word_count - 1)
        present = self._present(word)
        rank = self._rank(word)
        if self.logical_pages == 0:
            position, page, local = self._allocate_first()
        else:
            position, page, local = self._locate(rank, True)
        if present:
            struct.pack_into("<Q", self.owner.arena, self._page_offset(page, local), value & MASK64)
            return
        count = self._count(page)
        if count == PAGE_SLOTS and self._rebalance(position, page, local, value):
            pass
        else:
            if count == PAGE_SLOTS:
                position, page, local = self._split(position, page, local)
                count = self._count(page)
            move_bytes = (count - local) * 8
            if move_bytes:
                start = self._page_offset(page, local)
                self.owner.arena[start + 8:start + 8 + move_bytes] = self.owner.arena[start:start + move_bytes]
                self.shifted_bytes += move_bytes
            struct.pack_into("<Q", self.owner.arena, self._page_offset(page, local), value & MASK64)
            self._change_count(position, page, count + 1)
        self.owner.arena[self.owner.replay_bitmap_offset + word // 8] |= 1 << (word & 7)
        self._rank_add(word)
        self.distinct += 1
        self.peak_values = max(self.peak_values, self.distinct)


def reconstruct_with_indexed_gaps(context: EpochContext, header: bytes, nonce: int, *, budget_bytes: int | None = None) -> IndexedGapReconstructionResult:
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
    total_iterations = context.params.passes * (context.params.scratchpad_bytes // 8)
    arena = _IndexedGapArena(context.params.scratchpad_bytes, budget)
    completed = attempts = successful = successful_replayed = attempted_replayed = 0
    cumulative_rank = cumulative_index = cumulative_directory = cumulative_rebalances = cumulative_shifted = 0
    max_values = max_pages = 0
    all_states = True
    first = last = exhaustion = None
    transcript = hashlib.sha3_384(DOMAIN_INDEXED_GAP_TRANSCRIPT)

    def perform(miss: _MaterializedMiss) -> bool:
        nonlocal attempts, successful, successful_replayed, attempted_replayed
        nonlocal cumulative_rank, cumulative_index, cumulative_directory, cumulative_rebalances, cumulative_shifted
        nonlocal max_values, max_pages, all_states, first, last, exhaustion
        attempts += 1
        replay = _IndexedGapReplay(arena)
        replay_registers, replay_accumulator = _initial_machine_state(context, header_digest, nonce_bytes)
        replay_completed = 0
        try:
            for iteration in range(min(miss.consumer, total_iterations)):
                replay_accumulator = _mix_step(context, replay, replay_registers, replay_accumulator, iteration)
                replay_completed += 1
        except _IndexedGapExhausted:
            attempted_replayed += replay_completed
            cumulative_rank += replay.rank_probes
            cumulative_index += replay.index_probes
            cumulative_directory += replay.directory_probes
            cumulative_rebalances += replay.rebalances
            cumulative_shifted += replay.shifted_bytes
            max_values = max(max_values, replay.peak_values)
            max_pages = max(max_pages, replay.peak_pages)
            exhaustion = IndexedGapExhaustion(
                miss.consumer, miss.slot, miss.word, replay_completed, replay.distinct,
                replay.allocated_pages, replay.rank_probes, replay.index_probes,
                replay.directory_probes, replay.rebalances, replay.shifted_bytes,
                _boundary_commitment(DOMAIN_INDEXED_GAP_RECONSTRUCTION, context, header_digest,
                                     nonce_bytes, registers, accumulator, miss.consumer, miss.slot, miss.word),
            )
            return False
        attempted_replayed += replay_completed
        successful_replayed += replay_completed
        all_states = all_states and replay_registers == registers and replay_accumulator == accumulator
        if not all_states:
            raise RuntimeError("indexed-gap replay machine state does not match the live prefix")
        value = replay.read_exact_word(miss.word)
        cumulative_rank += replay.rank_probes
        cumulative_index += replay.index_probes
        cumulative_directory += replay.directory_probes
        cumulative_rebalances += replay.rebalances
        cumulative_shifted += replay.shifted_bytes
        max_values = max(max_values, replay.peak_values)
        max_pages = max(max_pages, replay.peak_pages)
        commitment = _boundary_commitment(
            DOMAIN_INDEXED_GAP_RECONSTRUCTION, context, header_digest, nonce_bytes,
            registers, accumulator, miss.consumer, miss.slot, miss.word, value,
        )
        boundary = IndexedGapBoundary(
            miss.consumer, miss.slot, miss.word, value, replay_completed, replay.peak_values,
            replay.peak_pages, replay.rank_probes, replay.index_probes, replay.directory_probes,
            replay.rebalances, replay.shifted_bytes, commitment,
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
            selector = _u64(_rol64(selector ^ registers[sample_index & 7], sample_index + 1) + 0x9E3779B97F4A7C15 + sample_index)
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

    execution_result = None
    status = "refused_indexed_gap_exhausted"
    if not stopped:
        params_bytes = context.params.encode()
        encoded_registers = struct.pack("<8Q", *registers)
        encoded_accumulator = struct.pack("<Q", accumulator)
        encoded_samples = struct.pack(f"<{FINAL_SAMPLE_WORDS}Q", *samples)
        memory_commitment = hashlib.sha3_384(DOMAIN_COMMITMENT + params_bytes + encoded_registers + encoded_accumulator + encoded_samples).digest()
        digest = hashlib.sha3_384(DOMAIN_RESULT + context.seed + header_digest + nonce_bytes + params_bytes + context.schedule_digest + context.dataset_digest + encoded_registers + encoded_accumulator + memory_commitment).digest()
        execution_result = ExecutionResult(digest, tuple(registers), context.schedule_digest, context.dataset_digest, memory_commitment)
        status = "exact_complete"

    return IndexedGapReconstructionResult(
        status, arena.layout, completed, arena.canonical_reads, arena.cache_hits,
        arena.initial_zero_reads, arena.materialized_misses, arena.writes, arena.evictions,
        attempts, successful, successful_replayed, attempted_replayed, cumulative_rank,
        cumulative_index, cumulative_directory, cumulative_rebalances, cumulative_shifted,
        max_values, max_pages, 1 if attempts else 0, all_states, transcript.hexdigest(),
        first, last, exhaustion, execution_result,
    )
