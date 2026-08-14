# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Repeated recursive regeneration with byte-accounted machine-state checkpoints."""

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
    _execute_operation,
    _read_u64,
    _rol64,
    _u64,
    _validate_header,
    _validate_seed,
)
from .recursive_regeneration import (
    DEFAULT_WORK_LIMIT,
    FRAME_BYTES,
    RecursiveBoundary,
    _RecursiveArena,
    _RecursiveRegenerator,
    _RegenerationExhausted,
)
from .repeated_recursive_regeneration import RepeatedRecursiveExhaustion


DOMAIN_CHECKPOINT_REGENERATION = b"Soveroot/PowResearch/CheckpointRegeneration/v1\x00"
DOMAIN_TARGET_CHECKPOINT_REGENERATION = (
    b"Soveroot/PowResearch/TargetCheckpointRegeneration/v1\x00"
)
DOMAIN_DEPENDENCY_BUNDLE_REGENERATION = (
    b"Soveroot/PowResearch/DependencyBundleRegeneration/v1\x00"
)
DOMAIN_OPERATION_BOUNDED_DEPENDENCY_BUNDLE_REGENERATION = (
    b"Soveroot/PowResearch/OperationBoundedDependencyBundleRegeneration/v1\x00"
)
DOMAIN_PHYSICALLY_ACCOUNTED_DEPENDENCY_BUNDLE_REGENERATION = (
    b"Soveroot/PowResearch/PhysicallyAccountedDependencyBundleRegeneration/v1\x00"
)
DOMAIN_ITERATIVE_WORK_STACK_DEPENDENCY_BUNDLE_REGENERATION = (
    b"Soveroot/PowResearch/IterativeWorkStackDependencyBundleRegeneration/v1\x00"
)
DOMAIN_HIERARCHICAL_CHECKPOINT_LADDER_REGENERATION = (
    b"Soveroot/PowResearch/HierarchicalCheckpointLadderRegeneration/v1\x00"
)
CHECKPOINT_ENTRY_BYTES = 80
TARGET_CHECKPOINT_ENTRY_BYTES = 88
EMPTY_CHECKPOINT_STOP = 0xFFFFFFFF
EMPTY_BUNDLE_WORD = 0xFFFF
DEFAULT_CHECKPOINT_CAPACITY = 4
DEFAULT_CHECKPOINT_STRIDE = 8
DEFAULT_DEPENDENCY_BUNDLE_WIDTH = 4
DEFAULT_DEPENDENCY_BUNDLE_CAPACITY = 12
DEFAULT_TOTAL_OPERATION_LIMIT = 5_000_000
NATIVE_STACK_FRAME_ALLOWANCE_BYTES = 2_048
NATIVE_STACK_DEPTH_CAPACITY = 20
NATIVE_STACK_RESERVE_BYTES = (
    NATIVE_STACK_FRAME_ALLOWANCE_BYTES * NATIVE_STACK_DEPTH_CAPACITY
)
ALLOCATOR_ALLOWANCE_BYTES = 4_096
PHYSICAL_EXTERNAL_RESERVE_BYTES = (
    NATIVE_STACK_RESERVE_BYTES + ALLOCATOR_ALLOWANCE_BYTES
)
ITERATIVE_EXTERNAL_RESERVE_BYTES = ALLOCATOR_ALLOWANCE_BYTES
ITERATIVE_FRAME_STRUCT = struct.Struct("<IIIHBBQ8QQQ")
if ITERATIVE_FRAME_STRUCT.size != FRAME_BYTES:
    raise AssertionError("iterative frame encoding must match the arena frame reserve")
HIERARCHICAL_CHECKPOINT_LEVELS = (
    (0, 8, 32, 0),
    (1, 64, 16, 32),
    (2, 512, 8, 48),
    (3, 4096, 8, 56),
)
HIERARCHICAL_CHECKPOINT_CAPACITY = 64
if sum(level[2] for level in HIERARCHICAL_CHECKPOINT_LEVELS) != HIERARCHICAL_CHECKPOINT_CAPACITY:
    raise AssertionError("hierarchical checkpoint capacities must cover every slot")


def _dependency_bundle_offsets(width: int) -> tuple[int, int, int]:
    """Return value, machine-state, and entry offsets for a packed bundle."""

    if width < 2 or width > DEFAULT_DEPENDENCY_BUNDLE_WIDTH:
        raise ValueError("dependency_bundle_width must be in [2, 4]")
    value_offset = (4 + width * 2 + 7) & ~7
    state_offset = value_offset + width * 8
    return value_offset, state_offset, state_offset + 9 * 8


@dataclass(frozen=True)
class CheckpointLayout:
    budget_bytes: int
    fixed_state_reserve_bytes: int
    arena_bytes: int
    write_bitmap_bytes: int
    primary_cache_capacity: int
    primary_cache_bytes: int
    frame_bytes: int
    frame_capacity: int
    frame_reserve_bytes: int
    checkpoint_entry_bytes: int
    checkpoint_capacity: int
    checkpoint_bytes: int
    checkpoint_stride: int
    memo_entry_bytes: int
    memo_capacity: int
    memo_bytes: int
    unused_arena_bytes: int
    admitted_bytes: int


@dataclass(frozen=True)
class CheckpointBoundary:
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
    checkpoint_lookups: int
    checkpoint_hits: int
    checkpoint_captures: int
    checkpoint_replacements: int
    checkpoint_probes: int
    commitment: str


@dataclass(frozen=True)
class RegenerationOperationCounts:
    recursive_calls: int
    replay_iterations: int
    memo_probes: int
    checkpoint_probes: int
    total: int


@dataclass(frozen=True)
class PhysicalMemoryAccounting:
    total_budget_bytes: int
    fixed_state_reserve_bytes: int
    native_stack_frame_allowance_bytes: int
    native_stack_depth_capacity: int
    native_stack_reserve_bytes: int
    allocator_allowance_bytes: int
    arena_allocation_bytes: int
    logical_frame_reserve_bytes: int
    rolling_transcript_state_bytes: int
    transcript_growth_bytes: int
    accounted_bytes: int


@dataclass(frozen=True)
class IterativeMemoryAccounting:
    total_budget_bytes: int
    fixed_state_reserve_bytes: int
    allocator_allowance_bytes: int
    arena_allocation_bytes: int
    explicit_frame_bytes: int
    explicit_frame_capacity: int
    explicit_work_stack_bytes_inside_arena: int
    native_recursion_bytes: int
    rolling_transcript_state_bytes: int
    transcript_growth_bytes: int
    accounted_bytes: int


