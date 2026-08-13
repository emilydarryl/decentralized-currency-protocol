# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Offline feasibility screen for full-state time checkpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct

from .bounded_probe import FIXED_STATE_RESERVE_BYTES
from .packed_reconstruction import RANK_CHUNK_WORDS
from .powvm import EpochContext, ExecutionResult, evaluate


FORMAT = "soveroot-pow-v1-time-checkpoint-screen-v0"
DOMAIN_SCREEN = b"Soveroot/PowResearch/TimeCheckpointScreen/v1\x00"
CHECKPOINT_DIVISIONS = 16


@dataclass(frozen=True)
class CheckpointStoreLayout:
    budget_bytes: int
    fixed_state_reserve_bytes: int
    bitmap_bytes_per_nonempty_store: int
    rank_directory_bytes_per_nonempty_store: int
    value_bytes: int
    checkpoint_divisions: int


@dataclass(frozen=True)
class CheckpointCut:
    checkpoint_iteration: int
    snapshot_materialized_values: int
    suffix_distinct_write_values: int
    duplicated_snapshot_delta_values: int
    checkpoint_frontier_values: int
    capture_peak_live_values: int
    resume_peak_live_values: int
    staged_peak_live_values: int
    full_checkpoint_bytes: int
    naive_snapshot_delta_bytes: int
    optimistic_staged_bytes: int
    full_checkpoint_fits: bool
    naive_snapshot_delta_fits: bool
    optimistic_staged_fits: bool


@dataclass(frozen=True)
class TimeCheckpointScreen:
    format: str
    warning: str
    layout: CheckpointStoreLayout
    total_iterations: int
    trace_reads: int
    trace_writes: int
    global_maximum_live_values: int
    cuts: tuple[CheckpointCut, ...]
    any_naive_snapshot_delta_fits: bool
    any_optimistic_staged_fits: bool
    screen_commitment: str
    execution_result: ExecutionResult

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["cuts"] = [asdict(cut) for cut in self.cuts]
        result["execution_result"] = self.execution_result.to_dict()
        return result


class _Recorder:
    def __init__(self, word_count: int) -> None:
        self.word_count = word_count
        self.events: list[tuple[bool, int, bool]] = []
        self.written = bytearray((word_count + 7) // 8)

    def _was_written(self, word: int) -> bool:
        return bool(self.written[word // 8] & (1 << (word & 7)))

    def read(self, _consumer_kind: int, _consumer: int, _slot: int, word: int) -> None:
        self.events.append((False, word, self._was_written(word)))

    def write(self, _iteration: int, _slot: int, word: int) -> None:
        self.events.append((True, word, False))
        self.written[word // 8] |= 1 << (word & 7)


def _store_bytes(value_count: int, bitmap_bytes: int, rank_bytes: int) -> int:
    return 0 if value_count == 0 else bitmap_bytes + rank_bytes + value_count * 8


def _backward_live(
    events: list[tuple[bool, int, bool]],
    start: int,
    stop: int,
    initial_live: set[int] | None = None,
) -> tuple[set[int], int]:
    live = set() if initial_live is None else set(initial_live)
    peak = len(live)
    for index in range(stop - 1, start - 1, -1):
        is_write, word, materialized = events[index]
        if is_write:
            live.discard(word)
        elif materialized:
            live.add(word)
        peak = max(peak, len(live))
    return live, peak


def screen_time_checkpoints(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    budget_bytes: int | None = None,
) -> TimeCheckpointScreen:
    word_count = context.params.scratchpad_bytes // 8
    total_iterations = context.params.passes * word_count
    budget = context.params.scratchpad_bytes // 2 if budget_bytes is None else budget_bytes
    if budget <= 0 or budget > context.params.scratchpad_bytes:
        raise ValueError("budget_bytes must be in (0, scratchpad_bytes]")
    recorder = _Recorder(word_count)
    execution_result = evaluate(context, header, nonce, scratch_observer=recorder)
    mix_event_count = total_iterations * 4
    if len(recorder.events) != mix_event_count + 16:
        raise RuntimeError("trace does not match the v1 iteration/finalization shape")

    bitmap_bytes = (word_count + 7) // 8
    rank_chunks = (word_count + RANK_CHUNK_WORDS - 1) // RANK_CHUNK_WORDS
    rank_bytes = (rank_chunks + 1) * 2
    layout = CheckpointStoreLayout(
        budget, FIXED_STATE_RESERVE_BYTES, bitmap_bytes, rank_bytes, 8, CHECKPOINT_DIVISIONS
    )
    checkpoints = tuple(total_iterations * division // CHECKPOINT_DIVISIONS
                        for division in range(CHECKPOINT_DIVISIONS + 1))
    cuts: list[CheckpointCut] = []
    transcript = hashlib.sha3_384(DOMAIN_SCREEN)
    transcript.update(struct.pack("<QQQQ", word_count, total_iterations, budget, CHECKPOINT_DIVISIONS))

    for checkpoint in checkpoints:
        boundary = checkpoint * 4
        prefix_written = {word for is_write, word, _ in recorder.events[:boundary] if is_write}
        suffix_written = {word for is_write, word, _ in recorder.events[boundary:mix_event_count] if is_write}
        frontier, resume_peak = _backward_live(recorder.events, boundary, len(recorder.events))
        _, capture_peak = _backward_live(recorder.events, 0, boundary, frontier)
        staged_peak = max(capture_peak, resume_peak)
        snapshot = len(prefix_written)
        delta = len(suffix_written)
        duplicated = len(prefix_written & suffix_written)
        full_checkpoint_bytes = FIXED_STATE_RESERVE_BYTES + _store_bytes(snapshot, bitmap_bytes, rank_bytes)
        naive_bytes = (FIXED_STATE_RESERVE_BYTES
                       + _store_bytes(snapshot, bitmap_bytes, rank_bytes)
                       + _store_bytes(delta, bitmap_bytes, rank_bytes))
        optimistic_bytes = FIXED_STATE_RESERVE_BYTES + _store_bytes(staged_peak, bitmap_bytes, rank_bytes)
        cut = CheckpointCut(
            checkpoint, snapshot, delta, duplicated, len(frontier), capture_peak,
            resume_peak, staged_peak, full_checkpoint_bytes, naive_bytes, optimistic_bytes,
            full_checkpoint_bytes <= budget, naive_bytes <= budget, optimistic_bytes <= budget,
        )
        cuts.append(cut)
        transcript.update(struct.pack(
            "<11Q3B", checkpoint, snapshot, delta, duplicated, len(frontier), capture_peak,
            resume_peak, staged_peak, full_checkpoint_bytes, naive_bytes, optimistic_bytes,
            cut.full_checkpoint_fits, cut.naive_snapshot_delta_fits, cut.optimistic_staged_fits,
        ))

    global_maximum_live = cuts[0].resume_peak_live_values
    return TimeCheckpointScreen(
        FORMAT,
        "NON-CONSENSUS FULL-MEMORY OFFLINE CHECKPOINT SCREEN; not an executable attack or gate result",
        layout,
        total_iterations,
        sum(not is_write for is_write, _, _ in recorder.events),
        sum(is_write for is_write, _, _ in recorder.events),
        global_maximum_live,
        tuple(cuts),
        any(cut.naive_snapshot_delta_fits for cut in cuts),
        any(cut.optimistic_staged_fits for cut in cuts),
        transcript.hexdigest(),
        execution_result,
    )
