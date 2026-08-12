# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Deterministic, non-consensus Soveroot PoW v1 research candidate.

This module is a measurement target, not a production algorithm. Its domains,
encoding, parameters, and output MUST NOT be used for block validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct
from typing import Final, Protocol


MASK64: Final = (1 << 64) - 1
REGISTER_COUNT: Final = 8
SCHEDULE_LENGTH: Final = 64
FINAL_SAMPLE_WORDS: Final = 16
SEED_BYTES: Final = 48
MAX_HEADER_BYTES: Final = 4096

DOMAIN_SCHEDULE: Final = b"Soveroot/PowResearch/Schedule/v1\x00"
DOMAIN_DATASET: Final = b"Soveroot/PowResearch/Dataset/v1\x00"
DOMAIN_REGISTERS: Final = b"Soveroot/PowResearch/Registers/v1\x00"
DOMAIN_COMMITMENT: Final = b"Soveroot/PowResearch/Commitment/v1\x00"
DOMAIN_RESULT: Final = b"Soveroot/PowResearch/Result/v1\x00"


@dataclass(frozen=True)
class Params:
    """Tunable research parameters; none are consensus constants."""

    dataset_bytes: int = 2 * 1024 * 1024
    scratchpad_bytes: int = 256 * 1024
    passes: int = 3

    def validate(self) -> None:
        _validate_memory_size("dataset_bytes", self.dataset_bytes, 64 * 1024, 64 * 1024 * 1024)
        _validate_memory_size("scratchpad_bytes", self.scratchpad_bytes, 8 * 1024, 8 * 1024 * 1024)
        if not 1 <= self.passes <= 16:
            raise ValueError("passes must be in [1, 16]")

    def encode(self) -> bytes:
        return struct.pack("<QQQ", self.dataset_bytes, self.scratchpad_bytes, self.passes)

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class ScheduleEntry:
    opcode: int
    immediate: int

    def encode(self) -> bytes:
        return struct.pack("<BQ", self.opcode, self.immediate)


@dataclass(frozen=True)
class EpochContext:
    seed: bytes
    params: Params
    schedule: tuple[ScheduleEntry, ...]
    dataset: bytes
    schedule_digest: bytes
    dataset_digest: bytes


@dataclass(frozen=True)
class ExecutionResult:
    digest: bytes
    registers: tuple[int, ...]
    schedule_digest: bytes
    dataset_digest: bytes
    memory_commitment: bytes

    def to_dict(self) -> dict[str, object]:
        return {
            "digest": self.digest.hex(),
            "registers": [f"{value:016x}" for value in self.registers],
            "schedule_digest": self.schedule_digest.hex(),
            "dataset_digest": self.dataset_digest.hex(),
            "memory_commitment": self.memory_commitment.hex(),
        }


@dataclass
class ExecutionMetrics:
    """Structural counters for tests and diagnostic tooling."""

    mix_iterations: int = 0
    mix_dataset_reads: int = 0
    mix_scratchpad_reads: int = 0
    mix_scratchpad_writes: int = 0
    final_sample_reads: int = 0
    finalization_input_bytes: int = 0


class ScratchAccessObserver(Protocol):
    """Receive exact word-level events without participating in evaluation."""

    def read(self, consumer_kind: int, consumer: int, slot: int, word: int) -> None: ...

    def write(self, iteration: int, slot: int, word: int) -> None: ...


def _validate_memory_size(name: str, value: int, minimum: int, maximum: int) -> None:
    if value < minimum or value > maximum or value & (value - 1):
        raise ValueError(f"{name} must be a power of two in [{minimum}, {maximum}]")
    if value % 8:
        raise ValueError(f"{name} must be divisible by 8")


def _validate_seed(seed: bytes) -> None:
    if len(seed) != SEED_BYTES:
        raise ValueError(f"seed must be exactly {SEED_BYTES} bytes")


def _validate_header(header: bytes) -> None:
    if not header or len(header) > MAX_HEADER_BYTES:
        raise ValueError(f"header must contain 1 to {MAX_HEADER_BYTES} bytes")


def _u64(value: int) -> int:
    return value & MASK64


def _rol64(value: int, shift: int) -> int:
    shift &= 63
    value &= MASK64
    if shift == 0:
        return value
    return ((value << shift) | (value >> (64 - shift))) & MASK64