@dataclass(frozen=True)
class CheckpointRegenerationResult:
    status: str
    layout: CheckpointLayout
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
    checkpoint_lookups: int
    checkpoint_hits: int
    checkpoint_captures: int
    checkpoint_replacements: int
    checkpoint_probes: int
    first_reconstruction: CheckpointBoundary | None
    last_reconstruction: CheckpointBoundary | None
    exhaustion: RepeatedRecursiveExhaustion | None
    transcript_commitment: str
    execution_result: ExecutionResult | None
    operation_limit: int | None = None
    operation_counts: RegenerationOperationCounts | None = None
    physical_memory_accounting: PhysicalMemoryAccounting | None = None
    iterative_memory_accounting: IterativeMemoryAccounting | None = None
    hierarchical_checkpoint_levels: list[dict[str, int]] | None = None

    def to_dict(self) -> dict[str, object]:
        document = asdict(self)
        document["execution_result"] = (
            None if self.execution_result is None else self.execution_result.to_dict()
        )
        if self.operation_limit is None:
            document.pop("operation_limit")
            document.pop("operation_counts")
        if self.physical_memory_accounting is None:
            document.pop("physical_memory_accounting")
        if self.iterative_memory_accounting is None:
            document.pop("iterative_memory_accounting")
        if self.hierarchical_checkpoint_levels is None:
            document.pop("hierarchical_checkpoint_levels")
        return document


