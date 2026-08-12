# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Deterministic, non-consensus prototype for Soveroot PoW research.

This module is a measurement harness, not a proposed production algorithm.
Its constants, encoding, and output MUST NOT be used for block validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct
from typing import Final


MASK64: Final = (1 << 64) - 1
REGISTER_COUNT: Final = 8
SEED_BYTES: Final = 48
MAX_HEADER_BYTES: Final = 4096

DOMAIN_PROGRAM: Final = b"Soveroot/PowResearch/Program/v0\x00"
DOMAIN_DATASET: Final = b"Soveroot/PowResearch/Dataset/v0\x00"
DOMAIN_SCRATCH: Final = b"Soveroot/PowResearch/Scratch/v0\x00"
DOMAIN_REGISTERS: Final = b"Soveroot/PowResearch/Registers/v0\x00"
DOMAIN_MIX: Final = b"Soveroot/PowResearch/Mix/v0\x00"
DOMAIN_RESULT: Final = b"Soveroot/PowResearch/Result/v0\x00"


@dataclass(frozen=True)
class Params:
    """Tunable research parameters; none are consensus constants."""

    dataset_bytes: int = 256 * 1024
    scratchpad_bytes: int = 64 * 1024
    program_instructions: int = 64
    passes: int = 4

    def validate(self) -> None:
        _validate_memory_size("dataset_bytes", self.dataset_bytes, 64 * 1024, 64 * 1024 * 1024)
        _validate_memory_size("scratchpad_bytes", self.scratchpad_bytes, 8 * 1024, 8 * 1024 * 1024)
        if not 16 <= self.program_instructions <= 256:
            raise ValueError("program_instructions must be in [16, 256]")
        if not 1 <= self.passes <= 16:
            raise ValueError("passes must be in [1, 16]")

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class Instruction:
    opcode: int
    destination: int
    source: int
    immediate: int

    def encode(self) -> bytes:
        return struct.pack("<BBBQ", self.opcode, self.destination, self.source, self.immediate)


@dataclass(frozen=True)
class EpochContext:
    seed: bytes
    params: Params
    program: tuple[Instruction, ...]
    dataset: bytes
    program_digest: bytes
    dataset_digest: bytes


@dataclass(frozen=True)
class ExecutionResult:
    digest: bytes
    registers: tuple[int, ...]
    program_digest: bytes
    dataset_digest: bytes
    scratchpad_digest: bytes

    def to_dict(self) -> dict[str, object]:
        return {
            "digest": self.digest.hex(),
            "registers": [f"{value:016x}" for value in self.registers],
            "program_digest": self.program_digest.hex(),
            "dataset_digest": self.dataset_digest.hex(),
            "scratchpad_digest": self.scratchpad_digest.hex(),
        }


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


def _rol64(value: int, shift: int) -> int:
    shift &= 63
    if shift == 0:
        return value & MASK64
    return ((value << shift) | (value >> (64 - shift))) & MASK64


def _read_u64(memory: bytes | bytearray, selector: int) -> int:
    offset = (selector % (len(memory) // 8)) * 8
    return struct.unpack_from("<Q", memory, offset)[0]


def _write_u64(memory: bytearray, selector: int, value: int) -> None:
    offset = (selector % (len(memory) // 8)) * 8
    struct.pack_into("<Q", memory, offset, value & MASK64)


def _generate_program(seed: bytes, count: int) -> tuple[Instruction, ...]:
    raw = hashlib.shake_256(DOMAIN_PROGRAM + seed).digest(count * 13)
    opcodes = [index & 7 for index in range(count)]
    shuffle_offset = count * 11
    for index in range(count - 1, 0, -1):
        random_value = struct.unpack_from("<H", raw, shuffle_offset)[0]
        shuffle_offset += 2
        selected = random_value % (index + 1)
        opcodes[index], opcodes[selected] = opcodes[selected], opcodes[index]
    instructions = []
    for index in range(count):
        chunk = raw[index * 11:(index + 1) * 11]
        instructions.append(Instruction(
            opcode=opcodes[index],
            destination=chunk[1] & (REGISTER_COUNT - 1),
            source=chunk[2] & (REGISTER_COUNT - 1),
            immediate=struct.unpack_from("<Q", chunk, 3)[0],
        ))
    return tuple(instructions)


def prepare_epoch(seed: bytes, params: Params = Params()) -> EpochContext:
    """Prepare seed-dependent state once and share it across nonce attempts."""

    _validate_seed(seed)
    params.validate()
    program = _generate_program(seed, params.program_instructions)
    encoded_program = b"".join(instruction.encode() for instruction in program)
    dataset = hashlib.shake_256(DOMAIN_DATASET + seed).digest(params.dataset_bytes)
    return EpochContext(
        seed=seed,
        params=params,
        program=program,
        dataset=dataset,
        program_digest=hashlib.sha3_384(encoded_program).digest(),
        dataset_digest=hashlib.sha3_384(dataset).digest(),
    )


def evaluate(context: EpochContext, header: bytes, nonce: int) -> ExecutionResult:
    """Evaluate one nonce using an already prepared epoch context."""

    _validate_seed(context.seed)
    context.params.validate()
    _validate_header(header)
    if not 0 <= nonce <= MASK64:
        raise ValueError("nonce must be an unsigned 64-bit integer")

    nonce_bytes = struct.pack("<Q", nonce)
    header_digest = hashlib.sha3_384(header).digest()
    register_bytes = hashlib.shake_256(
        DOMAIN_REGISTERS + context.seed + header_digest + nonce_bytes
    ).digest(REGISTER_COUNT * 8)
    registers = list(struct.unpack("<8Q", register_bytes))
    scratchpad = bytearray(hashlib.shake_256(
        DOMAIN_SCRATCH + context.seed + header_digest + nonce_bytes
    ).digest(context.params.scratchpad_bytes))

    for pass_index in range(context.params.passes):
        for pc, instruction in enumerate(context.program):
            destination = instruction.destination
            source = instruction.source
            left = registers[destination]
            right = registers[source]
            immediate = instruction.immediate
            selector = left ^ _rol64(right, pc + pass_index) ^ immediate

            if instruction.opcode == 0:
                result = left + right + immediate
            elif instruction.opcode == 1:
                result = left ^ _rol64(right, immediate) ^ immediate
            elif instruction.opcode == 2:
                result = (left | 1) * ((right ^ immediate) | 1)
            elif instruction.opcode == 3:
                result = _rol64(left ^ right ^ immediate, right)
            elif instruction.opcode == 4:
                result = left ^ _read_u64(context.dataset, selector)
            elif instruction.opcode == 5:
                result = right + _read_u64(scratchpad, selector)
            elif instruction.opcode == 6:
                result = left + right + immediate
                _write_u64(scratchpad, selector, result)
            else:
                state = struct.pack("<8QII", *registers, pass_index, pc)
                result = int.from_bytes(hashlib.sha3_384(DOMAIN_MIX + state).digest()[:8], "little")

            registers[destination] = result & MASK64

    encoded_registers = struct.pack("<8Q", *registers)
    scratchpad_digest = hashlib.sha3_384(scratchpad).digest()
    digest = hashlib.sha3_384(
        DOMAIN_RESULT
        + context.seed
        + header_digest
        + nonce_bytes
        + context.program_digest
        + context.dataset_digest
        + encoded_registers
        + scratchpad_digest
    ).digest()
    return ExecutionResult(
        digest=digest,
        registers=tuple(registers),
        program_digest=context.program_digest,
        dataset_digest=context.dataset_digest,
        scratchpad_digest=scratchpad_digest,
    )