def _read_u64(memory: bytes | bytearray, selector: int) -> int:
    offset = (selector & (len(memory) // 8 - 1)) * 8
    return struct.unpack_from("<Q", memory, offset)[0]


def _write_u64(memory: bytearray, selector: int, value: int) -> None:
    offset = (selector & (len(memory) // 8 - 1)) * 8
    struct.pack_into("<Q", memory, offset, value & MASK64)


def _generate_schedule(seed: bytes, params: Params) -> tuple[ScheduleEntry, ...]:
    immediate_bytes = SCHEDULE_LENGTH * 8
    shuffle_bytes = (SCHEDULE_LENGTH - 1) * 2
    raw = hashlib.shake_256(DOMAIN_SCHEDULE + seed + params.encode()).digest(
        immediate_bytes + shuffle_bytes
    )
    opcodes = [index & 7 for index in range(SCHEDULE_LENGTH)]
    shuffle_offset = immediate_bytes
    for index in range(SCHEDULE_LENGTH - 1, 0, -1):
        random_value = struct.unpack_from("<H", raw, shuffle_offset)[0]
        shuffle_offset += 2
        selected = random_value % (index + 1)
        opcodes[index], opcodes[selected] = opcodes[selected], opcodes[index]
    return tuple(
        ScheduleEntry(opcode=opcodes[index], immediate=struct.unpack_from("<Q", raw, index * 8)[0])
        for index in range(SCHEDULE_LENGTH)
    )


def prepare_epoch(seed: bytes, params: Params = Params()) -> EpochContext:
    """Prepare shareable seed state; this cost is not counted as nonce work."""

    _validate_seed(seed)
    params.validate()
    schedule = _generate_schedule(seed, params)
    encoded_schedule = b"".join(entry.encode() for entry in schedule)
    dataset = hashlib.shake_256(DOMAIN_DATASET + seed + params.encode()).digest(params.dataset_bytes)
    return EpochContext(
        seed=seed,
        params=params,
        schedule=schedule,
        dataset=dataset,
        schedule_digest=hashlib.sha3_384(encoded_schedule).digest(),
        dataset_digest=hashlib.sha3_384(dataset).digest(),
    )


def _execute_operation(
    opcode: int,
    x: int,
    y: int,
    first_scratch: int,
    second_scratch: int,
    dataset_word: int,
    immediate: int,
) -> int:
    if opcode == 0:
        return _u64(x + y + dataset_word + immediate)
    if opcode == 1:
        return _u64(x ^ _rol64(y + dataset_word, immediate) ^ first_scratch)
    if opcode == 2:
        return _u64((x | 1) * ((dataset_word ^ second_scratch ^ immediate) | 1))
    if opcode == 3:
        return _rol64(x ^ first_scratch ^ dataset_word, y ^ second_scratch ^ immediate)
    if opcode == 4:
        return _u64((x + first_scratch) ^ _u64(dataset_word + second_scratch + immediate))
    if opcode == 5:
        return _u64(_rol64(x + dataset_word + immediate, first_scratch) * (y | 1))
    if opcode == 6:
        return _u64((x ^ second_scratch) + _rol64(dataset_word ^ immediate, first_scratch ^ y))
    if opcode == 7:
        return _rol64(_u64((x | 1) * (y | 1) + first_scratch + second_scratch), dataset_word ^ immediate)
    raise ValueError("opcode must be in [0, 7]")


def evaluate(
    context: EpochContext,
    header: bytes,
    nonce: int,
    *,
    metrics: ExecutionMetrics | None = None,
    scratch_observer: ScratchAccessObserver | None = None,
) -> ExecutionResult:
    """Evaluate one nonce using fixed work proportional to scratchpad words and passes."""

    _validate_seed(context.seed)
    context.params.validate()
    _validate_header(header)
    if not 0 <= nonce <= MASK64:
        raise ValueError("nonce must be an unsigned 64-bit integer")
    if len(context.schedule) != SCHEDULE_LENGTH:
        raise ValueError("context schedule length is invalid")
    if len(context.dataset) != context.params.dataset_bytes:
        raise ValueError("context dataset length is invalid")

    params_bytes = context.params.encode()
    nonce_bytes = struct.pack("<Q", nonce)
    header_digest = hashlib.sha3_384(header).digest()
    initial_state = hashlib.shake_256(
        DOMAIN_REGISTERS + context.seed + header_digest + nonce_bytes + params_bytes
    ).digest(REGISTER_COUNT * 8 + 8)
    registers = list(struct.unpack("<8Q", initial_state[: REGISTER_COUNT * 8]))
    accumulator = struct.unpack_from("<Q", initial_state, REGISTER_COUNT * 8)[0]
    scratchpad = bytearray(context.params.scratchpad_bytes)
    scratchpad_words = context.params.scratchpad_bytes // 8

    for pass_index in range(context.params.passes):
        for word_index in range(scratchpad_words):
            iteration = pass_index * scratchpad_words + word_index
            lane = iteration & (REGISTER_COUNT - 1)
            entry = context.schedule[iteration & (SCHEDULE_LENGTH - 1)]
            x = registers[lane]
            y = registers[(lane + 1) & (REGISTER_COUNT - 1)]
            z = registers[(lane + 3) & (REGISTER_COUNT - 1)]

            first_selector = x ^ _rol64(y, iteration) ^ accumulator ^ entry.immediate
            if scratch_observer is not None:
                scratch_observer.read(0, iteration, 0, first_selector & (scratchpad_words - 1))
            first_scratch = _read_u64(scratchpad, first_selector)
            dataset_selector = (
                first_scratch
                ^ z
                ^ _rol64(accumulator, lane + pass_index)
                ^ iteration
            )
            dataset_word = _read_u64(context.dataset, dataset_selector)
            second_selector = (
                dataset_word
                ^ registers[(lane + 5) & (REGISTER_COUNT - 1)]
                ^ _rol64(_u64(first_scratch + accumulator), entry.immediate)
            )
            if scratch_observer is not None:
                scratch_observer.read(0, iteration, 1, second_selector & (scratchpad_words - 1))
            second_scratch = _read_u64(scratchpad, second_selector)

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
            sequential_value = mixed ^ accumulator ^ second_scratch
            dependent_value = second_scratch ^ _rol64(_u64(mixed + accumulator), dataset_word)
            if scratch_observer is not None:
                scratch_observer.write(iteration, 0, word_index)
            _write_u64(scratchpad, word_index, sequential_value)
            if scratch_observer is not None:
                scratch_observer.write(iteration, 1, second_selector & (scratchpad_words - 1))
            _write_u64(scratchpad, second_selector, dependent_value)

            registers[lane] = _u64(mixed + accumulator + first_scratch)
            neighbor = (lane + 2) & (REGISTER_COUNT - 1)
            registers[neighbor] = _u64(
                registers[neighbor] ^ _rol64(_u64(dataset_word + first_scratch), second_scratch)
            )

            if metrics is not None:
                metrics.mix_iterations += 1
                metrics.mix_dataset_reads += 1
                metrics.mix_scratchpad_reads += 2
                metrics.mix_scratchpad_writes += 2

    sampled_words: list[int] = []
    selector = accumulator ^ registers[0] ^ registers[4]
    for sample_index in range(FINAL_SAMPLE_WORDS):
        selector = _u64(
            _rol64(selector ^ registers[sample_index & (REGISTER_COUNT - 1)], sample_index + 1)
            + 0x9E3779B97F4A7C15
            + sample_index
        )
        if scratch_observer is not None:
            scratch_observer.read(1, sample_index, 0, selector & (scratchpad_words - 1))
        sampled = _read_u64(scratchpad, selector)
        sampled_words.append(sampled)
        selector = _u64(selector ^ sampled)
        if metrics is not None:
            metrics.final_sample_reads += 1

    encoded_registers = struct.pack("<8Q", *registers)
    encoded_accumulator = struct.pack("<Q", accumulator)
    encoded_samples = struct.pack(f"<{FINAL_SAMPLE_WORDS}Q", *sampled_words)
    commitment_input = (
        DOMAIN_COMMITMENT
        + params_bytes
        + encoded_registers
        + encoded_accumulator
        + encoded_samples
    )
    memory_commitment = hashlib.sha3_384(commitment_input).digest()
    result_input = (
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
    )
    digest = hashlib.sha3_384(result_input).digest()
    if metrics is not None:
        metrics.finalization_input_bytes = len(commitment_input) + len(result_input)
    return ExecutionResult(
        digest=digest,
        registers=tuple(registers),
        schedule_digest=context.schedule_digest,
        dataset_digest=context.dataset_digest,
        memory_commitment=memory_commitment,
    )