class _CheckpointRegenerator(_RecursiveRegenerator):
    def __init__(
        self,
        owner: _RecursiveArena,
        context: EpochContext,
        header_digest: bytes,
        nonce_bytes: bytes,
        work_limit: int,
        checkpoint_capacity: int,
        checkpoint_stride: int,
        operation_limit: int | None = None,
    ) -> None:
        super().__init__(
            owner, context, header_digest, nonce_bytes, work_limit, operation_limit
        )
        self.checkpoint_capacity = checkpoint_capacity
        self.checkpoint_stride = checkpoint_stride
        self.checkpoint_offset = owner.memo_offset + owner.layout.memo_bytes
        self.checkpoint_lookups = self.checkpoint_hits = 0
        self.checkpoint_captures = self.checkpoint_replacements = 0
        self.checkpoint_probes = 0
        for slot in range(checkpoint_capacity):
            struct.pack_into(
                "<I", owner.arena, self.checkpoint_offset + slot * CHECKPOINT_ENTRY_BYTES,
                EMPTY_CHECKPOINT_STOP,
            )

    def _checkpoint_find(
        self, stop: int, target_word: int, depth: int
    ) -> tuple[int, list[int], int] | None:
        self.checkpoint_lookups += 1
        selected_stop = -1
        selected_offset = 0
        for slot in range(self.checkpoint_capacity):
            self._charge_operation(stop, target_word, depth)
            self.checkpoint_probes += 1
            offset = self.checkpoint_offset + slot * CHECKPOINT_ENTRY_BYTES
            stored_stop = struct.unpack_from("<I", self.owner.arena, offset)[0]
            if stored_stop != EMPTY_CHECKPOINT_STOP and selected_stop < stored_stop < stop:
                selected_stop = stored_stop
                selected_offset = offset
        if selected_stop < 0:
            return None
        self.checkpoint_hits += 1
        state = struct.unpack_from("<9Q", self.owner.arena, selected_offset + 8)
        return selected_stop, list(state[:8]), state[8]

    def _checkpoint_put(self, stop: int, registers: list[int], accumulator: int) -> None:
        if stop == 0 or stop % self.checkpoint_stride:
            return
        slot = (stop // self.checkpoint_stride) % self.checkpoint_capacity
        offset = self.checkpoint_offset + slot * CHECKPOINT_ENTRY_BYTES
        stored_stop = struct.unpack_from("<I", self.owner.arena, offset)[0]
        if stored_stop != EMPTY_CHECKPOINT_STOP and stored_stop != stop:
            self.checkpoint_replacements += 1
        struct.pack_into(
            "<I4x9Q", self.owner.arena, offset, stop, *registers, accumulator & MASK64
        )
        self.checkpoint_captures += 1

    def value_at(self, target_word: int, stop: int, depth: int = 1) -> int:
        self._charge_operation(stop, target_word, depth)
        self.calls += 1
        if stop == 0:
            self.completed_values += 1
            return 0
        self.maximum_depth = max(self.maximum_depth, depth)
        if depth > self.owner.layout.frame_capacity:
            raise _RegenerationExhausted("frame_capacity", stop, target_word, depth)
        cached = self._memo_get(stop, target_word, depth)
        if cached is not None:
            return cached

        checkpoint = self._checkpoint_find(stop, target_word, depth)
        if checkpoint is None:
            start = 0
            registers, accumulator = _initial_machine_state(
                self.context, self.header_digest, self.nonce_bytes
            )
            target_value = 0
        else:
            start, registers, accumulator = checkpoint
            target_value = self.value_at(target_word, start, depth + 1)

        word_count = self.owner.word_count
        for iteration in range(start, stop):
            if self.iterations >= self.work_limit:
                raise _RegenerationExhausted("work_limit", stop, target_word, depth)
            self._charge_operation(stop, target_word, depth)
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
            self._checkpoint_put(iteration + 1, registers, accumulator)
        self._memo_put(stop, target_word, target_value, depth)
        self.completed_values += 1
        return target_value


class _TargetCheckpointRegenerator(_RecursiveRegenerator):
    """Checkpoint machine state together with one exact target-word value."""

    def __init__(
        self,
        owner: _RecursiveArena,
        context: EpochContext,
        header_digest: bytes,
        nonce_bytes: bytes,
        work_limit: int,
        checkpoint_capacity: int,
        checkpoint_stride: int,
        operation_limit: int | None = None,
    ) -> None:
        super().__init__(
            owner, context, header_digest, nonce_bytes, work_limit, operation_limit
        )
        self.checkpoint_capacity = checkpoint_capacity
        self.checkpoint_stride = checkpoint_stride
        self.checkpoint_offset = owner.memo_offset + owner.layout.memo_bytes
        self.checkpoint_lookups = self.checkpoint_hits = 0
        self.checkpoint_captures = self.checkpoint_replacements = 0
        self.checkpoint_probes = 0
        for slot in range(checkpoint_capacity):
            struct.pack_into(
                "<I", owner.arena,
                self.checkpoint_offset + slot * TARGET_CHECKPOINT_ENTRY_BYTES,
                EMPTY_CHECKPOINT_STOP,
            )

    def _checkpoint_find(
        self, target_word: int, stop: int, depth: int
    ) -> tuple[int, int, list[int], int] | None:
        self.checkpoint_lookups += 1
        self._charge_operation(stop, target_word, depth)
        self.checkpoint_probes += 1
        slot = target_word % self.checkpoint_capacity
        offset = self.checkpoint_offset + slot * TARGET_CHECKPOINT_ENTRY_BYTES
        stored_stop, stored_word = struct.unpack_from("<II", self.owner.arena, offset)
        if (
            stored_stop == EMPTY_CHECKPOINT_STOP
            or stored_word != target_word
            or stored_stop >= stop
        ):
            return None
        self.checkpoint_hits += 1
        values = struct.unpack_from("<10Q", self.owner.arena, offset + 8)
        return stored_stop, values[0], list(values[1:9]), values[9]

    def _checkpoint_put(
        self,
        target_word: int,
        target_value: int,
        stop: int,
        registers: list[int],
        accumulator: int,
    ) -> None:
        if stop == 0 or stop % self.checkpoint_stride:
            return
        slot = target_word % self.checkpoint_capacity
        offset = self.checkpoint_offset + slot * TARGET_CHECKPOINT_ENTRY_BYTES
        stored_stop, stored_word = struct.unpack_from("<II", self.owner.arena, offset)
        if (
            stored_stop != EMPTY_CHECKPOINT_STOP
            and (stored_stop != stop or stored_word != target_word)
        ):
            self.checkpoint_replacements += 1
        struct.pack_into(
            "<II10Q", self.owner.arena, offset, stop, target_word,
            target_value & MASK64, *registers, accumulator & MASK64,
        )
        self.checkpoint_captures += 1

    def value_at(self, target_word: int, stop: int, depth: int = 1) -> int:
        self._charge_operation(stop, target_word, depth)
        self.calls += 1
        if stop == 0:
            self.completed_values += 1
            return 0
        self.maximum_depth = max(self.maximum_depth, depth)
        if depth > self.owner.layout.frame_capacity:
            raise _RegenerationExhausted("frame_capacity", stop, target_word, depth)
        cached = self._memo_get(stop, target_word, depth)
        if cached is not None:
            return cached

        checkpoint = self._checkpoint_find(target_word, stop, depth)
        if checkpoint is None:
            start = 0
            registers, accumulator = _initial_machine_state(
                self.context, self.header_digest, self.nonce_bytes
            )
            target_value = 0
        else:
            start, target_value, registers, accumulator = checkpoint

        word_count = self.owner.word_count
        for iteration in range(start, stop):
            if self.iterations >= self.work_limit:
                raise _RegenerationExhausted("work_limit", stop, target_word, depth)
            self._charge_operation(stop, target_word, depth)
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
            mixed_value = _execute_operation(
                entry.opcode, x, y, first_scratch, second_scratch,
                dataset_word, entry.immediate,
            )
            accumulator = _u64(
                _rol64(
                    accumulator ^ mixed_value ^ dataset_word,
                    first_scratch ^ second_scratch ^ entry.immediate,
                )
                + first_scratch + entry.immediate + iteration
            )
            first_write = mixed_value ^ accumulator ^ second_scratch
            second_write = second_scratch ^ _rol64(
                _u64(mixed_value + accumulator), dataset_word
            )
            if word_index == target_word:
                target_value = first_write & MASK64
            if second_word == target_word:
                target_value = second_write & MASK64
            registers[lane] = _u64(mixed_value + accumulator + first_scratch)
            neighbor = (lane + 2) & 7
            registers[neighbor] = _u64(
                registers[neighbor]
                ^ _rol64(_u64(dataset_word + first_scratch), second_scratch)
            )
            self._checkpoint_put(
                target_word, target_value, iteration + 1, registers, accumulator
            )
        self._memo_put(stop, target_word, target_value, depth)
        self.completed_values += 1
        return target_value


class _DependencyBundleRegenerator(_RecursiveRegenerator):
    """Checkpoint machine state with exact values from one direct dependency step."""

    def __init__(
        self,
        owner: _RecursiveArena,
        context: EpochContext,
        header_digest: bytes,
        nonce_bytes: bytes,
        work_limit: int,
        checkpoint_capacity: int,
        checkpoint_stride: int,
        dependency_bundle_width: int,
        operation_limit: int | None = None,
    ) -> None:
        super().__init__(
            owner, context, header_digest, nonce_bytes, work_limit, operation_limit
        )
        self.checkpoint_capacity = checkpoint_capacity
        self.checkpoint_stride = checkpoint_stride
        self.dependency_bundle_width = dependency_bundle_width
        (
            self.bundle_value_offset,
            self.bundle_state_offset,
            self.checkpoint_entry_bytes,
        ) = _dependency_bundle_offsets(dependency_bundle_width)
        self.checkpoint_offset = owner.memo_offset + owner.layout.memo_bytes
        self.checkpoint_lookups = self.checkpoint_hits = 0
        self.checkpoint_captures = self.checkpoint_replacements = 0
        self.checkpoint_probes = 0
        for slot in range(checkpoint_capacity):
            struct.pack_into(
                "<I", self.owner.arena,
                self.checkpoint_offset + slot * self.checkpoint_entry_bytes,
                EMPTY_CHECKPOINT_STOP,
            )

    def _checkpoint_find(
        self, target_word: int, stop: int, depth: int
    ) -> tuple[int, int, list[int], int] | None:
        self.checkpoint_lookups += 1
        selected: tuple[int, int, list[int], int] | None = None
        for slot in range(self.checkpoint_capacity):
            self._charge_operation(stop, target_word, depth)
            self.checkpoint_probes += 1
            offset = self.checkpoint_offset + slot * self.checkpoint_entry_bytes
            stored_stop = struct.unpack_from("<I", self.owner.arena, offset)[0]
            if (
                stored_stop == EMPTY_CHECKPOINT_STOP
                or stored_stop >= stop
                or (selected is not None and stored_stop <= selected[0])
            ):
                continue
            words = struct.unpack_from(
                f"<{self.dependency_bundle_width}H", self.owner.arena, offset + 4
            )
            try:
                value_index = words.index(target_word)
            except ValueError:
                continue
            target_value = struct.unpack_from(
                "<Q", self.owner.arena,
                offset + self.bundle_value_offset + value_index * 8,
            )[0]
            state = struct.unpack_from(
                "<9Q", self.owner.arena, offset + self.bundle_state_offset
            )
            selected = stored_stop, target_value, list(state[:8]), state[8]
        if selected is not None:
            self.checkpoint_hits += 1
        return selected

    def _checkpoint_put(
        self,
        anchor_word: int,
        stop: int,
        candidates: list[tuple[int, int]],
        registers: list[int],
        accumulator: int,
    ) -> None:
        if stop == 0 or stop % self.checkpoint_stride:
            return
        words: list[int] = []
        values: list[int] = []
        for word, value in candidates:
            if word in words:
                values[words.index(word)] = value & MASK64
                continue
            if len(words) == self.dependency_bundle_width:
                break
            words.append(word)
            values.append(value & MASK64)
        while len(words) < self.dependency_bundle_width:
            words.append(EMPTY_BUNDLE_WORD)
            values.append(0)

        slot = anchor_word % self.checkpoint_capacity
        offset = self.checkpoint_offset + slot * self.checkpoint_entry_bytes
        stored_stop = struct.unpack_from("<I", self.owner.arena, offset)[0]
        stored_anchor = struct.unpack_from("<H", self.owner.arena, offset + 4)[0]
        if (
            stored_stop != EMPTY_CHECKPOINT_STOP
            and (stored_stop != stop or stored_anchor != anchor_word)
        ):
            self.checkpoint_replacements += 1
        struct.pack_into("<I", self.owner.arena, offset, stop)
        struct.pack_into(
            f"<{self.dependency_bundle_width}H", self.owner.arena, offset + 4, *words
        )
        padding_start = offset + 4 + self.dependency_bundle_width * 2
        padding_end = offset + self.bundle_value_offset
        self.owner.arena[padding_start:padding_end] = b"\x00" * (padding_end - padding_start)
        struct.pack_into(
            f"<{self.dependency_bundle_width}Q", self.owner.arena,
            offset + self.bundle_value_offset, *values,
        )
        struct.pack_into(
            "<9Q", self.owner.arena, offset + self.bundle_state_offset,
            *registers, accumulator & MASK64,
        )
        self.checkpoint_captures += 1

    @staticmethod
    def _value_after_writes(
        word: int,
        value: int,
        first_word: int,
        first_write: int,
        second_word: int,
        second_write: int,
    ) -> int:
        if word == first_word:
            value = first_write
        if word == second_word:
            value = second_write
        return value & MASK64

    def value_at(self, target_word: int, stop: int, depth: int = 1) -> int:
        self._charge_operation(stop, target_word, depth)
        self.calls += 1
        if stop == 0:
            self.completed_values += 1
            return 0
        self.maximum_depth = max(self.maximum_depth, depth)
        if depth > self.owner.layout.frame_capacity:
            raise _RegenerationExhausted("frame_capacity", stop, target_word, depth)
        cached = self._memo_get(stop, target_word, depth)
        if cached is not None:
            return cached

        checkpoint = self._checkpoint_find(target_word, stop, depth)
        if checkpoint is None:
            start = 0
            registers, accumulator = _initial_machine_state(
                self.context, self.header_digest, self.nonce_bytes
            )
            target_value = 0
        else:
            start, target_value, registers, accumulator = checkpoint

        word_count = self.owner.word_count
        for iteration in range(start, stop):
            if self.iterations >= self.work_limit:
                raise _RegenerationExhausted("work_limit", stop, target_word, depth)
            self._charge_operation(stop, target_word, depth)
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
            mixed_value = _execute_operation(
                entry.opcode, x, y, first_scratch, second_scratch,
                dataset_word, entry.immediate,
            )
            accumulator = _u64(
                _rol64(
                    accumulator ^ mixed_value ^ dataset_word,
                    first_scratch ^ second_scratch ^ entry.immediate,
                )
                + first_scratch + entry.immediate + iteration
            )
            first_write = (mixed_value ^ accumulator ^ second_scratch) & MASK64
            second_write = (
                second_scratch
                ^ _rol64(_u64(mixed_value + accumulator), dataset_word)
            ) & MASK64
            if word_index == target_word:
                target_value = first_write
            if second_word == target_word:
                target_value = second_write
            registers[lane] = _u64(mixed_value + accumulator + first_scratch)
            neighbor = (lane + 2) & 7
            registers[neighbor] = _u64(
                registers[neighbor]
                ^ _rol64(_u64(dataset_word + first_scratch), second_scratch)
            )
            self._checkpoint_put(
                target_word,
                iteration + 1,
                [
                    (target_word, target_value),
                    (
                        first_word,
                        self._value_after_writes(
                            first_word, first_scratch, word_index, first_write,
                            second_word, second_write,
                        ),
                    ),
                    (second_word, second_write),
                    (
                        word_index,
                        second_write if word_index == second_word else first_write,
                    ),
                ],
                registers,
                accumulator,
            )
        self._memo_put(stop, target_word, target_value, depth)
        self.completed_values += 1
        return target_value


class _IterativeDependencyBundleRegenerator(_DependencyBundleRegenerator):
    """Regenerate values with an arena-resident stack and no recursive calls."""

    _ENTER = 0
    _NEED_FIRST = 1
    _HAVE_FIRST = 2
    _HAVE_SECOND = 3

    def _frame_offset(self, slot: int) -> int:
        return self.owner.frame_offset + slot * FRAME_BYTES

    def _write_frame(
        self,
        slot: int,
        target_word: int,
        stop: int,
        iteration: int,
        depth: int,
        phase: int,
        target_value: int,
        registers: list[int],
        accumulator: int,
        first_scratch: int,
    ) -> None:
        ITERATIVE_FRAME_STRUCT.pack_into(
            self.owner.arena,
            self._frame_offset(slot),
            target_word,
            stop,
            iteration,
            depth,
            phase,
            0,
            target_value & MASK64,
            *registers,
            accumulator & MASK64,
            first_scratch & MASK64,
        )

    def _read_frame(
        self, slot: int
    ) -> tuple[int, int, int, int, int, int, list[int], int, int]:
        fields = ITERATIVE_FRAME_STRUCT.unpack_from(
            self.owner.arena, self._frame_offset(slot)
        )
        return (
            fields[0],
            fields[1],
            fields[2],
            fields[3],
            fields[4],
            fields[6],
            list(fields[7:15]),
            fields[15],
            fields[16],
        )

    def _push_enter(self, slot: int, target_word: int, stop: int, depth: int) -> bool:
        if stop == 0:
            self._charge_operation(stop, target_word, depth)
            self.calls += 1
            self.completed_values += 1
            return False
        if slot >= self.owner.layout.frame_capacity:
            self._charge_operation(stop, target_word, depth)
            self.calls += 1
            self.maximum_depth = max(self.maximum_depth, depth)
            raise _RegenerationExhausted("frame_capacity", stop, target_word, depth)
        self._write_frame(
            slot, target_word, stop, 0, depth, self._ENTER, 0, [0] * 8, 0, 0
        )
        return True

    def value_at(self, target_word: int, stop: int, depth: int = 1) -> int:
        """Evaluate the logical call graph using packed iterative frames."""

        stack_size = 1
        if not self._push_enter(0, target_word, stop, depth):
            return 0
        returned_value = 0
        while stack_size:
            slot = stack_size - 1
            (
                frame_target,
                frame_stop,
                iteration,
                frame_depth,
                phase,
                target_value,
                registers,
                accumulator,
                first_scratch,
            ) = self._read_frame(slot)

            if phase == self._ENTER:
                self._charge_operation(frame_stop, frame_target, frame_depth)
                self.calls += 1
                if frame_stop == 0:
                    self.completed_values += 1
                    returned_value = 0
                    stack_size -= 1
                    continue
                self.maximum_depth = max(self.maximum_depth, frame_depth)
                if frame_depth > self.owner.layout.frame_capacity:
                    raise _RegenerationExhausted(
                        "frame_capacity", frame_stop, frame_target, frame_depth
                    )
                cached = self._memo_get(frame_stop, frame_target, frame_depth)
                if cached is not None:
                    returned_value = cached
                    stack_size -= 1
                    continue
                checkpoint = self._checkpoint_find(
                    frame_target, frame_stop, frame_depth
                )
                if checkpoint is None:
                    iteration = 0
                    registers, accumulator = _initial_machine_state(
                        self.context, self.header_digest, self.nonce_bytes
                    )
                    target_value = 0
                else:
                    iteration, target_value, registers, accumulator = checkpoint
                self._write_frame(
                    slot,
                    frame_target,
                    frame_stop,
                    iteration,
                    frame_depth,
                    self._NEED_FIRST,
                    target_value,
                    registers,
                    accumulator,
                    0,
                )
                continue

            if phase == self._NEED_FIRST:
                if iteration >= frame_stop:
                    self._memo_put(
                        frame_stop, frame_target, target_value, frame_depth
                    )
                    self.completed_values += 1
                    returned_value = target_value
                    stack_size -= 1
                    continue
                if self.iterations >= self.work_limit:
                    raise _RegenerationExhausted(
                        "work_limit", frame_stop, frame_target, frame_depth
                    )
                self._charge_operation(frame_stop, frame_target, frame_depth)
                self.iterations += 1
                lane = iteration & 7
                entry = self.context.schedule[iteration & 63]
                first_selector = (
                    registers[lane]
                    ^ _rol64(registers[(lane + 1) & 7], iteration)
                    ^ accumulator
                    ^ entry.immediate
                )
                first_word = first_selector & (self.owner.word_count - 1)
                self._write_frame(
                    slot,
                    frame_target,
                    frame_stop,
                    iteration,
                    frame_depth,
                    self._HAVE_FIRST,
                    target_value,
                    registers,
                    accumulator,
                    0,
                )
                if self._push_enter(
                    stack_size, first_word, iteration, frame_depth + 1
                ):
                    stack_size += 1
                else:
                    returned_value = 0
                continue

            lane = iteration & 7
            pass_index = iteration // self.owner.word_count
            entry = self.context.schedule[iteration & 63]
            x = registers[lane]
            y = registers[(lane + 1) & 7]
            z = registers[(lane + 3) & 7]
            first_selector = x ^ _rol64(y, iteration) ^ accumulator ^ entry.immediate
            first_word = first_selector & (self.owner.word_count - 1)

            if phase == self._HAVE_FIRST:
                first_scratch = returned_value
                dataset_selector = (
                    first_scratch
                    ^ z
                    ^ _rol64(accumulator, lane + pass_index)
                    ^ iteration
                )
                dataset_word = _read_u64(self.context.dataset, dataset_selector)
                second_selector = (
                    dataset_word
                    ^ registers[(lane + 5) & 7]
                    ^ _rol64(_u64(first_scratch + accumulator), entry.immediate)
                )
                second_word = second_selector & (self.owner.word_count - 1)
                self._write_frame(
                    slot,
                    frame_target,
                    frame_stop,
                    iteration,
                    frame_depth,
                    self._HAVE_SECOND,
                    target_value,
                    registers,
                    accumulator,
                    first_scratch,
                )
                if self._push_enter(
                    stack_size, second_word, iteration, frame_depth + 1
                ):
                    stack_size += 1
                else:
                    returned_value = 0
                continue

            if phase != self._HAVE_SECOND:
                raise AssertionError("invalid iterative work-stack phase")
            second_scratch = returned_value
            dataset_selector = (
                first_scratch
                ^ z
                ^ _rol64(accumulator, lane + pass_index)
                ^ iteration
            )
            dataset_word = _read_u64(self.context.dataset, dataset_selector)
            second_selector = (
                dataset_word
                ^ registers[(lane + 5) & 7]
                ^ _rol64(_u64(first_scratch + accumulator), entry.immediate)
            )
            second_word = second_selector & (self.owner.word_count - 1)
            mixed_value = _execute_operation(
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
                    accumulator ^ mixed_value ^ dataset_word,
                    first_scratch ^ second_scratch ^ entry.immediate,
                )
                + first_scratch
                + entry.immediate
                + iteration
            )
            first_write = (mixed_value ^ accumulator ^ second_scratch) & MASK64
            second_write = (
                second_scratch
                ^ _rol64(_u64(mixed_value + accumulator), dataset_word)
            ) & MASK64
            word_index = iteration & (self.owner.word_count - 1)
            if word_index == frame_target:
                target_value = first_write
            if second_word == frame_target:
                target_value = second_write
            registers[lane] = _u64(mixed_value + accumulator + first_scratch)
            neighbor = (lane + 2) & 7
            registers[neighbor] = _u64(
                registers[neighbor]
                ^ _rol64(_u64(dataset_word + first_scratch), second_scratch)
            )
            self._checkpoint_put(
                frame_target,
                iteration + 1,
                [
                    (frame_target, target_value),
                    (
                        first_word,
                        self._value_after_writes(
                            first_word,
                            first_scratch,
                            word_index,
                            first_write,
                            second_word,
                            second_write,
                        ),
                    ),
                    (second_word, second_write),
                    (
                        word_index,
                        second_write if word_index == second_word else first_write,
                    ),
                ],
                registers,
                accumulator,
            )
            self._write_frame(
                slot,
                frame_target,
                frame_stop,
                iteration + 1,
                frame_depth,
                self._NEED_FIRST,
                target_value,
                registers,
                accumulator,
                0,
            )
        return returned_value


