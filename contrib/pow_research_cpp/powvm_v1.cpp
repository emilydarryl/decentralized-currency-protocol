// Copyright (c) 2026 The Soveroot developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or https://opensource.org/license/mit/.
//
// NON-CONSENSUS RESEARCH CODE. This executable is deliberately standalone.

#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <span>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

using Bytes = std::vector<std::uint8_t>;

constexpr std::size_t SEED_BYTES{48};
constexpr std::size_t REGISTER_COUNT{8};
constexpr std::size_t SCHEDULE_LENGTH{64};
constexpr std::size_t FINAL_SAMPLE_WORDS{16};
constexpr std::size_t MAX_HEADER_BYTES{4096};

constexpr char DOMAIN_SCHEDULE[] = "Soveroot/PowResearch/Schedule/v1\0";
constexpr char DOMAIN_DATASET[] = "Soveroot/PowResearch/Dataset/v1\0";
constexpr char DOMAIN_REGISTERS[] = "Soveroot/PowResearch/Registers/v1\0";
constexpr char DOMAIN_COMMITMENT[] = "Soveroot/PowResearch/Commitment/v1\0";
constexpr char DOMAIN_RESULT[] = "Soveroot/PowResearch/Result/v1\0";

struct Params {
    std::size_t dataset_bytes;
    std::size_t scratchpad_bytes;
    std::size_t passes;
};

struct ScheduleEntry {
    std::uint8_t opcode;
    std::uint64_t immediate;
};

struct EpochContext {
    Bytes seed;
    Params params;
    std::array<ScheduleEntry, SCHEDULE_LENGTH> schedule;
    Bytes dataset;
    Bytes schedule_digest;
    Bytes dataset_digest;
};

