// Copyright (c) 2026 The Soveroot developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or https://opensource.org/license/mit/.
//
// NON-CONSENSUS RESEARCH CODE. This executable is deliberately standalone.

#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
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

struct ExecutionTiming {
    std::int64_t input_setup_ns;
    std::int64_t scratchpad_init_ns;
    std::int64_t mix_execute_ns;
    std::int64_t finalize_ns;
};

struct SpillStats {
    std::uint64_t retained_reads{0};
    std::uint64_t retained_writes{0};
    std::uint64_t spill_reads{0};
    std::uint64_t spill_writes{0};
    std::size_t logical_retained_bytes{0};
    std::size_t spill_file_bytes{0};
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

class FullScratchpad {
public:
    explicit FullScratchpad(std::size_t bytes) : m_memory(bytes, 0) {}

    std::uint64_t Read(std::uint64_t selector)
    {
        return ReadMemory(m_memory, selector);
    }

    void Write(std::uint64_t selector, std::uint64_t value)
    {
        WriteMemory(m_memory, selector, value);
    }

    void ExportStats(SpillStats*) const {}

private:
    Bytes m_memory;
};

class StaticHalfSpillScratchpad {
public:
    StaticHalfSpillScratchpad(
        std::size_t bytes,
        const std::filesystem::path& spill_directory,
        std::uint64_t nonce)
        : m_word_count(bytes / 8), m_retained(bytes / 2, 0)
    {
        if (bytes % 16 != 0) throw std::invalid_argument("half-spill scratchpad must contain an even number of words");
        if (!std::filesystem::is_directory(spill_directory)) {
            throw std::invalid_argument("half-spill directory does not exist");
        }
        m_stats.logical_retained_bytes = m_retained.size();
        m_stats.spill_file_bytes = bytes / 2;
        m_path = spill_directory /
            ("soveroot-pow-v1-half-spill-" + std::to_string(nonce) + "-" +
             std::to_string(s_file_counter++) + ".bin");
        m_file.rdbuf()->pubsetbuf(nullptr, 0);
        m_file.open(m_path, std::ios::binary | std::ios::in | std::ios::out | std::ios::trunc);
        if (!m_file) throw std::runtime_error("unable to create half-spill backing file");
        m_file.seekp(static_cast<std::streamoff>(m_stats.spill_file_bytes - 1));
        m_file.put('\0');
        m_file.flush();
        if (!m_file) throw std::runtime_error("unable to initialize half-spill backing file");
    }

    StaticHalfSpillScratchpad(const StaticHalfSpillScratchpad&) = delete;
    StaticHalfSpillScratchpad& operator=(const StaticHalfSpillScratchpad&) = delete;

    ~StaticHalfSpillScratchpad()
    {
        m_file.close();
        std::error_code error;
        std::filesystem::remove(m_path, error);
    }

    std::uint64_t Read(std::uint64_t selector)
    {
        const std::size_t word = static_cast<std::size_t>(selector) & (m_word_count - 1);
        if ((word & 1) == 0) {
            ++m_stats.retained_reads;
            return ReadLE64(m_retained.data() + (word / 2) * 8);
        }

        ++m_stats.spill_reads;
        std::array<std::uint8_t, 8> encoded{};
        SeekRead(word / 2);
        m_file.read(reinterpret_cast<char*>(encoded.data()), encoded.size());
        if (!m_file) throw std::runtime_error("unable to read half-spill backing file");
        return ReadLE64(encoded.data());
    }

    void Write(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = static_cast<std::size_t>(selector) & (m_word_count - 1);
        if ((word & 1) == 0) {
            ++m_stats.retained_writes;
            WriteLE64(m_retained.data() + (word / 2) * 8, value);
            return;
        }

        ++m_stats.spill_writes;
        std::array<std::uint8_t, 8> encoded{};
        WriteLE64(encoded.data(), value);
        m_file.clear();
        m_file.seekp(static_cast<std::streamoff>((word / 2) * 8));
        m_file.write(reinterpret_cast<const char*>(encoded.data()), encoded.size());
        if (!m_file) throw std::runtime_error("unable to write half-spill backing file");
    }

    void ExportStats(SpillStats* output) const
    {
        if (output != nullptr) *output = m_stats;
    }

private:
    void SeekRead(std::size_t spill_word)
    {
        m_file.clear();
        m_file.seekg(static_cast<std::streamoff>(spill_word * 8));
        if (!m_file) throw std::runtime_error("unable to seek half-spill backing file");
    }