class _HierarchicalCheckpointLadderRegenerator(
    _IterativeDependencyBundleRegenerator
):
    """Use one directly addressed target checkpoint at each frozen time scale."""

    def _checkpoint_find(
        self, target_word: int, stop: int, depth: int
    ) -> tuple[int, int, list[int], int] | None:
        self.checkpoint_lookups += 1
        selected: tuple[int, int, list[int], int] | None = None
        for _level, _stride, capacity, base_slot in HIERARCHICAL_CHECKPOINT_LEVELS:
            self._charge_operation(stop, target_word, depth)
            self.checkpoint_probes += 1
            slot = base_slot + target_word % capacity
            offset = self.checkpoint_offset + slot * self.checkpoint_entry_bytes
            stored_stop = struct.unpack_from("<I", self.owner.arena, offset)[0]
            if (
                stored_stop == EMPTY_CHECKPOINT_STOP
                or stored_stop >= stop
                or (selected is not None and stored_stop <= selected[0])
            ):
                continue
            words = struct.unpack_from(
                f"<{self.dependency_bundle_width}H", self.owner.arena, offset + 4
            )
            try:
                value_index = words.index(target_word)
            except ValueError:
                continue
            target_value = struct.unpack_from(
                "<Q",
                self.owner.arena,
                offset + self.bundle_value_offset + value_index * 8,
            )[0]
            state = struct.unpack_from(
                "<9Q", self.owner.arena, offset + self.bundle_state_offset
            )
            selected = stored_stop, target_value, list(state[:8]), state[8]
        if selected is not None:
            self.checkpoint_hits += 1
        return selected

    def _checkpoint_put(
        self,
        anchor_word: int,
        stop: int,
        candidates: list[tuple[int, int]],
        registers: list[int],
        accumulator: int,
    ) -> None:
        if stop == 0:
            return
        words: list[int] = []
        values: list[int] = []
        for word, value in candidates:
            if word in words:
                values[words.index(word)] = value & MASK64
                continue
            if len(words) == self.dependency_bundle_width:
                break
            words.append(word)
            values.append(value & MASK64)
        while len(words) < self.dependency_bundle_width:
            words.append(EMPTY_BUNDLE_WORD)
            values.append(0)

        for _level, stride, capacity, base_slot in HIERARCHICAL_CHECKPOINT_LEVELS:
            if stop % stride:
                continue
            slot = base_slot + anchor_word % capacity
            offset = self.checkpoint_offset + slot * self.checkpoint_entry_bytes
            stored_stop = struct.unpack_from("<I", self.owner.arena, offset)[0]
            stored_anchor = struct.unpack_from("<H", self.owner.arena, offset + 4)[0]
            if (
                stored_stop != EMPTY_CHECKPOINT_STOP
                and (stored_stop != stop or stored_anchor != anchor_word)
            ):
                self.checkpoint_replacements += 1
            struct.pack_into("<I", self.owner.arena, offset, stop)
            struct.pack_into(
                f"<{self.dependency_bundle_width}H",
                self.owner.arena,
                offset + 4,
                *words,
            )
            padding_start = offset + 4 + self.dependency_bundle_width * 2
            padding_end = offset + self.bundle_value_offset
            self.owner.arena[padding_start:padding_end] = b"\x00" * (
                padding_end - padding_start
            )
            struct.pack_into(
                f"<{self.dependency_bundle_width}Q",
                self.owner.arena,
                offset + self.bundle_value_offset,
                *values,
            )
            struct.pack_into(
                "<9Q",
                self.owner.arena,
                offset + self.bundle_state_offset,
                *registers,
                accumulator & MASK64,
            )
            self.checkpoint_captures += 1


