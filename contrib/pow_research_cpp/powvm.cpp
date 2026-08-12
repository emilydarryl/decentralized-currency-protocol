// Copyright (c) 2026 The Soveroot developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or https://opensource.org/license/mit/.
//
// NON-CONSENSUS RESEARCH CODE. This executable is deliberately standalone.

#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <span>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {

using Bytes = std::vector<std::uint8_t>;

constexpr std::size_t SEED_BYTES{48};
constexpr std::size_t REGISTER_COUNT{8};
constexpr std::size_t MAX_HEADER_BYTES{4096};

constexpr char DOMAIN_PROGRAM[] = "Soveroot/PowResearch/Program/v0\0";
constexpr char DOMAIN_DATASET[] = "Soveroot/PowResearch/Dataset/v0\0";
constexpr char DOMAIN_SCRATCH[] = "Soveroot/PowResearch/Scratch/v0\0";
constexpr char DOMAIN_REGISTERS[] = "Soveroot/PowResearch/Registers/v0\0";
constexpr char DOMAIN_MIX[] = "Soveroot/PowResearch/Mix/v0\0";
constexpr char DOMAIN_RESULT[] = "Soveroot/PowResearch/Result/v0\0";

struct Params {
    std::size_t dataset_bytes;
    std::size_t scratchpad_bytes;
    std::size_t program_instructions;
    std::size_t passes;
};

struct Instruction {
    std::uint8_t opcode;
    std::uint8_t destination;
    std::uint8_t source;
    std::uint64_t immediate;
};

struct EpochContext {
    Bytes seed;
    Params params;
    std::vector<Instruction> program;
    Bytes dataset;
    Bytes program_digest;
    Bytes dataset_digest;
};

struct ExecutionResult {
    Bytes digest;
    std::array<std::uint64_t, REGISTER_COUNT> registers;
    Bytes program_digest;
    Bytes dataset_digest;
    Bytes scratchpad_digest;
};

constexpr std::array<std::uint64_t, 24> KECCAK_ROUND_CONSTANTS{
    0x0000000000000001ULL, 0x0000000000008082ULL,
    0x800000000000808aULL, 0x8000000080008000ULL,
    0x000000000000808bULL, 0x0000000080000001ULL,
    0x8000000080008081ULL, 0x8000000000008009ULL,
    0x000000000000008aULL, 0x0000000000000088ULL,
    0x0000000080008009ULL, 0x000000008000000aULL,
    0x000000008000808bULL, 0x800000000000008bULL,
    0x8000000000008089ULL, 0x8000000000008003ULL,
    0x8000000000008002ULL, 0x8000000000000080ULL,
    0x000000000000800aULL, 0x800000008000000aULL,
    0x8000000080008081ULL, 0x8000000000008080ULL,
    0x0000000080000001ULL, 0x8000000080008008ULL,
};

constexpr std::array<unsigned, 24> KECCAK_ROTATIONS{
    1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 2, 14,
    27, 41, 56, 8, 25, 43, 62, 18, 39, 61, 20, 44,
};

constexpr std::array<unsigned, 24> KECCAK_LANES{
    10, 7, 11, 17, 18, 3, 5, 16, 8, 21, 24, 4,
    15, 23, 19, 13, 12, 2, 20, 14, 22, 9, 6, 1,
};

std::uint64_t ReadLE64(const std::uint8_t* data)
{
    std::uint64_t value{0};
    for (unsigned i{0}; i < 8; ++i) value |= std::uint64_t{data[i]} << (8 * i);
    return value;
}

void AppendLE64(Bytes& output, std::uint64_t value)
{
    for (unsigned i{0}; i < 8; ++i) output.push_back(static_cast<std::uint8_t>(value >> (8 * i)));
}

void WriteLE64(std::uint8_t* output, std::uint64_t value)
{
    for (unsigned i{0}; i < 8; ++i) output[i] = static_cast<std::uint8_t>(value >> (8 * i));
}