    inline static std::uint64_t s_file_counter{0};
    std::size_t m_word_count;
    Bytes m_retained;
    std::filesystem::path m_path;
    std::fstream m_file;
    SpillStats m_stats;
};

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

template <typename Scratchpad, typename... ScratchpadArgs>
ExecutionResult EvaluateWithScratchpad(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce,
    ExecutionTiming* timing,
    SpillStats* spill_stats,
    ScratchpadArgs&&... scratchpad_args)
{
    using Clock = std::chrono::steady_clock;
    Validate(context.seed, context.params);
    if (header.empty() || header.size() > MAX_HEADER_BYTES) throw std::invalid_argument("header size is outside the v1 research envelope");
    if (context.dataset.size() != context.params.dataset_bytes) throw std::invalid_argument("context dataset length is invalid");

    const auto input_started = Clock::now();
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
    const auto scratchpad_started = Clock::now();
    Scratchpad scratchpad(
        context.params.scratchpad_bytes,
        std::forward<ScratchpadArgs>(scratchpad_args)...);
    const std::size_t scratchpad_words = context.params.scratchpad_bytes / 8;
    const auto mix_started = Clock::now();

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
            const std::uint64_t first_scratch = scratchpad.Read(first_selector);
            const std::uint64_t dataset_selector =
                first_scratch ^ z ^
                std::rotl(accumulator, static_cast<int>((lane + pass) & 63)) ^
                iteration;
            const std::uint64_t dataset_word = ReadMemory(context.dataset, dataset_selector);
            const std::uint64_t second_selector =
                dataset_word ^ registers[(lane + 5) & (REGISTER_COUNT - 1)] ^
                std::rotl(first_scratch + accumulator, static_cast<int>(entry.immediate & 63));
            const std::uint64_t second_scratch = scratchpad.Read(second_selector);

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
            scratchpad.Write(word, sequential_value);
            scratchpad.Write(second_selector, dependent_value);

            registers[lane] = mixed + accumulator + first_scratch;
            const std::size_t neighbor = (lane + 2) & (REGISTER_COUNT - 1);
            registers[neighbor] ^=
                std::rotl(dataset_word + first_scratch, static_cast<int>(second_scratch & 63));
        }
    }

    const auto finalize_started = Clock::now();
    std::array<std::uint64_t, FINAL_SAMPLE_WORDS> samples{};
    std::uint64_t selector = accumulator ^ registers[0] ^ registers[4];
    for (std::size_t i{0}; i < FINAL_SAMPLE_WORDS; ++i) {
        selector =
            std::rotl(selector ^ registers[i & (REGISTER_COUNT - 1)], static_cast<int>((i + 1) & 63)) +
            0x9E3779B97F4A7C15ULL + i;
        samples[i] = scratchpad.Read(selector);
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
    ExecutionResult result{
        Sha3_384(result_input),
        registers,
        context.schedule_digest,
        context.dataset_digest,
        memory_commitment,
    };
    const auto finished = Clock::now();
    if (timing != nullptr) {
        timing->input_setup_ns =
            std::chrono::duration_cast<std::chrono::nanoseconds>(scratchpad_started - input_started).count();
        timing->scratchpad_init_ns =
            std::chrono::duration_cast<std::chrono::nanoseconds>(mix_started - scratchpad_started).count();
        timing->mix_execute_ns =
            std::chrono::duration_cast<std::chrono::nanoseconds>(finalize_started - mix_started).count();
        timing->finalize_ns =
            std::chrono::duration_cast<std::chrono::nanoseconds>(finished - finalize_started).count();
    }
    scratchpad.ExportStats(spill_stats);
    return result;
}

ExecutionResult Evaluate(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce,
    ExecutionTiming* timing = nullptr)
{
    return EvaluateWithScratchpad<FullScratchpad>(
        context, header, nonce, timing, nullptr);
}