def reconstruct_repeatedly_with_checkpoints(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
    work_limit: int = DEFAULT_WORK_LIMIT,
    primary_numerator: int = 1,
    primary_denominator: int = 32,
    checkpoint_capacity: int = DEFAULT_CHECKPOINT_CAPACITY,
    checkpoint_stride: int = DEFAULT_CHECKPOINT_STRIDE,
    _target_aware: bool = False,
    _dependency_bundle_width: int = 1,
    _operation_limit: int | None = None,
    _external_reserve_bytes: int = 0,
    _rolling_transcript: bool = False,
    _iterative_work_stack: bool = False,
    _hierarchical_checkpoint_ladder: bool = False,
) -> CheckpointRegenerationResult:
    """Recover successive misses using exact reusable machine-state checkpoints."""

    _validate_seed(context.seed)
    context.params.validate()
    _validate_header(header)
    if not 0 <= nonce <= MASK64:
        raise ValueError("nonce must be an unsigned 64-bit integer")
    if work_limit <= 0:
        raise ValueError("work_limit must be positive")
    if _operation_limit is not None and _operation_limit <= 0:
        raise ValueError("operation_limit must be positive")
    if checkpoint_capacity <= 0:
        raise ValueError("checkpoint_capacity must be positive")
    if checkpoint_stride <= 0:
        raise ValueError("checkpoint_stride must be positive")
    dependency_bundles = _dependency_bundle_width > 1
    if dependency_bundles and not _target_aware:
        raise ValueError("dependency bundles require target-aware checkpoints")
    if _iterative_work_stack and not dependency_bundles:
        raise ValueError("iterative work stack requires dependency bundles")
    if _hierarchical_checkpoint_ladder and not _iterative_work_stack:
        raise ValueError("hierarchical checkpoint ladder requires iterative work stack")
    if (
        _hierarchical_checkpoint_ladder
        and checkpoint_capacity != HIERARCHICAL_CHECKPOINT_CAPACITY
    ):
        raise ValueError("hierarchical checkpoint capacity must match frozen levels")
    checkpoint_entry_bytes = (
        _dependency_bundle_offsets(_dependency_bundle_width)[2]
        if dependency_bundles else
        TARGET_CHECKPOINT_ENTRY_BYTES if _target_aware else CHECKPOINT_ENTRY_BYTES
    )
    checkpoint_bytes = checkpoint_capacity * checkpoint_entry_bytes
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
        checkpoint_bytes,
        _external_reserve_bytes,
    )
    base = arena.layout
    layout = CheckpointLayout(
        base.budget_bytes, base.fixed_state_reserve_bytes, base.arena_bytes,
        base.write_bitmap_bytes, base.primary_cache_capacity, base.primary_cache_bytes,
        base.frame_bytes, base.frame_capacity, base.frame_reserve_bytes,
        checkpoint_entry_bytes, checkpoint_capacity, checkpoint_bytes, checkpoint_stride,
        base.memo_entry_bytes, base.memo_capacity, base.memo_bytes,
        base.unused_arena_bytes - checkpoint_bytes, base.admitted_bytes,
    )
    if dependency_bundles:
        regenerator_class = (
            _HierarchicalCheckpointLadderRegenerator
            if _hierarchical_checkpoint_ladder else
            _IterativeDependencyBundleRegenerator
            if _iterative_work_stack else
            _DependencyBundleRegenerator
        )
        regenerator = regenerator_class(
            arena, context, header_digest, nonce_bytes, work_limit,
            checkpoint_capacity, checkpoint_stride, _dependency_bundle_width,
            _operation_limit,
        )
    else:
        regenerator_class = (
            _TargetCheckpointRegenerator if _target_aware else _CheckpointRegenerator
        )
        regenerator = regenerator_class(
            arena, context, header_digest, nonce_bytes, work_limit,
            checkpoint_capacity, checkpoint_stride, _operation_limit,
        )
    completed = attempts = successful = 0
    first: CheckpointBoundary | None = None
    last: CheckpointBoundary | None = None
    exhaustion: RepeatedRecursiveExhaustion | None = None
    domain = (
        DOMAIN_HIERARCHICAL_CHECKPOINT_LADDER_REGENERATION
        if dependency_bundles and _hierarchical_checkpoint_ladder else
        DOMAIN_ITERATIVE_WORK_STACK_DEPENDENCY_BUNDLE_REGENERATION
        if dependency_bundles and _iterative_work_stack else
        DOMAIN_PHYSICALLY_ACCOUNTED_DEPENDENCY_BUNDLE_REGENERATION
        if dependency_bundles and _rolling_transcript else
        DOMAIN_OPERATION_BOUNDED_DEPENDENCY_BUNDLE_REGENERATION
        if dependency_bundles and _operation_limit is not None else
        DOMAIN_DEPENDENCY_BUNDLE_REGENERATION if dependency_bundles else
        DOMAIN_TARGET_CHECKPOINT_REGENERATION if _target_aware else
        DOMAIN_CHECKPOINT_REGENERATION
    )
    transcript = hashlib.sha3_384(domain)
    rolling_transcript_digest = transcript.digest() if _rolling_transcript else None

    def boundary_for(miss: _MaterializedMiss, value: int, commitment: str) -> CheckpointBoundary:
        return CheckpointBoundary(
            miss.consumer, miss.slot, miss.word, value, regenerator.calls,
            regenerator.cache_hits, regenerator.completed_values, regenerator.iterations,
            regenerator.maximum_depth, regenerator.memo_peak_entries,
            regenerator.memo_evictions, regenerator.memo_probes,
            regenerator.memo_shifted_bytes,
            regenerator.checkpoint_lookups, regenerator.checkpoint_hits,
            regenerator.checkpoint_captures, regenerator.checkpoint_replacements,
            regenerator.checkpoint_probes, commitment,
        )

    def recover(miss: _MaterializedMiss) -> bool:
        nonlocal attempts, successful, first, last, exhaustion
        nonlocal rolling_transcript_digest
        attempts += 1
        state_commitment = _boundary_commitment(
            domain, context, header_digest, nonce_bytes,
            registers, accumulator, miss.consumer, miss.slot, miss.word,
        )
        try:
            value = regenerator.value_at(miss.word, miss.consumer)
        except _RegenerationExhausted as error:
            exhaustion = RepeatedRecursiveExhaustion(
                error.reason, miss.consumer, miss.slot, miss.word, error.stop,
                error.depth, regenerator.iterations, state_commitment,
            )
            return False
        commitment = _boundary_commitment(
            domain, context, header_digest, nonce_bytes,
            registers, accumulator, miss.consumer, miss.slot, miss.word, value,
        )
        boundary = boundary_for(miss, value, commitment)
        if rolling_transcript_digest is None:
            transcript.update(bytes.fromhex(commitment))
        else:
            rolling_transcript_digest = hashlib.sha3_384(
                rolling_transcript_digest + bytes.fromhex(commitment)
            ).digest()
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
                + 0x9E3779B97F4A7C15 + sample_index
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

    status = (
        "refused_hierarchical_checkpoint_ladder_exhausted"
        if dependency_bundles and _hierarchical_checkpoint_ladder else
        "refused_iterative_work_stack_dependency_bundle_exhausted"
        if dependency_bundles and _iterative_work_stack else
        "refused_physically_accounted_dependency_bundle_exhausted"
        if dependency_bundles and _rolling_transcript else
        "refused_operation_bounded_dependency_bundle_exhausted"
        if dependency_bundles and _operation_limit is not None else
        "refused_dependency_bundle_regeneration_exhausted" if dependency_bundles else
        "refused_target_checkpoint_regeneration_exhausted" if _target_aware else
        "refused_checkpoint_regeneration_exhausted"
    )
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
            digest=digest, registers=tuple(registers),
            schedule_digest=context.schedule_digest,
            dataset_digest=context.dataset_digest,
            memory_commitment=memory_commitment,
        )
        status = "exact_complete"

    return CheckpointRegenerationResult(
        status, layout, primary_numerator, primary_denominator, work_limit,
        completed, arena.canonical_reads, arena.cache_hits, arena.initial_zero_reads,
        arena.materialized_misses, arena.writes, arena.evictions, attempts, successful,
        regenerator.calls, regenerator.cache_hits, regenerator.completed_values,
        regenerator.iterations, regenerator.maximum_depth, regenerator.memo_peak_entries,
        regenerator.memo_evictions, regenerator.memo_probes,
        regenerator.memo_shifted_bytes,
        regenerator.checkpoint_lookups, regenerator.checkpoint_hits,
        regenerator.checkpoint_captures, regenerator.checkpoint_replacements,
        regenerator.checkpoint_probes, first, last, exhaustion,
        (
            rolling_transcript_digest.hex()
            if rolling_transcript_digest is not None else transcript.hexdigest()
        ),
        execution_result,
        _operation_limit,
        (
            RegenerationOperationCounts(
                regenerator.calls,
                regenerator.iterations,
                regenerator.memo_probes,
                regenerator.checkpoint_probes,
                regenerator.total_operations,
            )
            if _operation_limit is not None else None
        ),
        (
            PhysicalMemoryAccounting(
                budget,
                layout.fixed_state_reserve_bytes,
                NATIVE_STACK_FRAME_ALLOWANCE_BYTES,
                NATIVE_STACK_DEPTH_CAPACITY,
                NATIVE_STACK_RESERVE_BYTES,
                ALLOCATOR_ALLOWANCE_BYTES,
                layout.arena_bytes,
                layout.frame_reserve_bytes,
                48,
                0,
                layout.fixed_state_reserve_bytes
                + layout.arena_bytes
                + PHYSICAL_EXTERNAL_RESERVE_BYTES,
            )
            if _rolling_transcript and not _iterative_work_stack else None
        ),
        (
            IterativeMemoryAccounting(
                budget,
                layout.fixed_state_reserve_bytes,
                ALLOCATOR_ALLOWANCE_BYTES,
                layout.arena_bytes,
                layout.frame_bytes,
                layout.frame_capacity,
                layout.frame_reserve_bytes,
                0,
                48,
                0,
                layout.fixed_state_reserve_bytes
                + layout.arena_bytes
                + ITERATIVE_EXTERNAL_RESERVE_BYTES,
            )
            if _iterative_work_stack else None
        ),
        (
            [
                {
                    "level": level,
                    "stride": stride,
                    "capacity": capacity,
                    "base_slot": base_slot,
                }
                for level, stride, capacity, base_slot
                in HIERARCHICAL_CHECKPOINT_LEVELS
            ]
            if _hierarchical_checkpoint_ladder else None
        ),
    )