void KeccakF(std::array<std::uint64_t, 25>& state)
{
    for (std::size_t round{0}; round < KECCAK_ROUND_CONSTANTS.size(); ++round) {
        std::array<std::uint64_t, 5> column{};
        for (std::size_t i{0}; i < 5; ++i) {
            column[i] = state[i] ^ state[i + 5] ^ state[i + 10] ^ state[i + 15] ^ state[i + 20];
        }
        for (std::size_t i{0}; i < 5; ++i) {
            const std::uint64_t delta = column[(i + 4) % 5] ^ std::rotl(column[(i + 1) % 5], 1);
            for (std::size_t j{0}; j < 25; j += 5) state[j + i] ^= delta;
        }

        std::uint64_t current = state[1];
        for (std::size_t i{0}; i < 24; ++i) {
            const std::size_t lane = KECCAK_LANES[i];
            const std::uint64_t saved = state[lane];
            state[lane] = std::rotl(current, static_cast<int>(KECCAK_ROTATIONS[i]));
            current = saved;
        }

        for (std::size_t row{0}; row < 25; row += 5) {
            const auto saved = std::array<std::uint64_t, 5>{
                state[row], state[row + 1], state[row + 2], state[row + 3], state[row + 4]};
            for (std::size_t i{0}; i < 5; ++i) {
                state[row + i] = saved[i] ^ ((~saved[(i + 1) % 5]) & saved[(i + 2) % 5]);
            }
        }
        state[0] ^= KECCAK_ROUND_CONSTANTS[round];
    }
}

Bytes KeccakSponge(std::span<const std::uint8_t> input, std::size_t rate, std::uint8_t suffix, std::size_t output_size)
{
    std::array<std::uint64_t, 25> state{};
    while (input.size() >= rate) {
        for (std::size_t i{0}; i < rate / 8; ++i) state[i] ^= ReadLE64(input.data() + i * 8);
        KeccakF(state);
        input = input.subspan(rate);
    }

    Bytes final_block(rate, 0);
    std::copy(input.begin(), input.end(), final_block.begin());
    final_block[input.size()] ^= suffix;
    final_block.back() ^= 0x80;
    for (std::size_t i{0}; i < rate / 8; ++i) state[i] ^= ReadLE64(final_block.data() + i * 8);
    KeccakF(state);

    Bytes output;
    output.reserve(output_size);
    while (output.size() < output_size) {
        Bytes block(rate);
        for (std::size_t i{0}; i < rate / 8; ++i) WriteLE64(block.data() + i * 8, state[i]);
        const std::size_t take = std::min(rate, output_size - output.size());
        output.insert(output.end(), block.begin(), block.begin() + take);
        if (output.size() < output_size) KeccakF(state);
    }
    return output;
}

Bytes Sha3_384(std::span<const std::uint8_t> input)
{
    return KeccakSponge(input, 104, 0x06, 48);
}

Bytes Shake256(std::span<const std::uint8_t> input, std::size_t output_size)
{
    return KeccakSponge(input, 136, 0x1f, output_size);
}

template <std::size_t N>
Bytes DomainInput(const char (&domain)[N], std::span<const std::uint8_t> first = {}, std::span<const std::uint8_t> second = {}, std::span<const std::uint8_t> third = {})
{
    Bytes output(reinterpret_cast<const std::uint8_t*>(domain), reinterpret_cast<const std::uint8_t*>(domain) + N - 1);
    output.insert(output.end(), first.begin(), first.end());
    output.insert(output.end(), second.begin(), second.end());
    output.insert(output.end(), third.begin(), third.end());
    return output;
}

bool IsPowerOfTwo(std::size_t value)
{
    return value != 0 && (value & (value - 1)) == 0;
}

void Validate(const Bytes& seed, const Params& params)
{
    if (seed.size() != SEED_BYTES) throw std::invalid_argument("seed must be exactly 48 bytes");
    if (!IsPowerOfTwo(params.dataset_bytes) || params.dataset_bytes < 64 * 1024 || params.dataset_bytes > 64 * 1024 * 1024) {
        throw std::invalid_argument("dataset_bytes is outside the research envelope");
    }
    if (!IsPowerOfTwo(params.scratchpad_bytes) || params.scratchpad_bytes < 8 * 1024 || params.scratchpad_bytes > 8 * 1024 * 1024) {
        throw std::invalid_argument("scratchpad_bytes is outside the research envelope");
    }
    if (params.program_instructions < 16 || params.program_instructions > 256) throw std::invalid_argument("invalid instruction count");
    if (params.passes < 1 || params.passes > 16) throw std::invalid_argument("invalid pass count");
}