ExecutionResult EvaluateHalfSpill(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce,
    const std::filesystem::path& spill_directory,
    ExecutionTiming* timing = nullptr,
    SpillStats* spill_stats = nullptr)
{
    return EvaluateWithScratchpad<StaticHalfSpillScratchpad>(
        context, header, nonce, timing, spill_stats, spill_directory, nonce);
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

std::string CompilerDescription()
{
#if defined(__clang__)
    return "clang-" __clang_version__;
#elif defined(__GNUC__)
    return "gcc-" __VERSION__;
#elif defined(_MSC_VER)
    return "msvc-" + std::to_string(_MSC_VER);
#else
    return "unknown";
#endif
}

struct TimingSummary {
    std::int64_t minimum;
    std::int64_t median;
    std::int64_t mean;
    std::int64_t maximum;
};

TimingSummary Summarize(const std::vector<std::int64_t>& samples)
{
    if (samples.empty()) throw std::invalid_argument("cannot summarize empty timings");
    std::vector<std::int64_t> sorted = samples;
    std::sort(sorted.begin(), sorted.end());
    const std::int64_t median = sorted.size() % 2 == 0
        ? (sorted[sorted.size() / 2 - 1] + sorted[sorted.size() / 2]) / 2
        : sorted[sorted.size() / 2];
    return {
        sorted.front(),
        median,
        std::accumulate(samples.begin(), samples.end(), std::int64_t{0}) /
            static_cast<std::int64_t>(samples.size()),
        sorted.back(),
    };
}

void PrintTimingJson(std::string_view name, const std::vector<std::int64_t>& samples, bool trailing_comma)
{
    const TimingSummary summary = Summarize(samples);
    std::cout << "    \"" << name << "\": {\"min\": " << summary.minimum
              << ", \"median\": " << summary.median << ", \"mean\": " << summary.mean
              << ", \"max\": " << summary.maximum << ", \"samples\": [";
    for (std::size_t i{0}; i < samples.size(); ++i) {
        if (i != 0) std::cout << ',';
        std::cout << samples[i];
    }
    std::cout << "]}" << (trailing_comma ? "," : "") << '\n';
}

void PrintAttemptTimingJson(const std::vector<std::int64_t>& samples)
{
    const TimingSummary summary = Summarize(samples);
    std::cout << "  \"attempt_ns\": {\"min\": " << summary.minimum
              << ", \"median\": " << summary.median << ", \"mean\": " << summary.mean
              << ", \"max\": " << summary.maximum << ", \"samples\": [";
    for (std::size_t i{0}; i < samples.size(); ++i) {
        if (i != 0) std::cout << ',';
        std::cout << samples[i];
    }
    std::cout << "]},\n";
}

void PrintBenchmark(
    const Bytes& seed,
    const Bytes& header,
    std::uint64_t first_nonce,
    std::size_t attempts,
    const Params& params,
    const std::filesystem::path* spill_directory = nullptr)
{
    if (attempts < 1 || attempts > 10000) throw std::invalid_argument("attempts must be in [1, 10000]");
    if (attempts - 1 > std::numeric_limits<std::uint64_t>::max() - first_nonce) {
        throw std::invalid_argument("nonce range exceeds uint64");
    }

    using Clock = std::chrono::steady_clock;
    const auto prepare_started = Clock::now();
    const EpochContext context = PrepareEpoch(seed, params);
    const auto prepare_ns =
        std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - prepare_started).count();

    std::vector<std::int64_t> samples;
    std::vector<std::int64_t> input_setup_samples;
    std::vector<std::int64_t> scratchpad_init_samples;
    std::vector<std::int64_t> mix_execute_samples;
    std::vector<std::int64_t> finalize_samples;
    samples.reserve(attempts);
    input_setup_samples.reserve(attempts);
    scratchpad_init_samples.reserve(attempts);
    mix_execute_samples.reserve(attempts);
    finalize_samples.reserve(attempts);
    std::uint64_t digest_xor{0};
    Bytes digest_sequence;
    digest_sequence.reserve(attempts * 48);
    SpillStats aggregate_spill_stats{};
    for (std::size_t attempt{0}; attempt < attempts; ++attempt) {
        ExecutionTiming timing{};
        SpillStats attempt_spill_stats{};
        const auto started = Clock::now();
        const ExecutionResult result = spill_directory == nullptr
            ? Evaluate(context, header, first_nonce + attempt, &timing)
            : EvaluateHalfSpill(
                  context,
                  header,
                  first_nonce + attempt,
                  *spill_directory,
                  &timing,
                  &attempt_spill_stats);
        samples.push_back(
            std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - started).count());
        input_setup_samples.push_back(timing.input_setup_ns);
        scratchpad_init_samples.push_back(timing.scratchpad_init_ns);
        mix_execute_samples.push_back(timing.mix_execute_ns);
        finalize_samples.push_back(timing.finalize_ns);
        digest_xor ^= ReadLE64(result.digest.data());
        Append(digest_sequence, result.digest);
        aggregate_spill_stats.retained_reads += attempt_spill_stats.retained_reads;
        aggregate_spill_stats.retained_writes += attempt_spill_stats.retained_writes;
        aggregate_spill_stats.spill_reads += attempt_spill_stats.spill_reads;
        aggregate_spill_stats.spill_writes += attempt_spill_stats.spill_writes;
        aggregate_spill_stats.logical_retained_bytes = attempt_spill_stats.logical_retained_bytes;
        aggregate_spill_stats.spill_file_bytes = attempt_spill_stats.spill_file_bytes;
    }
    const std::size_t working_set =
        params.dataset_bytes +
        (spill_directory == nullptr ? params.scratchpad_bytes : params.scratchpad_bytes / 2) +
        SCHEDULE_LENGTH * 9 + REGISTER_COUNT * 8;

    std::cout << "{\n"
              << "  \"format\": \""
              << (spill_directory == nullptr
                      ? "soveroot-pow-research-cpp-benchmark-v1"
                      : "soveroot-pow-research-cpp-half-spill-benchmark-v1")
              << "\",\n"
              << "  \"warning\": \"NON-CONSENSUS V1 CANDIDATE; timings do not establish memory hardness, mining economics, or specialization resistance\",\n"
              << "  \"compiler\": \"" << CompilerDescription() << "\",\n"
              << "  \"steady_clock\": true,\n"
              << "  \"scratchpad_backend\": \""
              << (spill_directory == nullptr ? "full-in-process" : "static-even-words-half-spill")
              << "\",\n"
              << "  \"attempts\": " << attempts << ",\n"
              << "  \"first_nonce\": " << first_nonce << ",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes
              << ", \"scratchpad_bytes\": " << params.scratchpad_bytes
              << ", \"passes\": " << params.passes << "},\n"
              << "  \"working_set_bytes_estimate\": " << working_set << ",\n"
              << "  \"prepare_ns\": " << prepare_ns << ",\n";
    PrintAttemptTimingJson(samples);
    if (spill_directory != nullptr) {
        std::cout << "  \"spill_stats\": {\"logical_retained_bytes\": "
                  << aggregate_spill_stats.logical_retained_bytes
                  << ", \"spill_file_bytes\": " << aggregate_spill_stats.spill_file_bytes
                  << ", \"retained_reads\": " << aggregate_spill_stats.retained_reads
                  << ", \"retained_writes\": " << aggregate_spill_stats.retained_writes
                  << ", \"spill_reads\": " << aggregate_spill_stats.spill_reads
                  << ", \"spill_writes\": " << aggregate_spill_stats.spill_writes
                  << ", \"os_page_cache_bytes\": \"unmeasured\"},\n";
    }
    std::cout << "  \"phase_ns\": {\n";
    PrintTimingJson("input_setup", input_setup_samples, true);
    PrintTimingJson("scratchpad_init", scratchpad_init_samples, true);
    PrintTimingJson("mix_execute", mix_execute_samples, true);
    PrintTimingJson("finalize", finalize_samples, false);
    std::cout << "  },\n"
              << "  \"digest_xor_64\": \"" << std::hex << std::setfill('0') << std::setw(16)
              << digest_xor << "\",\n"
              << "  \"digest_sequence_commitment\": \""
              << Hex(Sha3_384(digest_sequence)) << "\"\n"
              << "}\n";
}

} // namespace

