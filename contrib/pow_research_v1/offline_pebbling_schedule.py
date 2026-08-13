# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Deterministic graph-only replay schedules for the non-consensus v1 candidate."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
import hashlib
import heapq
import struct

from .versioned_graph import CapturedVersionedGraph


DOMAIN_SCHEDULE = b"Soveroot/PowResearch/OfflinePebblingSchedule/v1\x00"
_NO_FUTURE_USE = 1 << 63


@dataclass(frozen=True)
class OfflinePebblingSchedule:
    budget_bytes: int
    value_entry_bytes: int
    capacity_values: int
    canonical_reads: int
    canonical_read_misses: int
    replayed_producers: int
    replayed_input_requests: int
    replay_cache_hits: int
    replay_cache_misses: int
    maximum_replay_depth: int
    peak_retained_values: int
    peak_transient_values: int
    schedule_frames: int
    schedule_actions: int
    schedule_bytes: int
    schedule_commitment: str

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)


def _decode_graph(
    graph: CapturedVersionedGraph,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]], tuple[tuple[int, int], ...]]:
    """Recover producer inputs/outputs and final reads from the canonical event order."""

    written_versions = len(graph.version_producers) - 1
    if written_versions % 2:
        raise ValueError("captured graph must contain two outputs per producer")
    producer_count = written_versions // 2
    producer_event_count = producer_count * 4
    if len(graph.events) < producer_event_count:
        raise ValueError("captured graph event stream is incomplete")

    inputs: list[tuple[int, int]] = []
    outputs: list[tuple[int, int]] = []
    for producer in range(producer_count):
        group = graph.events[producer * 4 : producer * 4 + 4]
        if tuple(tag for tag, _ in group) != (0, 0, 1, 1):
            raise ValueError("captured producer events must be read, read, write, write")
        producer_inputs = (group[0][1], group[1][1])
        producer_outputs = (group[2][1], group[3][1])
        for version in producer_inputs:
            if version < 0 or version >= len(graph.version_producers):
                raise ValueError("producer input names an unknown version")
            source = graph.version_producers[version]
            if source is not None and source >= producer:
                raise ValueError("captured graph is not an acyclic producer graph")
        for version in producer_outputs:
            if not 0 < version < len(graph.version_producers):
                raise ValueError("producer output names an unknown version")
            if graph.version_producers[version] != producer:
                raise ValueError("producer table disagrees with the event stream")
        inputs.append(producer_inputs)
        outputs.append(producer_outputs)

    final_events = graph.events[producer_event_count:]
    if any(tag != 0 for tag, _ in final_events):
        raise ValueError("events after the producer stream must be final reads")
    return inputs, outputs, final_events