std::vector<Instruction> GenerateProgram(const Bytes& seed, std::size_t count)
{
    const Bytes raw = Shake256(DomainInput(DOMAIN_PROGRAM, seed), count * 13);
    std::vector<std::uint8_t> opcodes(count);
    for (std::size_t i{0}; i < count; ++i) opcodes[i] = static_cast<std::uint8_t>(i & 7);
    std::size_t shuffle_offset = count * 11;
    for (std::size_t i{count - 1}; i > 0; --i) {
        const std::uint16_t random_value = std::uint16_t{raw[shuffle_offset]} | (std::uint16_t{raw[shuffle_offset + 1]} << 8);
        shuffle_offset += 2;
        const std::size_t selected = random_value % (i + 1);
        std::swap(opcodes[i], opcodes[selected]);
    }

    std::vector<Instruction> program;
    program.reserve(count);
    for (std::size_t i{0}; i < count; ++i) {
        const std::size_t offset = i * 11;
        program.push_back({opcodes[i], static_cast<std::uint8_t>(raw[offset + 1] & 7),
                           static_cast<std::uint8_t>(raw[offset + 2] & 7), ReadLE64(raw.data() + offset + 3)});
    }
    return program;
}

EpochContext PrepareEpoch(const Bytes& seed, const Params& params)
{
    Validate(seed, params);
    auto program = GenerateProgram(seed, params.program_instructions);
    Bytes encoded_program;
    encoded_program.reserve(program.size() * 11);
    for (const Instruction& instruction : program) {
        encoded_program.push_back(instruction.opcode);
        encoded_program.push_back(instruction.destination);
        encoded_program.push_back(instruction.source);
        AppendLE64(encoded_program, instruction.immediate);
    }
    Bytes dataset = Shake256(DomainInput(DOMAIN_DATASET, seed), params.dataset_bytes);
    return {seed, params, std::move(program), dataset, Sha3_384(encoded_program), Sha3_384(dataset)};
}

std::uint64_t ReadMemory(const Bytes& memory, std::uint64_t selector)
{
    const std::size_t offset = static_cast<std::size_t>(selector % (memory.size() / 8)) * 8;
    return ReadLE64(memory.data() + offset);
}

void WriteMemory(Bytes& memory, std::uint64_t selector, std::uint64_t value)
{
    const std::size_t offset = static_cast<std::size_t>(selector % (memory.size() / 8)) * 8;
    WriteLE64(memory.data() + offset, value);
}

ExecutionResult Evaluate(const EpochContext& context, const Bytes& header, std::uint64_t nonce)
{
    Validate(context.seed, context.params);
    if (header.empty() || header.size() > MAX_HEADER_BYTES) throw std::invalid_argument("header size is outside the research envelope");

    Bytes nonce_bytes;
    AppendLE64(nonce_bytes, nonce);
    const Bytes header_digest = Sha3_384(header);
    const Bytes register_bytes = Shake256(DomainInput(DOMAIN_REGISTERS, context.seed, header_digest, nonce_bytes), REGISTER_COUNT * 8);
    std::array<std::uint64_t, REGISTER_COUNT> registers{};
    for (std::size_t i{0}; i < REGISTER_COUNT; ++i) registers[i] = ReadLE64(register_bytes.data() + i * 8);
    Bytes scratchpad = Shake256(DomainInput(DOMAIN_SCRATCH, context.seed, header_digest, nonce_bytes), context.params.scratchpad_bytes);

    for (std::size_t pass{0}; pass < context.params.passes; ++pass) {
        for (std::size_t pc{0}; pc < context.program.size(); ++pc) {
            const Instruction& instruction = context.program[pc];
            const std::uint64_t left = registers[instruction.destination];
            const std::uint64_t right = registers[instruction.source];
            const std::uint64_t selector = left ^ std::rotl(right, static_cast<int>((pc + pass) & 63)) ^ instruction.immediate;
            std::uint64_t result{0};
            switch (instruction.opcode) {
            case 0:
                result = left + right + instruction.immediate;
                break;
            case 1:
                result = left ^ std::rotl(right, static_cast<int>(instruction.immediate & 63)) ^ instruction.immediate;
                break;
            case 2:
                result = (left | 1) * ((right ^ instruction.immediate) | 1);
                break;
            case 3:
                result = std::rotl(left ^ right ^ instruction.immediate, static_cast<int>(right & 63));
                break;
            case 4:
                result = left ^ ReadMemory(context.dataset, selector);
                break;
            case 5:
                result = right + ReadMemory(scratchpad, selector);
                break;
            case 6:
                result = left + right + instruction.immediate;
                WriteMemory(scratchpad, selector, result);
                break;
            case 7: {
                Bytes state;
                state.reserve(REGISTER_COUNT * 8 + 8);
                for (const std::uint64_t value : registers) AppendLE64(state, value);
                for (unsigned i{0}; i < 4; ++i) state.push_back(static_cast<std::uint8_t>(pass >> (8 * i)));
                for (unsigned i{0}; i < 4; ++i) state.push_back(static_cast<std::uint8_t>(pc >> (8 * i)));
                const Bytes mixed = Sha3_384(DomainInput(DOMAIN_MIX, state));
                result = ReadLE64(mixed.data());
                break;
            }
            default:
                throw std::logic_error("unreachable opcode");
            }
            registers[instruction.destination] = result;
        }
    }

    Bytes encoded_registers;
    for (const std::uint64_t value : registers) AppendLE64(encoded_registers, value);
    const Bytes scratchpad_digest = Sha3_384(scratchpad);
    Bytes final_input = DomainInput(DOMAIN_RESULT, context.seed, header_digest, nonce_bytes);
    final_input.insert(final_input.end(), context.program_digest.begin(), context.program_digest.end());
    final_input.insert(final_input.end(), context.dataset_digest.begin(), context.dataset_digest.end());
    final_input.insert(final_input.end(), encoded_registers.begin(), encoded_registers.end());
    final_input.insert(final_input.end(), scratchpad_digest.begin(), scratchpad_digest.end());
    return {Sha3_384(final_input), registers, context.program_digest, context.dataset_digest, scratchpad_digest};
}