int main(int argc, char* argv[])
{
    try {
        if (argc == 10 && std::string_view{argv[1]} == "benchmark-half-spill") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t first_nonce = std::stoull(argv[4]);
            const std::size_t attempts = ParseSize(argv[5]);
            const Params params{ParseSize(argv[6]), ParseSize(argv[7]), ParseSize(argv[8])};
            const std::filesystem::path spill_directory{argv[9]};
            PrintBenchmark(seed, header, first_nonce, attempts, params, &spill_directory);
            return 0;
        }
        if (argc == 9 && std::string_view{argv[1]} == "half-spill") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            const std::filesystem::path spill_directory{argv[8]};
            PrintResult(EvaluateHalfSpill(
                PrepareEpoch(seed, params), header, nonce, spill_directory));
            return 0;
        }
        if (argc == 9 && std::string_view{argv[1]} == "benchmark") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t first_nonce = std::stoull(argv[4]);
            const std::size_t attempts = ParseSize(argv[5]);
            const Params params{ParseSize(argv[6]), ParseSize(argv[7]), ParseSize(argv[8])};
            PrintBenchmark(seed, header, first_nonce, attempts, params);
            return 0;
        }
        if (argc != 7) {
            std::cerr << "NON-CONSENSUS Soveroot PoW v1 research implementation\n"
                      << "usage: powvm_v1_cpp SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp benchmark SEED_HEX HEADER_HEX FIRST_NONCE ATTEMPTS DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp half-spill SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES SPILL_DIRECTORY\n"
                      << "   or: powvm_v1_cpp benchmark-half-spill SEED_HEX HEADER_HEX FIRST_NONCE ATTEMPTS DATASET_BYTES SCRATCHPAD_BYTES PASSES SPILL_DIRECTORY\n";
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