struct ExecutionResult {
    Bytes digest;
    std::array<std::uint64_t, REGISTER_COUNT> registers;
    Bytes schedule_digest;
    Bytes dataset_digest;
    Bytes memory_commitment;
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
Bytes DomainBytes(const char (&domain)[N])
{
    return Bytes{
        reinterpret_cast<const std::uint8_t*>(domain),
        reinterpret_cast<const std::uint8_t*>(domain) + N - 1};
}

void Append(Bytes& output, std::span<const std::uint8_t> input)
{
    output.insert(output.end(), input.begin(), input.end());
}

bool IsPowerOfTwo(std::size_t value)
{
    return value != 0 && (value & (value - 1)) == 0;
}

void Validate(const Bytes& seed, const Params& params)
{
    if (seed.size() != SEED_BYTES) throw std::invalid_argument("seed must be exactly 48 bytes");
    if (!IsPowerOfTwo(params.dataset_bytes) || params.dataset_bytes < 64 * 1024 || params.dataset_bytes > 64 * 1024 * 1024) {
        throw std::invalid_argument("dataset_bytes is outside the v1 research envelope");
    }
    if (!IsPowerOfTwo(params.scratchpad_bytes) || params.scratchpad_bytes < 8 * 1024 || params.scratchpad_bytes > 8 * 1024 * 1024) {
        throw std::invalid_argument("scratchpad_bytes is outside the v1 research envelope");
    }
    if (params.passes < 1 || params.passes > 16) throw std::invalid_argument("invalid pass count");
}

Bytes EncodeParams(const Params& params)
{
    Bytes encoded;
    encoded.reserve(24);
    AppendLE64(encoded, params.dataset_bytes);
    AppendLE64(encoded, params.scratchpad_bytes);
    AppendLE64(encoded, params.passes);
    return encoded;
}

std::array<ScheduleEntry, SCHEDULE_LENGTH> GenerateSchedule(const Bytes& seed, const Params& params)
{
    constexpr std::size_t immediate_bytes{SCHEDULE_LENGTH * 8};
    constexpr std::size_t shuffle_bytes{(SCHEDULE_LENGTH - 1) * 2};
    Bytes input = DomainBytes(DOMAIN_SCHEDULE);
    Append(input, seed);
    const Bytes encoded_params = EncodeParams(params);
    Append(input, encoded_params);
    const Bytes raw = Shake256(input, immediate_bytes + shuffle_bytes);

    std::array<std::uint8_t, SCHEDULE_LENGTH> opcodes{};
    for (std::size_t i{0}; i < SCHEDULE_LENGTH; ++i) opcodes[i] = static_cast<std::uint8_t>(i & 7);
    std::size_t shuffle_offset{immediate_bytes};
    for (std::size_t i{SCHEDULE_LENGTH - 1}; i > 0; --i) {
        const std::uint16_t random_value =
            std::uint16_t{raw[shuffle_offset]} |
            (std::uint16_t{raw[shuffle_offset + 1]} << 8);
        shuffle_offset += 2;
        std::swap(opcodes[i], opcodes[random_value % (i + 1)]);
    }

    std::array<ScheduleEntry, SCHEDULE_LENGTH> schedule{};
    for (std::size_t i{0}; i < SCHEDULE_LENGTH; ++i) {
        schedule[i] = {opcodes[i], ReadLE64(raw.data() + i * 8)};
    }
    return schedule;
}

EpochContext PrepareEpoch(const Bytes& seed, const Params& params)
{
    Validate(seed, params);
    const auto schedule = GenerateSchedule(seed, params);
    Bytes encoded_schedule;
    encoded_schedule.reserve(SCHEDULE_LENGTH * 9);
    for (const ScheduleEntry& entry : schedule) {
        encoded_schedule.push_back(entry.opcode);
        AppendLE64(encoded_schedule, entry.immediate);
    }

    Bytes dataset_input = DomainBytes(DOMAIN_DATASET);
    Append(dataset_input, seed);
    const Bytes encoded_params = EncodeParams(params);
    Append(dataset_input, encoded_params);
    Bytes dataset = Shake256(dataset_input, params.dataset_bytes);
    return {seed, params, schedule, dataset, Sha3_384(encoded_schedule), Sha3_384(dataset)};
}

std::uint64_t ReadMemory(const Bytes& memory, std::uint64_t selector)
{
    const std::size_t word = static_cast<std::size_t>(selector) & (memory.size() / 8 - 1);
    return ReadLE64(memory.data() + word * 8);
}

void WriteMemory(Bytes& memory, std::uint64_t selector, std::uint64_t value)
{
    const std::size_t word = static_cast<std::size_t>(selector) & (memory.size() / 8 - 1);
    WriteLE64(memory.data() + word * 8, value);
}

std::uint64_t ExecuteOperation(
    std::uint8_t opcode,
    std::uint64_t x,
    std::uint64_t y,
    std::uint64_t first_scratch,
    std::uint64_t second_scratch,
    std::uint64_t dataset_word,
    std::uint64_t immediate)
{
    switch (opcode) {
    case 0:
        return x + y + dataset_word + immediate;
    case 1:
        return x ^ std::rotl(y + dataset_word, static_cast<int>(immediate & 63)) ^ first_scratch;
    case 2:
        return (x | 1) * ((dataset_word ^ second_scratch ^ immediate) | 1);
    case 3:
        return std::rotl(x ^ first_scratch ^ dataset_word, static_cast<int>((y ^ second_scratch ^ immediate) & 63));
    case 4:
        return (x + first_scratch) ^ (dataset_word + second_scratch + immediate);
    case 5:
        return std::rotl(x + dataset_word + immediate, static_cast<int>(first_scratch & 63)) * (y | 1);
    case 6:
        return (x ^ second_scratch) + std::rotl(dataset_word ^ immediate, static_cast<int>((first_scratch ^ y) & 63));
    case 7:
        return std::rotl((x | 1) * (y | 1) + first_scratch + second_scratch, static_cast<int>((dataset_word ^ immediate) & 63));
    default:
        throw std::logic_error("unreachable opcode");
    }
}

ExecutionResult Evaluate(const EpochContext& context, const Bytes& header, std::uint64_t nonce)
{
    Validate(context.seed, context.params);
    if (header.empty() || header.size() > MAX_HEADER_BYTES) throw std::invalid_argument("header size is outside the v1 research envelope");
    if (context.dataset.size() != context.params.dataset_bytes) throw std::invalid_argument("context dataset length is invalid");

    const Bytes params_bytes = EncodeParams(context.params);
    Bytes nonce_bytes;
    AppendLE64(nonce_bytes, nonce);
    const Bytes header_digest = Sha3_384(header);
    Bytes initial_input = DomainBytes(DOMAIN_REGISTERS);
    Append(initial_input, context.seed);
    Append(initial_input, header_digest);
    Append(initial_input, nonce_bytes);
    Append(initial_input, params_bytes);
    const Bytes initial_state = Shake256(initial_input, REGISTER_COUNT * 8 + 8);

    std::array<std::uint64_t, REGISTER_COUNT> registers{};
    for (std::size_t i{0}; i < REGISTER_COUNT; ++i) {
        registers[i] = ReadLE64(initial_state.data() + i * 8);
    }
    std::uint64_t accumulator = ReadLE64(initial_state.data() + REGISTER_COUNT * 8);
    Bytes scratchpad(context.params.scratchpad_bytes, 0);
    const std::size_t scratchpad_words = context.params.scratchpad_bytes / 8;

    for (std::size_t pass{0}; pass < context.params.passes; ++pass) {
        for (std::size_t word{0}; word < scratchpad_words; ++word) {
            const std::uint64_t iteration = pass * scratchpad_words + word;
            const std::size_t lane = static_cast<std::size_t>(iteration) & (REGISTER_COUNT - 1);
            const ScheduleEntry& entry = context.schedule[static_cast<std::size_t>(iteration) & (SCHEDULE_LENGTH - 1)];
            const std::uint64_t x = registers[lane];
            const std::uint64_t y = registers[(lane + 1) & (REGISTER_COUNT - 1)];
            const std::uint64_t z = registers[(lane + 3) & (REGISTER_COUNT - 1)];

            const std::uint64_t first_selector =
                x ^ std::rotl(y, static_cast<int>(iteration & 63)) ^ accumulator ^ entry.immediate;
            const std::uint64_t first_scratch = ReadMemory(scratchpad, first_selector);
            const std::uint64_t dataset_selector =
                first_scratch ^ z ^
                std::rotl(accumulator, static_cast<int>((lane + pass) & 63)) ^
                iteration;
            const std::uint64_t dataset_word = ReadMemory(context.dataset, dataset_selector);
            const std::uint64_t second_selector =
                dataset_word ^ registers[(lane + 5) & (REGISTER_COUNT - 1)] ^
                std::rotl(first_scratch + accumulator, static_cast<int>(entry.immediate & 63));
            const std::uint64_t second_scratch = ReadMemory(scratchpad, second_selector);

            const std::uint64_t mixed = ExecuteOperation(
                entry.opcode, x, y, first_scratch, second_scratch, dataset_word, entry.immediate);
            accumulator =
                std::rotl(
                    accumulator ^ mixed ^ dataset_word,
                    static_cast<int>((first_scratch ^ second_scratch ^ entry.immediate) & 63)) +
                first_scratch + entry.immediate + iteration;
            const std::uint64_t sequential_value = mixed ^ accumulator ^ second_scratch;
            const std::uint64_t dependent_value =
                second_scratch ^ std::rotl(mixed + accumulator, static_cast<int>(dataset_word & 63));
            WriteMemory(scratchpad, word, sequential_value);
            WriteMemory(scratchpad, second_selector, dependent_value);

            registers[lane] = mixed + accumulator + first_scratch;
            const std::size_t neighbor = (lane + 2) & (REGISTER_COUNT - 1);
            registers[neighbor] ^=
                std::rotl(dataset_word + first_scratch, static_cast<int>(second_scratch & 63));
        }
    }

    std::array<std::uint64_t, FINAL_SAMPLE_WORDS> samples{};
    std::uint64_t selector = accumulator ^ registers[0] ^ registers[4];
    for (std::size_t i{0}; i < FINAL_SAMPLE_WORDS; ++i) {
        selector =
            std::rotl(selector ^ registers[i & (REGISTER_COUNT - 1)], static_cast<int>((i + 1) & 63)) +
            0x9E3779B97F4A7C15ULL + i;
        samples[i] = ReadMemory(scratchpad, selector);
        selector ^= samples[i];
    }

    Bytes encoded_registers;
    encoded_registers.reserve(REGISTER_COUNT * 8);
    for (const std::uint64_t value : registers) AppendLE64(encoded_registers, value);
    Bytes encoded_accumulator;
    AppendLE64(encoded_accumulator, accumulator);
    Bytes encoded_samples;
    encoded_samples.reserve(FINAL_SAMPLE_WORDS * 8);
    for (const std::uint64_t value : samples) AppendLE64(encoded_samples, value);

    Bytes commitment_input = DomainBytes(DOMAIN_COMMITMENT);
    Append(commitment_input, params_bytes);
    Append(commitment_input, encoded_registers);
    Append(commitment_input, encoded_accumulator);
    Append(commitment_input, encoded_samples);
    const Bytes memory_commitment = Sha3_384(commitment_input);

    Bytes result_input = DomainBytes(DOMAIN_RESULT);
    Append(result_input, context.seed);
    Append(result_input, header_digest);
    Append(result_input, nonce_bytes);
    Append(result_input, params_bytes);
    Append(result_input, context.schedule_digest);
    Append(result_input, context.dataset_digest);
    Append(result_input, encoded_registers);
    Append(result_input, encoded_accumulator);
    Append(result_input, memory_commitment);
    return {
        Sha3_384(result_input),
        registers,
        context.schedule_digest,
        context.dataset_digest,
        memory_commitment,
    };
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
    for (std::size_t i{0}; i < text.size(); i += 2) {
        output.push_back(static_cast<std::uint8_t>((digit(text[i]) << 4) | digit(text[i + 1])));
    }
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
    std::cout << "schedule_digest=" << Hex(result.schedule_digest) << '\n';
    std::cout << "dataset_digest=" << Hex(result.dataset_digest) << '\n';
    std::cout << "memory_commitment=" << Hex(result.memory_commitment) << '\n';
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
        if (argc != 7) {
            std::cerr << "NON-CONSENSUS Soveroot PoW v1 research implementation\n"
                      << "usage: powvm_v1_cpp SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n";
            return 2;
        }
        const Bytes seed = ParseHex(argv[1]);
        const Bytes header = ParseHex(argv[2]);
        const std::uint64_t nonce = std::stoull(argv[3]);
        const Params params{ParseSize(argv[4]), ParseSize(argv[5]), ParseSize(argv[6])};
        PrintResult(Evaluate(PrepareEpoch(seed, params), header, nonce));
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
