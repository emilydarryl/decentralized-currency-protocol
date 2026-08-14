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
CHECKPOINT_ENTRY_BYTES = 80
TARGET_CHECKPOINT_ENTRY_BYTES = 88
EMPTY_CHECKPOINT_STOP = 0xFFFFFFFF
EMPTY_BUNDLE_WORD = 0xFFFF
DEFAULT_CHECKPOINT_CAPACITY = 4
DEFAULT_CHECKPOINT_STRIDE = 8
DEFAULT_DEPENDENCY_BUNDLE_WIDTH = 4
DEFAULT_DEPENDENCY_BUNDLE_CAPACITY = 12


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

    def to_dict(self) -> dict[str, object]:
        document = asdict(self)
        document["execution_result"] = (
            None if self.execution_result is None else self.execution_result.to_dict()
        )
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
    ) -> None:
        super().__init__(owner, context, header_digest, nonce_bytes, work_limit)
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

    def _checkpoint_find(self, stop: int) -> tuple[int, list[int], int] | None:
        self.checkpoint_lookups += 1
        selected_stop = -1
        selected_offset = 0
        for slot in range(self.checkpoint_capacity):
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

        checkpoint = self._checkpoint_find(stop)
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
        self._memo_put(stop, target_word, target_value)
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
    ) -> None:
        super().__init__(owner, context, header_digest, nonce_bytes, work_limit)
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
        self, target_word: int, stop: int
    ) -> tuple[int, int, list[int], int] | None:
        self.checkpoint_lookups += 1
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

        checkpoint = self._checkpoint_find(target_word, stop)
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
        self._memo_put(stop, target_word, target_value)
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
    ) -> None:
        super().__init__(owner, context, header_digest, nonce_bytes, work_limit)
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
        self, target_word: int, stop: int
    ) -> tuple[int, int, list[int], int] | None:
        self.checkpoint_lookups += 1
        selected: tuple[int, int, list[int], int] | None = None
        for slot in range(self.checkpoint_capacity):
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

        checkpoint = self._checkpoint_find(target_word, stop)
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
        self._memo_put(stop, target_word, target_value)
        self.completed_values += 1
        return target_value


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
) -> CheckpointRegenerationResult:
    """Recover successive misses using exact reusable machine-state checkpoints."""

    _validate_seed(context.seed)
    context.params.validate()
    _validate_header(header)
    if not 0 <= nonce <= MASK64:
        raise ValueError("nonce must be an unsigned 64-bit integer")
    if work_limit <= 0:
        raise ValueError("work_limit must be positive")
    if checkpoint_capacity <= 0:
        raise ValueError("checkpoint_capacity must be positive")
    if checkpoint_stride <= 0:
        raise ValueError("checkpoint_stride must be positive")
    dependency_bundles = _dependency_bundle_width > 1
    if dependency_bundles and not _target_aware:
        raise ValueError("dependency bundles require target-aware checkpoints")
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
        regenerator = _DependencyBundleRegenerator(
            arena, context, header_digest, nonce_bytes, work_limit,
            checkpoint_capacity, checkpoint_stride, _dependency_bundle_width,
        )
    else:
        regenerator_class = (
            _TargetCheckpointRegenerator if _target_aware else _CheckpointRegenerator
        )
        regenerator = regenerator_class(
            arena, context, header_digest, nonce_bytes, work_limit,
            checkpoint_capacity, checkpoint_stride,
        )
    completed = attempts = successful = 0
    first: CheckpointBoundary | None = None
    last: CheckpointBoundary | None = None
    exhaustion: RepeatedRecursiveExhaustion | None = None
    domain = (
        DOMAIN_DEPENDENCY_BUNDLE_REGENERATION if dependency_bundles else
        DOMAIN_TARGET_CHECKPOINT_REGENERATION if _target_aware else
        DOMAIN_CHECKPOINT_REGENERATION
    )
    transcript = hashlib.sha3_384(domain)

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
        transcript.hexdigest(), execution_result,
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