def reconstruct_repeatedly_with_target_checkpoints(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
    work_limit: int = DEFAULT_WORK_LIMIT,
    primary_numerator: int = 1,
    primary_denominator: int = 128,
    checkpoint_capacity: int = DEFAULT_CHECKPOINT_CAPACITY,
    checkpoint_stride: int = DEFAULT_CHECKPOINT_STRIDE,
) -> CheckpointRegenerationResult:
    """Recover misses using checkpoints bound to one exact target-word value."""

    return reconstruct_repeatedly_with_checkpoints(
        context,
        header,
        nonce,
        budget_bytes=budget_bytes,
        work_limit=work_limit,
        primary_numerator=primary_numerator,
        primary_denominator=primary_denominator,
        checkpoint_capacity=checkpoint_capacity,
        checkpoint_stride=checkpoint_stride,
        _target_aware=True,
    )


def reconstruct_repeatedly_with_dependency_bundles(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
    work_limit: int = DEFAULT_WORK_LIMIT,
    primary_numerator: int = 1,
    primary_denominator: int = 128,
    checkpoint_capacity: int = DEFAULT_DEPENDENCY_BUNDLE_CAPACITY,
    checkpoint_stride: int = DEFAULT_CHECKPOINT_STRIDE,
    dependency_bundle_width: int = DEFAULT_DEPENDENCY_BUNDLE_WIDTH,
) -> CheckpointRegenerationResult:
    """Recover misses using state checkpoints with direct-dependency values."""

    _dependency_bundle_offsets(dependency_bundle_width)
    return reconstruct_repeatedly_with_checkpoints(
        context,
        header,
        nonce,
        budget_bytes=budget_bytes,
        work_limit=work_limit,
        primary_numerator=primary_numerator,
        primary_denominator=primary_denominator,
        checkpoint_capacity=checkpoint_capacity,
        checkpoint_stride=checkpoint_stride,
        _target_aware=True,
        _dependency_bundle_width=dependency_bundle_width,
    )


