# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Optimistic cut-set lower bounds for the non-consensus v1 dependency graph."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .versioned_graph import CapturedVersionedGraph


@dataclass(frozen=True)
class CutSetLowerBound:
    budget_bytes: int
    value_entry_bytes: int
    capacity_values: int
    peak_live_values: int
    strongest_cut_event: int
    live_values_at_strongest_cut: int
    paired_producers_at_strongest_cut: int
    values_over_capacity: int
    additional_producer_executions_min: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _minimum_producers_for_values(values: int, paired_producers: int) -> int:
    """Best-case producers needed when each yields at most two live values."""

    if values <= 0:
        return 0
    paired_values = paired_producers * 2
    if values <= paired_values:
        return (values + 1) // 2
    return paired_producers + values - paired_values


def cut_set_lower_bound(
    graph: CapturedVersionedGraph,
    *,
    budget_bytes: int,
    value_entry_bytes: int,
) -> CutSetLowerBound:
    """Scan every graph cut and return an optimistic regeneration lower bound.

    At a cut, every live version must survive in storage or be regenerated before
    its last future read. The relaxation gives the attacker perfect future
    knowledge, spends the entire budget on values, charges no schedule bytes, and
    lets one producer execution regenerate both of its outputs. This can only
    understate the work required by a real executable attacker.
    """

    if budget_bytes <= 0:
        raise ValueError("budget_bytes must be positive")
    if value_entry_bytes <= 0:
        raise ValueError("value_entry_bytes must be positive")
    capacity = budget_bytes // value_entry_bytes
    if capacity <= 0:
        raise ValueError("budget cannot hold one value entry")

    last_read: dict[int, int] = {}
    for event_index, (tag, version) in enumerate(graph.events):
        if tag == 0 and version != 0:
            last_read[version] = event_index
        elif tag not in (0, 1):
            raise ValueError("unknown captured graph event tag")

    active: set[int] = set()
    live_by_producer: dict[int, int] = {}
    paired_producers = 0
    peak_live = 0
    strongest_event = 0
    strongest_live = 0
    strongest_pairs = 0
    strongest_over = 0
    strongest_bound = 0

    def add_version(version: int) -> None:
        nonlocal paired_producers
        producer = graph.version_producers[version]
        if producer is None:
            raise ValueError("materialized version has no producer")
        previous = live_by_producer.get(producer, 0)
        if previous >= 2:
            raise ValueError("a v1 producer cannot have more than two live outputs")
        live_by_producer[producer] = previous + 1
        if previous == 1:
            paired_producers += 1
        active.add(version)

    def remove_version(version: int) -> None:
        nonlocal paired_producers
        producer = graph.version_producers[version]
        if producer is None or version not in active:
            raise ValueError("attempted to remove an inactive version")
        previous = live_by_producer[producer]
        if previous == 2:
            paired_producers -= 1
        if previous == 1:
            del live_by_producer[producer]
        else:
            live_by_producer[producer] = previous - 1
        active.remove(version)

    for event_index, (tag, version) in enumerate(graph.events):
        if tag == 1 and version in last_read:
            add_version(version)
        elif tag == 0 and version != 0 and last_read[version] == event_index:
            remove_version(version)

        live = len(active)
        peak_live = max(peak_live, live)
        over_capacity = max(0, live - capacity)
        bound = _minimum_producers_for_values(over_capacity, paired_producers)
        if bound > strongest_bound or (bound == strongest_bound and over_capacity > strongest_over):
            strongest_event = event_index
            strongest_live = live
            strongest_pairs = paired_producers
            strongest_over = over_capacity
            strongest_bound = bound

    if active:
        raise ValueError("captured graph ended with live versions")
    return CutSetLowerBound(
        budget_bytes=budget_bytes,
        value_entry_bytes=value_entry_bytes,
        capacity_values=capacity,
        peak_live_values=peak_live,
        strongest_cut_event=strongest_event,
        live_values_at_strongest_cut=strongest_live,
        paired_producers_at_strongest_cut=strongest_pairs,
        values_over_capacity=strongest_over,
        additional_producer_executions_min=strongest_bound,
    )