class _Planner:
    def __init__(
        self,
        graph: CapturedVersionedGraph,
        *,
        budget_bytes: int,
        value_entry_bytes: int,
    ) -> None:
        if budget_bytes <= 0:
            raise ValueError("budget_bytes must be positive")
        if value_entry_bytes <= 0:
            raise ValueError("value_entry_bytes must be positive")
        self.capacity = budget_bytes // value_entry_bytes
        if self.capacity < 2:
            raise ValueError("budget must hold at least two value entries")

        self.graph = graph
        self.inputs, self.outputs, self.final_events = _decode_graph(graph)
        self.future_reads: dict[int, deque[int]] = defaultdict(deque)
        for event_index, (tag, version) in enumerate(graph.events):
            if tag == 0 and version:
                self.future_reads[version].append(event_index)

        self.cache: set[int] = set()
        self.eviction_heap: list[tuple[int, int]] = []
        self.canonical_reads = 0
        self.canonical_misses = 0
        self.replayed_producers = 0
        self.replayed_input_requests = 0
        self.replay_cache_hits = 0
        self.replay_cache_misses = 0
        self.maximum_depth = 0
        self.peak_retained = 0
        self.peak_transient = 0
        self.schedule_frames = 0
        self.schedule_actions = 0
        self.schedule_bytes = len(DOMAIN_SCHEDULE) + 24
        self.hasher = hashlib.sha3_384()
        self.hasher.update(DOMAIN_SCHEDULE)
        self.hasher.update(struct.pack("<QQQ", budget_bytes, value_entry_bytes, len(self.inputs)))

    def _next_use(self, version: int) -> int:
        uses = self.future_reads.get(version)
        return uses[0] if uses else _NO_FUTURE_USE

    def _heap_update(self, version: int) -> None:
        heapq.heappush(self.eviction_heap, (-self._next_use(version), version))

    def _farthest_unpinned(self, pinned: frozenset[int]) -> tuple[int, int]:
        deferred: list[tuple[int, int]] = []
        victim: tuple[int, int] | None = None
        while self.eviction_heap:
            item = heapq.heappop(self.eviction_heap)
            next_use = -item[0]
            version = item[1]
            if version not in self.cache or next_use != self._next_use(version):
                continue
            if version in pinned:
                deferred.append(item)
                continue
            victim = (version, next_use)
            break
        for item in deferred:
            heapq.heappush(self.eviction_heap, item)
        if victim is None:
            raise ValueError("value capacity is too small for the pinned replay frontier")
        return victim

    def _retain(self, version: int, pinned: frozenset[int]) -> None:
        if version == 0 or version in self.cache:
            return
        # A recursively requested historical value can have no remaining
        # canonical read while still being required by its immediate parent.
        if not self.future_reads.get(version) and version not in pinned:
            return
        while len(self.cache) >= self.capacity:
            victim, victim_next_use = self._farthest_unpinned(pinned)
            if version not in pinned and self._next_use(version) >= victim_next_use:
                self._heap_update(victim)
                return
            self.cache.remove(victim)
        self.cache.add(version)
        self._heap_update(version)
        self.peak_retained = max(self.peak_retained, len(self.cache))

    def _ensure(
        self,
        version: int,
        pinned: frozenset[int],
        depth: int,
        actions: list[int],
    ) -> None:
        if version == 0:
            return
        self.replayed_input_requests += 1
        self.maximum_depth = max(self.maximum_depth, depth)
        if version in self.cache:
            self.replay_cache_hits += 1
            return
        self.replay_cache_misses += 1
        producer = self.graph.version_producers[version]
        if producer is None:
            raise ValueError("materialized version has no producer")

        left, right = self.inputs[producer]
        self._ensure(left, pinned, depth + 1, actions)
        left_pin = pinned | ({left} if left else set())
        self._ensure(right, frozenset(left_pin), depth + 1, actions)
        self.peak_transient = max(self.peak_transient, len(self.cache) + 2)

        self.replayed_producers += 1
        actions.append(producer)
        first, second = self.outputs[producer]
        requested_pin = pinned | {version}
        self._retain(version, frozenset(requested_pin))
        sibling = second if version == first else first
        self._retain(sibling, frozenset(requested_pin))

    def _canonical_read(self, version: int, event_index: int) -> None:
        self.canonical_reads += 1
        if version and version not in self.cache:
            actions: list[int] = []
            self._ensure(version, frozenset(), 1, actions)
            if len(actions) > 0xFFFFFFFF or version > 0xFFFFFFFF:
                raise ValueError("schedule frame exceeds the v0 encoding")
            frame = struct.pack("<BII", 1, version, len(actions))
            self.hasher.update(frame)
            for producer in actions:
                if producer > 0xFFFFFFFF:
                    raise ValueError("producer ordinal exceeds the v0 encoding")
                self.hasher.update(struct.pack("<I", producer))
            self.canonical_misses += 1
            self.schedule_frames += 1
            self.schedule_actions += len(actions)
            self.schedule_bytes += len(frame) + 4 * len(actions)

        if version:
            uses = self.future_reads[version]
            if not uses or uses[0] != event_index:
                raise ValueError("canonical future-use index is inconsistent")
            uses.popleft()
            if version in self.cache:
                if uses:
                    self._heap_update(version)
                else:
                    self.cache.remove(version)

    def run(self, *, budget_bytes: int, value_entry_bytes: int) -> OfflinePebblingSchedule:
        for producer, (left, right) in enumerate(self.inputs):
            event_index = producer * 4
            self._canonical_read(left, event_index)
            self._canonical_read(right, event_index + 1)
            self.peak_transient = max(self.peak_transient, len(self.cache) + 2)
            first, second = self.outputs[producer]
            self._retain(first, frozenset())
            self._retain(second, frozenset())

        final_start = len(self.inputs) * 4
        for offset, (_, version) in enumerate(self.final_events):
            self._canonical_read(version, final_start + offset)

        if any(self.future_reads.values()):
            raise ValueError("captured graph ended before all future reads were consumed")
        return OfflinePebblingSchedule(
            budget_bytes=budget_bytes,
            value_entry_bytes=value_entry_bytes,
            capacity_values=self.capacity,
            canonical_reads=self.canonical_reads,
            canonical_read_misses=self.canonical_misses,
            replayed_producers=self.replayed_producers,
            replayed_input_requests=self.replayed_input_requests,
            replay_cache_hits=self.replay_cache_hits,
            replay_cache_misses=self.replay_cache_misses,
            maximum_replay_depth=self.maximum_depth,
            peak_retained_values=self.peak_retained,
            peak_transient_values=self.peak_transient,
            schedule_frames=self.schedule_frames,
            schedule_actions=self.schedule_actions,
            schedule_bytes=self.schedule_bytes,
            schedule_commitment=self.hasher.hexdigest(),
        )


def search_offline_pebbling_schedule(
    graph: CapturedVersionedGraph,
    *,
    budget_bytes: int,
    value_entry_bytes: int,
) -> OfflinePebblingSchedule:
    """Build an optimistic recursive replay schedule over scratch versions only.

    This planner is not an executable reduced-memory PoW evaluator. In particular,
    it treats the historical VM and address state needed by a producer as free.
    """

    planner = _Planner(
        graph,
        budget_bytes=budget_bytes,
        value_entry_bytes=value_entry_bytes,
    )
    return planner.run(budget_bytes=budget_bytes, value_entry_bytes=value_entry_bytes)
