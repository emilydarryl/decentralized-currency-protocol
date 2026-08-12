# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Exact versioned scratch-dependency graph for the non-consensus v1 candidate."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct

from .powvm import EpochContext, ExecutionResult, FINAL_SAMPLE_WORDS, evaluate


FORMAT = "soveroot-pow-v1-versioned-graph-v0"
DOMAIN_VERSIONED_GRAPH = b"Soveroot/PowResearch/VersionedGraph/v1\x00"
CANONICAL_READ_EDGE_BYTES = 27
CANONICAL_WRITE_VERSION_BYTES = 34


@dataclass(frozen=True)
class Layout:
    read_edge_bytes: int
    write_version_bytes: int
    version_table_entry_bytes: int


PACKED_LAYOUT = Layout(16, 24, 4)
CONSERVATIVE_LAYOUT = Layout(40, 40, 8)


class VersionedGraphRecorder:
    """Commit to exact read-from and overwrite edges without retaining the graph."""

    def __init__(self, word_count: int, mix_iterations: int) -> None:
        self.word_count = word_count
        self.mix_iterations = mix_iterations
        self.current_version = [0] * word_count
        self.read_edges = 0
        self.write_versions = 0
        self.initial_zero_edges = 0
        self.materialized_edges = 0
        self.overwrite_edges = 0
        self._hasher = hashlib.sha3_384()
        self._hasher.update(DOMAIN_VERSIONED_GRAPH)
        self._hasher.update(struct.pack("<QQQ", word_count, mix_iterations, FINAL_SAMPLE_WORDS))

    def read(self, consumer_kind: int, consumer: int, slot: int, word: int) -> None:
        if consumer_kind not in (0, 1):
            raise ValueError("consumer kind must identify mixing or finalization")
        if slot not in (0, 1) or (consumer_kind == 1 and slot != 0):
            raise ValueError("invalid read slot")
        if not 0 <= word < self.word_count:
            raise ValueError("read word is outside the scratchpad")
        source_version = self.current_version[word]
        self._hasher.update(struct.pack("<BBQBQQ", 0, consumer_kind, consumer, slot, word, source_version))
        self.read_edges += 1
        if source_version == 0:
            self.initial_zero_edges += 1
        else:
            self.materialized_edges += 1

    def write(self, iteration: int, slot: int, word: int) -> None:
        if slot not in (0, 1):
            raise ValueError("invalid write slot")
        if not 0 <= word < self.word_count:
            raise ValueError("write word is outside the scratchpad")
        previous_version = self.current_version[word]
        self.write_versions += 1
        self._hasher.update(struct.pack(
            "<BQQBQQ",
            1,
            self.write_versions,
            iteration,
            slot,
            word,
            previous_version,
        ))
        self.current_version[word] = self.write_versions
        if previous_version:
            self.overwrite_edges += 1

    def _layout(self, layout: Layout) -> dict[str, int]:
        graph_records_bytes = (
            self.read_edges * layout.read_edge_bytes
            + self.write_versions * layout.write_version_bytes
        )
        version_table_bytes = self.word_count * layout.version_table_entry_bytes
        return {
            "read_edge_bytes": layout.read_edge_bytes,
            "write_version_bytes": layout.write_version_bytes,
            "version_table_entry_bytes": layout.version_table_entry_bytes,
            "graph_records_bytes": graph_records_bytes,
            "version_table_bytes": version_table_bytes,
            "logical_model_bytes": graph_records_bytes + version_table_bytes,
        }

    def summary(self) -> dict[str, object]:
        expected_reads = self.mix_iterations * 2 + FINAL_SAMPLE_WORDS
        expected_writes = self.mix_iterations * 2
        if self.read_edges != expected_reads or self.write_versions != expected_writes:
            raise ValueError("observed graph does not match the v1 access-count invariant")
        header_bytes = len(DOMAIN_VERSIONED_GRAPH) + 24
        encoded_bytes = (
            header_bytes
            + self.read_edges * CANONICAL_READ_EDGE_BYTES
            + self.write_versions * CANONICAL_WRITE_VERSION_BYTES
        )
        return {
            "graph_commitment": self._hasher.hexdigest(),
            "mix_iterations": self.mix_iterations,
            "read_edges": self.read_edges,
            "write_versions": self.write_versions,
            "initial_zero_edges": self.initial_zero_edges,
            "materialized_edges": self.materialized_edges,
            "overwrite_edges": self.overwrite_edges,
            "canonical_encoding": {
                "header_bytes": header_bytes,
                "read_edge_bytes": CANONICAL_READ_EDGE_BYTES,
                "write_version_bytes": CANONICAL_WRITE_VERSION_BYTES,
                "encoded_bytes": encoded_bytes,
            },
            "logical_layouts": {
                "packed": self._layout(PACKED_LAYOUT),
                "conservative": self._layout(CONSERVATIVE_LAYOUT),
            },
        }


def evaluate_versioned_graph(
    context: EpochContext,
    header: bytes,
    nonce: int,
) -> tuple[ExecutionResult, dict[str, object]]:
    word_count = context.params.scratchpad_bytes // 8
    recorder = VersionedGraphRecorder(word_count, word_count * context.params.passes)
    result = evaluate(context, header, nonce, scratch_observer=recorder)
    return result, recorder.summary()