def reconstruct_repeatedly_with_operation_bounded_dependency_bundles(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
    work_limit: int = DEFAULT_WORK_LIMIT,
    operation_limit: int = DEFAULT_TOTAL_OPERATION_LIMIT,
    primary_numerator: int = 1,
    primary_denominator: int = 128,
    checkpoint_capacity: int = DEFAULT_DEPENDENCY_BUNDLE_CAPACITY,
    checkpoint_stride: int = DEFAULT_CHECKPOINT_STRIDE,
    dependency_bundle_width: int = DEFAULT_DEPENDENCY_BUNDLE_WIDTH,
) -> CheckpointRegenerationResult:
    """Recover bundle-backed misses under one deterministic operation ceiling."""

    _dependency_bundle_offsets(dependency_bundle_width)
    return reconstruct_repeatedly_with_checkpoints(
        context,
        header,
        nonce,
        budget_bytes=budget_bytes,
        work_limit=work_limit,
        primary_numerator=primary_numerator,
        primary_denominator=primary_denominator,
        checkpoint_capacity=checkpoint_capacity,
        checkpoint_stride=checkpoint_stride,
        _target_aware=True,
        _dependency_bundle_width=dependency_bundle_width,
        _operation_limit=operation_limit,
    )


def reconstruct_repeatedly_with_physically_accounted_dependency_bundles(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
    work_limit: int = DEFAULT_WORK_LIMIT,
    operation_limit: int = DEFAULT_TOTAL_OPERATION_LIMIT,
    primary_numerator: int = 1,
    primary_denominator: int = 128,
    checkpoint_capacity: int = DEFAULT_DEPENDENCY_BUNDLE_CAPACITY,
    checkpoint_stride: int = DEFAULT_CHECKPOINT_STRIDE,
    dependency_bundle_width: int = DEFAULT_DEPENDENCY_BUNDLE_WIDTH,
) -> CheckpointRegenerationResult:
    """Run the bounded bundle attack with explicit external-memory reserves."""

    _dependency_bundle_offsets(dependency_bundle_width)
    return reconstruct_repeatedly_with_checkpoints(
        context,
        header,
        nonce,
        budget_bytes=budget_bytes,
        work_limit=work_limit,
        primary_numerator=primary_numerator,
        primary_denominator=primary_denominator,
        checkpoint_capacity=checkpoint_capacity,
        checkpoint_stride=checkpoint_stride,
        _target_aware=True,
        _dependency_bundle_width=dependency_bundle_width,
        _operation_limit=operation_limit,
        _external_reserve_bytes=PHYSICAL_EXTERNAL_RESERVE_BYTES,
        _rolling_transcript=True,
    )