Bytes ParseHex(std::string_view text)
{
    if (text.size() % 2 != 0) throw std::invalid_argument("hex input must have even length");
    auto digit = [](char value) -> unsigned {
        if (value >= '0' && value <= '9') return value - '0';
        if (value >= 'a' && value <= 'f') return value - 'a' + 10;
        if (value >= 'A' && value <= 'F') return value - 'A' + 10;
        throw std::invalid_argument("invalid hexadecimal input");
    };
    Bytes output;
    output.reserve(text.size() / 2);
    for (std::size_t i{0}; i < text.size(); i += 2) output.push_back(static_cast<std::uint8_t>((digit(text[i]) << 4) | digit(text[i + 1])));
    return output;
}

std::string Hex(std::span<const std::uint8_t> bytes)
{
    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (const std::uint8_t value : bytes) output << std::setw(2) << static_cast<unsigned>(value);
    return output.str();
}

std::size_t ParseSize(const char* value)
{
    const unsigned long long parsed = std::stoull(value);
    if (parsed > std::numeric_limits<std::size_t>::max()) throw std::out_of_range("size is too large");
    return static_cast<std::size_t>(parsed);
}

void PrintResult(const ExecutionResult& result)
{
    std::cout << "digest=" << Hex(result.digest) << '\n';
    std::cout << "program_digest=" << Hex(result.program_digest) << '\n';
    std::cout << "dataset_digest=" << Hex(result.dataset_digest) << '\n';
    std::cout << "scratchpad_digest=" << Hex(result.scratchpad_digest) << '\n';
    std::cout << "registers=" << std::hex << std::setfill('0');
    for (std::size_t i{0}; i < result.registers.size(); ++i) {
        if (i != 0) std::cout << ',';
        std::cout << std::setw(16) << result.registers[i];
    }
    std::cout << '\n';
}

} // namespace

int main(int argc, char* argv[])
{
    try {
        if (argc != 8) {
            std::cerr << "NON-CONSENSUS Soveroot PoW research implementation\n"
                      << "usage: powvm_cpp SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES INSTRUCTIONS PASSES\n";
            return 2;
        }
        const Bytes seed = ParseHex(argv[1]);
        const Bytes header = ParseHex(argv[2]);
        const std::uint64_t nonce = std::stoull(argv[3]);
        const Params params{ParseSize(argv[4]), ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
        PrintResult(Evaluate(PrepareEpoch(seed, params), header, nonce));
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