def reconstruct_repeatedly_with_iterative_work_stack(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
    work_limit: int = DEFAULT_WORK_LIMIT,
    operation_limit: int = DEFAULT_TOTAL_OPERATION_LIMIT,
    primary_numerator: int = 1,
    primary_denominator: int = 128,
    checkpoint_capacity: int = DEFAULT_DEPENDENCY_BUNDLE_CAPACITY,
    checkpoint_stride: int = DEFAULT_CHECKPOINT_STRIDE,
    dependency_bundle_width: int = DEFAULT_DEPENDENCY_BUNDLE_WIDTH,
) -> CheckpointRegenerationResult:
    """Run the bounded bundle attack with an arena-resident explicit stack."""

    _dependency_bundle_offsets(dependency_bundle_width)
    return reconstruct_repeatedly_with_checkpoints(
        context,
        header,
        nonce,
        budget_bytes=budget_bytes,
        work_limit=work_limit,
        primary_numerator=primary_numerator,
        primary_denominator=primary_denominator,
        checkpoint_capacity=checkpoint_capacity,
        checkpoint_stride=checkpoint_stride,
        _target_aware=True,
        _dependency_bundle_width=dependency_bundle_width,
        _operation_limit=operation_limit,
        _external_reserve_bytes=ITERATIVE_EXTERNAL_RESERVE_BYTES,
        _rolling_transcript=True,
        _iterative_work_stack=True,
    )


def reconstruct_repeatedly_with_hierarchical_checkpoint_ladder(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
    work_limit: int = DEFAULT_WORK_LIMIT,
    operation_limit: int = DEFAULT_TOTAL_OPERATION_LIMIT,
    primary_numerator: int = 1,
    primary_denominator: int = 128,
    dependency_bundle_width: int = DEFAULT_DEPENDENCY_BUNDLE_WIDTH,
) -> CheckpointRegenerationResult:
    """Run the iterative attacker with the frozen four-level checkpoint ladder."""

    _dependency_bundle_offsets(dependency_bundle_width)
    return reconstruct_repeatedly_with_checkpoints(
        context,
        header,
        nonce,
        budget_bytes=budget_bytes,
        work_limit=work_limit,
        primary_numerator=primary_numerator,
        primary_denominator=primary_denominator,
        checkpoint_capacity=HIERARCHICAL_CHECKPOINT_CAPACITY,
        checkpoint_stride=HIERARCHICAL_CHECKPOINT_LEVELS[0][1],
        _target_aware=True,
        _dependency_bundle_width=dependency_bundle_width,
        _operation_limit=operation_limit,
        _external_reserve_bytes=ITERATIVE_EXTERNAL_RESERVE_BYTES,
        _rolling_transcript=True,
        _iterative_work_stack=True,
        _hierarchical_checkpoint_ladder=True,
    )
