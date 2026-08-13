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
#include <iterator>
#include <list>
#include <limits>
#include <numeric>
#include <set>
#include <span>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <unordered_map>
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
constexpr char DOMAIN_ACCESS_TRACE[] = "Soveroot/PowResearch/AccessTrace/v1\0";
constexpr char DOMAIN_VERSIONED_GRAPH[] = "Soveroot/PowResearch/VersionedGraph/v1\0";
constexpr char DOMAIN_BOUNDED_STATE[] = "Soveroot/PowResearch/BoundedProbeState/v1\0";
constexpr char DOMAIN_RECONSTRUCTION[] = "Soveroot/PowResearch/BoundedReconstruction/v1\0";
constexpr char DOMAIN_REPEATED_TRANSCRIPT[] = "Soveroot/PowResearch/RepeatedReconstruction/v1\0";
constexpr std::size_t BOUNDED_FIXED_STATE_RESERVE_BYTES{512};
constexpr std::size_t BOUNDED_CACHE_ENTRY_BYTES{16};
constexpr std::size_t REPLAY_NUMERATOR{5};
constexpr std::size_t REPLAY_DENOMINATOR{8};

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

struct RecomputationStats {
    std::uint64_t retained_reads{0};
    std::uint64_t retained_writes{0};
    std::uint64_t recomputed_reads{0};
    std::uint64_t discarded_writes{0};
    std::uint64_t replayed_iterations{0};
    std::size_t logical_retained_bytes{0};
    std::size_t replay_workspace_bytes{0};
    std::size_t peak_scratch_bytes{0};
};

struct MachineState {
    std::array<std::uint64_t, REGISTER_COUNT> registers{};
    std::uint64_t accumulator{0};
};

struct BoundedProbeStats {
    std::size_t budget_bytes{0};
    std::size_t fixed_state_reserve_bytes{0};
    std::size_t arena_bytes{0};
    std::size_t write_bitmap_bytes{0};
    std::size_t cache_entry_bytes{0};
    std::size_t cache_capacity{0};
    std::size_t cache_payload_bytes{0};
    std::size_t unused_arena_bytes{0};
    std::size_t admitted_bytes{0};
    std::uint64_t reads{0};
    std::uint64_t cache_hits{0};
    std::uint64_t initial_zero_reads{0};
    std::uint64_t materialized_misses{0};
    std::uint64_t writes{0};
    std::uint64_t evictions{0};
};

struct BoundedProbeResult {
    bool exact_complete{false};
    std::uint64_t completed_iterations{0};
    std::uint8_t miss_consumer_kind{0};
    std::uint64_t miss_consumer{0};
    std::uint8_t miss_slot{0};
    std::uint64_t miss_word{0};
    Bytes state_commitment;
    ExecutionResult execution_result{};
    BoundedProbeStats stats{};
};

struct BoundedReconstructionStats {
    std::size_t budget_bytes{0};
    std::size_t fixed_state_reserve_bytes{0};
    std::size_t arena_bytes{0};
    std::size_t write_bitmap_bytes{0};
    std::size_t cache_entry_bytes{0};
    std::size_t primary_cache_capacity{0};
    std::size_t primary_cache_bytes{0};
    std::size_t replay_capacity{0};
    std::size_t replay_workspace_bytes{0};
    std::size_t unused_arena_bytes{0};
    std::size_t admitted_bytes{0};
    std::uint64_t canonical_reads{0};
    std::uint64_t cache_hits{0};
    std::uint64_t initial_zero_reads{0};
    std::uint64_t materialized_misses{0};
    std::uint64_t writes{0};
    std::uint64_t evictions{0};
    std::uint64_t replay_peak_entries{0};
    std::uint64_t replay_hash_probes{0};
};

struct BoundedReconstructionResult {
    std::string status{"refused_before_reconstruction"};
    std::uint64_t completed_iterations{0};
    std::uint64_t reconstructed_misses{0};
    std::uint64_t replayed_iterations{0};
    std::uint64_t reconstruction_consumer{0};
    std::uint8_t reconstruction_slot{0};
    std::uint64_t reconstruction_word{0};
    std::uint64_t reconstruction_value{0};
    Bytes reconstruction_commitment;
    bool replay_state_matched{false};
    std::uint64_t refusal_consumer{0};
    std::uint8_t refusal_slot{0};
    std::uint64_t refusal_word{0};
    Bytes refusal_state_commitment;
    ExecutionResult execution_result{};
    BoundedReconstructionStats stats{};
};

struct ReconstructionBoundary {
    std::uint64_t consumer{0};
    std::uint8_t slot{0};
    std::uint64_t word{0};
    std::uint64_t value{0};
    std::uint64_t replayed_iterations{0};
    std::uint64_t replay_peak_entries{0};
    std::uint64_t replay_hash_probes{0};
    Bytes commitment;
};

struct ReplayExhaustionBoundary {
    std::uint64_t consumer{0};
    std::uint8_t slot{0};
    std::uint64_t word{0};
    std::uint64_t replay_completed_iterations{0};
    std::uint64_t replay_peak_entries{0};
    std::uint64_t replay_hash_probes{0};
    Bytes state_commitment;
};

struct RepeatedReconstructionResult {
    std::string status{"refused_replay_workspace_exhausted"};
    std::uint64_t completed_iterations{0};
    std::uint64_t reconstruction_attempts{0};
    std::uint64_t reconstructed_misses{0};
    std::uint64_t successful_replayed_iterations{0};
    std::uint64_t attempted_replay_iterations{0};
    std::uint64_t cumulative_replay_hash_probes{0};
    std::uint64_t max_replay_peak_entries{0};
    std::uint64_t max_reconstruction_depth{0};
    bool all_replay_states_matched{true};
    Bytes transcript_commitment;
    bool has_first{false};
    ReconstructionBoundary first_reconstruction{};
    ReconstructionBoundary last_reconstruction{};
    bool has_exhaustion{false};
    ReplayExhaustionBoundary exhaustion{};
    ExecutionResult execution_result{};
    BoundedReconstructionStats stats{};
};

struct TraceEvent {
    std::size_t word;
    bool is_write;
};

struct CacheTraceStats {
    std::size_t capacity_words;
    std::uint64_t materialized_read_hits;
    std::uint64_t materialized_read_misses;
    std::uint64_t evictions;
};

struct BudgetCacheScenario {
    std::size_t budget_bytes;
    std::size_t entry_bytes;
    CacheTraceStats lru;
    CacheTraceStats offline_optimal;
};

struct TraceSummary {
    std::uint64_t reads{0};
    std::uint64_t writes{0};
    std::uint64_t initial_zero_reads{0};
    std::uint64_t materialized_reads{0};
    std::size_t distinct_read_words{0};
    std::size_t distinct_written_words{0};
    std::size_t maximum_live_values{0};
    Bytes trace_commitment;
    CacheTraceStats half_capacity{};
    CacheTraceStats quarter_capacity{};
    BudgetCacheScenario compact_half_budget{};
    BudgetCacheScenario conservative_half_budget{};
};

struct GraphLayoutEstimate {
    std::size_t read_edge_bytes;
    std::size_t write_version_bytes;
    std::size_t version_table_entry_bytes;
    std::size_t graph_records_bytes;
    std::size_t version_table_bytes;
    std::size_t logical_model_bytes;
};

struct VersionedGraphSummary {
    std::size_t mix_iterations{0};
    std::uint64_t read_edges{0};
    std::uint64_t write_versions{0};
    std::uint64_t initial_zero_edges{0};
    std::uint64_t materialized_edges{0};
    std::uint64_t overwrite_edges{0};
    std::size_t canonical_header_bytes{0};
    std::size_t canonical_read_edge_bytes{0};
    std::size_t canonical_write_version_bytes{0};
    std::size_t canonical_encoded_bytes{0};
    Bytes graph_commitment;
    GraphLayoutEstimate packed{};
    GraphLayoutEstimate conservative{};
};

class TraceRecorder {
public:
    explicit TraceRecorder(std::size_t word_count) : m_word_count(word_count)
    {
        m_events.reserve(word_count * 4);
    }

    void Read(std::size_t word) { m_events.push_back({word, false}); }
    void Write(std::size_t word) { m_events.push_back({word, true}); }

    TraceSummary Summarize() const;
    VersionedGraphSummary SummarizeVersionedGraph() const;

private:
    CacheTraceStats SimulateCache(std::size_t capacity_words) const;
    CacheTraceStats SimulateOfflineOptimal(std::size_t capacity_words) const;

    std::size_t m_word_count;
    std::vector<TraceEvent> m_events;
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

CacheTraceStats TraceRecorder::SimulateCache(std::size_t capacity_words) const
{
    if (capacity_words == 0 || capacity_words > m_word_count) {
        throw std::invalid_argument("trace cache capacity is invalid");
    }
    std::vector<bool> written(m_word_count, false);
    std::list<std::size_t> recent;
    std::unordered_map<std::size_t, std::list<std::size_t>::iterator> cached;
    cached.reserve(capacity_words);
    CacheTraceStats stats{capacity_words, 0, 0, 0};

    auto touch = [&](std::size_t word) {
        const auto found = cached.find(word);
        if (found != cached.end()) {
            recent.erase(found->second);
            recent.push_front(word);
            found->second = recent.begin();
            return;
        }
        if (cached.size() == capacity_words) {
            cached.erase(recent.back());
            recent.pop_back();
            ++stats.evictions;
        }
        recent.push_front(word);
        cached.emplace(word, recent.begin());
    };

    for (const TraceEvent& event : m_events) {
        if (event.is_write) {
            written[event.word] = true;
            touch(event.word);
        } else if (written[event.word]) {
            if (cached.contains(event.word)) {
                ++stats.materialized_read_hits;
            } else {
                ++stats.materialized_read_misses;
            }
            touch(event.word);
        }
    }
    return stats;
}

CacheTraceStats TraceRecorder::SimulateOfflineOptimal(std::size_t capacity_words) const
{
    if (capacity_words == 0 || capacity_words > m_word_count) {
        throw std::invalid_argument("trace cache capacity is invalid");
    }
    struct Access {
        std::size_t word;
        bool is_write;
    };
    constexpr std::size_t NEVER = std::numeric_limits<std::size_t>::max();
    std::vector<bool> written(m_word_count, false);
    std::vector<Access> accesses;
    accesses.reserve(m_events.size());
    for (const TraceEvent& event : m_events) {
        if (event.is_write) {
            written[event.word] = true;
            accesses.push_back({event.word, true});
        } else if (written[event.word]) {
            accesses.push_back({event.word, false});
        }
    }

    std::vector<std::size_t> next_use(accesses.size(), NEVER);
    std::vector<std::size_t> next_read(m_word_count, NEVER);
    for (std::size_t index{accesses.size()}; index > 0; --index) {
        const Access& access = accesses[index - 1];
        next_use[index - 1] = next_read[access.word];
        if (access.is_write) {
            next_read[access.word] = NEVER;
        } else {
            next_read[access.word] = index - 1;
        }
    }

    std::unordered_map<std::size_t, std::size_t> cached;
    cached.reserve(capacity_words);
    std::set<std::pair<std::size_t, std::size_t>> by_next_use;
    CacheTraceStats stats{capacity_words, 0, 0, 0};
    for (std::size_t index{0}; index < accesses.size(); ++index) {
        const Access& access = accesses[index];
        const auto found = cached.find(access.word);
        if (!access.is_write) {
            if (found == cached.end()) {
                ++stats.materialized_read_misses;
            } else {
                ++stats.materialized_read_hits;
            }
        }
        if (found != cached.end()) {
            by_next_use.erase({found->second, access.word});
            cached.erase(found);
        }

        const std::size_t next = next_use[index];
        if (next == NEVER) continue;
        if (cached.size() == capacity_words) {
            const auto farthest = std::prev(by_next_use.end());
            if (farthest->first <= next) continue;
            cached.erase(farthest->second);
            by_next_use.erase(farthest);
            ++stats.evictions;
        }
        cached.emplace(access.word, next);
        by_next_use.emplace(next, access.word);
    }
    return stats;
}

TraceSummary TraceRecorder::Summarize() const
{
    TraceSummary summary{};
    std::vector<bool> read_words(m_word_count, false);
    std::vector<bool> written_words(m_word_count, false);
    std::vector<bool> materialized_read(m_events.size(), false);
    Bytes encoded_trace = DomainBytes(DOMAIN_ACCESS_TRACE);
    encoded_trace.reserve(encoded_trace.size() + m_events.size() * 9);

    for (std::size_t index{0}; index < m_events.size(); ++index) {
        const TraceEvent& event = m_events[index];
        encoded_trace.push_back(event.is_write ? 1 : 0);
        AppendLE64(encoded_trace, event.word);
        if (event.is_write) {
            ++summary.writes;
            written_words[event.word] = true;
        } else {
            ++summary.reads;
            read_words[event.word] = true;
            if (written_words[event.word]) {
                ++summary.materialized_reads;
                materialized_read[index] = true;
            } else {
                ++summary.initial_zero_reads;
            }
        }
    }
    summary.distinct_read_words = static_cast<std::size_t>(
        std::count(read_words.begin(), read_words.end(), true));
    summary.distinct_written_words = static_cast<std::size_t>(
        std::count(written_words.begin(), written_words.end(), true));

    std::vector<bool> live(m_word_count, false);
    std::size_t live_count{0};
    for (std::size_t index{m_events.size()}; index > 0; --index) {
        const TraceEvent& event = m_events[index - 1];
        if (event.is_write) {
            if (live[event.word]) {
                live[event.word] = false;
                --live_count;
            }
        } else if (materialized_read[index - 1] && !live[event.word]) {
            live[event.word] = true;
            ++live_count;
            summary.maximum_live_values = std::max(summary.maximum_live_values, live_count);
        }
    }

    summary.trace_commitment = Sha3_384(encoded_trace);
    summary.half_capacity = SimulateCache(m_word_count / 2);
    summary.quarter_capacity = SimulateCache(m_word_count / 4);
    const std::size_t half_budget_bytes = m_word_count * 8 / 2;
    auto budget_scenario = [&](std::size_t entry_bytes) {
        const std::size_t capacity = std::max<std::size_t>(1, half_budget_bytes / entry_bytes);
        return BudgetCacheScenario{
            half_budget_bytes,
            entry_bytes,
            SimulateCache(capacity),
            SimulateOfflineOptimal(capacity),
        };
    };
    summary.compact_half_budget = budget_scenario(16);
    summary.conservative_half_budget = budget_scenario(24);
    return summary;
}

VersionedGraphSummary TraceRecorder::SummarizeVersionedGraph() const
{
    constexpr std::size_t FINAL_READS{FINAL_SAMPLE_WORDS};
    constexpr std::size_t EVENTS_PER_ITERATION{4};
    constexpr std::size_t CANONICAL_READ_EDGE_BYTES{1 + 1 + 8 + 1 + 8 + 8};
    constexpr std::size_t CANONICAL_WRITE_VERSION_BYTES{1 + 8 + 8 + 1 + 8 + 8};
    constexpr std::size_t PACKED_READ_EDGE_BYTES{16};
    constexpr std::size_t PACKED_WRITE_VERSION_BYTES{24};
    constexpr std::size_t PACKED_VERSION_TABLE_ENTRY_BYTES{4};
    constexpr std::size_t CONSERVATIVE_READ_EDGE_BYTES{40};
    constexpr std::size_t CONSERVATIVE_WRITE_VERSION_BYTES{40};
    constexpr std::size_t CONSERVATIVE_VERSION_TABLE_ENTRY_BYTES{8};

    if (m_events.size() < FINAL_READS ||
        (m_events.size() - FINAL_READS) % EVENTS_PER_ITERATION != 0) {
        throw std::logic_error("trace does not match the v1 iteration/finalization shape");
    }

    VersionedGraphSummary summary{};
    summary.mix_iterations = (m_events.size() - FINAL_READS) / EVENTS_PER_ITERATION;
    std::vector<std::uint64_t> current_version(m_word_count, 0);
    Bytes encoded = DomainBytes(DOMAIN_VERSIONED_GRAPH);
    AppendLE64(encoded, m_word_count);
    AppendLE64(encoded, summary.mix_iterations);
    AppendLE64(encoded, FINAL_READS);
    summary.canonical_header_bytes = encoded.size();

    auto record_read = [&](const TraceEvent& event, std::uint8_t consumer_kind,
                           std::uint64_t consumer, std::uint8_t slot) {
        if (event.is_write) throw std::logic_error("expected a read trace event");
        const std::uint64_t source_version = current_version[event.word];
        encoded.push_back(0);
        encoded.push_back(consumer_kind);
        AppendLE64(encoded, consumer);
        encoded.push_back(slot);
        AppendLE64(encoded, event.word);
        AppendLE64(encoded, source_version);
        ++summary.read_edges;
        if (source_version == 0) {
            ++summary.initial_zero_edges;
        } else {
            ++summary.materialized_edges;
        }
    };
    auto record_write = [&](const TraceEvent& event, std::uint64_t iteration, std::uint8_t slot) {
        if (!event.is_write) throw std::logic_error("expected a write trace event");
        const std::uint64_t previous_version = current_version[event.word];
        const std::uint64_t version = ++summary.write_versions;
        encoded.push_back(1);
        AppendLE64(encoded, version);
        AppendLE64(encoded, iteration);
        encoded.push_back(slot);
        AppendLE64(encoded, event.word);
        AppendLE64(encoded, previous_version);
        current_version[event.word] = version;
        if (previous_version != 0) ++summary.overwrite_edges;
    };

    for (std::size_t iteration{0}; iteration < summary.mix_iterations; ++iteration) {
        const std::size_t offset = iteration * EVENTS_PER_ITERATION;
        record_read(m_events[offset], 0, iteration, 0);
        record_read(m_events[offset + 1], 0, iteration, 1);
        record_write(m_events[offset + 2], iteration, 0);
        record_write(m_events[offset + 3], iteration, 1);
    }
    const std::size_t final_offset = summary.mix_iterations * EVENTS_PER_ITERATION;
    for (std::size_t sample{0}; sample < FINAL_READS; ++sample) {
        record_read(m_events[final_offset + sample], 1, sample, 0);
    }

    summary.canonical_read_edge_bytes = CANONICAL_READ_EDGE_BYTES;
    summary.canonical_write_version_bytes = CANONICAL_WRITE_VERSION_BYTES;
    summary.canonical_encoded_bytes = encoded.size();
    const std::size_t expected_encoded_bytes =
        summary.canonical_header_bytes +
        summary.read_edges * CANONICAL_READ_EDGE_BYTES +
        summary.write_versions * CANONICAL_WRITE_VERSION_BYTES;
    if (summary.canonical_encoded_bytes != expected_encoded_bytes) {
        throw std::logic_error("versioned graph byte accounting mismatch");
    }
    summary.graph_commitment = Sha3_384(encoded);

    auto estimate_layout = [&](std::size_t read_edge_bytes,
                               std::size_t write_version_bytes,
                               std::size_t version_table_entry_bytes) {
        const std::size_t graph_records_bytes =
            summary.read_edges * read_edge_bytes +
            summary.write_versions * write_version_bytes;
        const std::size_t version_table_bytes = m_word_count * version_table_entry_bytes;
        return GraphLayoutEstimate{
            read_edge_bytes,
            write_version_bytes,
            version_table_entry_bytes,
            graph_records_bytes,
            version_table_bytes,
            graph_records_bytes + version_table_bytes,
        };
    };
    summary.packed = estimate_layout(
        PACKED_READ_EDGE_BYTES,
        PACKED_WRITE_VERSION_BYTES,
        PACKED_VERSION_TABLE_ENTRY_BYTES);
    summary.conservative = estimate_layout(
        CONSERVATIVE_READ_EDGE_BYTES,
        CONSERVATIVE_WRITE_VERSION_BYTES,
        CONSERVATIVE_VERSION_TABLE_ENTRY_BYTES);
    return summary;
}

class FullScratchpad {
public:
    explicit FullScratchpad(std::size_t bytes, TraceRecorder* trace = nullptr)
        : m_memory(bytes, 0), m_trace(trace)
    {
    }

    std::uint64_t Read(std::uint64_t selector)
    {
        if (m_trace != nullptr) m_trace->Read(Word(selector));
        return ReadMemory(m_memory, selector);
    }

    void Write(std::uint64_t selector, std::uint64_t value)
    {
        if (m_trace != nullptr) m_trace->Write(Word(selector));
        WriteMemory(m_memory, selector, value);
    }

    void ExportStats(SpillStats*) const {}
    void ExportRecomputationStats(RecomputationStats*) const {}

private:
    std::size_t Word(std::uint64_t selector) const
    {
        return static_cast<std::size_t>(selector) & (m_memory.size() / 8 - 1);
    }

    Bytes m_memory;
    TraceRecorder* m_trace;
};

class BoundedReadMiss final : public std::runtime_error {
public:
    BoundedReadMiss(
        std::uint8_t consumer_kind,
        std::uint64_t consumer,
        std::uint8_t slot,
        std::uint64_t word)
        : std::runtime_error("bounded probe encountered a materialized cache miss"),
          consumer_kind(consumer_kind),
          consumer(consumer),
          slot(slot),
          word(word)
    {
    }

    std::uint8_t consumer_kind;
    std::uint64_t consumer;
    std::uint8_t slot;
    std::uint64_t word;
};

class BoundedArenaScratchpad {
public:
    BoundedArenaScratchpad(
        std::size_t scratchpad_bytes,
        std::size_t budget_bytes,
        std::uint64_t total_iterations)
        : m_word_count(scratchpad_bytes / 8),
          m_total_iterations(total_iterations)
    {
        m_stats.budget_bytes = budget_bytes;
        m_stats.fixed_state_reserve_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES;
        m_stats.write_bitmap_bytes = (m_word_count + 7) / 8;
        m_stats.cache_entry_bytes = BOUNDED_CACHE_ENTRY_BYTES;
        if (budget_bytes <= BOUNDED_FIXED_STATE_RESERVE_BYTES) {
            throw std::invalid_argument("bounded-probe budget cannot hold the fixed reserve");
        }
        m_stats.arena_bytes = budget_bytes - BOUNDED_FIXED_STATE_RESERVE_BYTES;
        if (m_stats.arena_bytes <= m_stats.write_bitmap_bytes) {
            throw std::invalid_argument("bounded-probe budget cannot hold the write bitmap and one cache entry");
        }
        m_stats.cache_capacity =
            (m_stats.arena_bytes - m_stats.write_bitmap_bytes) / BOUNDED_CACHE_ENTRY_BYTES;
        if (m_stats.cache_capacity == 0) {
            throw std::invalid_argument("bounded-probe budget cannot hold one cache entry");
        }
        m_stats.cache_payload_bytes = m_stats.cache_capacity * BOUNDED_CACHE_ENTRY_BYTES;
        m_stats.unused_arena_bytes =
            m_stats.arena_bytes - m_stats.write_bitmap_bytes - m_stats.cache_payload_bytes;
        m_stats.admitted_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES + m_stats.arena_bytes;
        m_cache_offset = m_stats.write_bitmap_bytes;
        m_arena.resize(m_stats.arena_bytes, 0);
        for (std::size_t slot{0}; slot < m_stats.cache_capacity; ++slot) {
            WriteLE64(m_arena.data() + EntryOffset(slot), std::numeric_limits<std::uint64_t>::max());
        }
    }

    std::uint64_t Read(std::uint64_t selector)
    {
        const std::size_t word = static_cast<std::size_t>(selector) & (m_word_count - 1);
        const std::uint64_t read_ordinal = m_stats.reads++;
        const std::size_t entry_offset = EntryOffset(word % m_stats.cache_capacity);
        const std::uint64_t tag = ReadLE64(m_arena.data() + entry_offset);
        if (tag == word) {
            ++m_stats.cache_hits;
            return ReadLE64(m_arena.data() + entry_offset + 8);
        }
        if (!WasWritten(word)) {
            ++m_stats.initial_zero_reads;
            return 0;
        }

        ++m_stats.materialized_misses;
        if (read_ordinal < m_total_iterations * 2) {
            throw BoundedReadMiss{
                0,
                read_ordinal / 2,
                static_cast<std::uint8_t>(read_ordinal & 1),
                word};
        }
        throw BoundedReadMiss{1, read_ordinal - m_total_iterations * 2, 0, word};
    }

    void Write(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = static_cast<std::size_t>(selector) & (m_word_count - 1);
        const std::size_t entry_offset = EntryOffset(word % m_stats.cache_capacity);
        const std::uint64_t previous = ReadLE64(m_arena.data() + entry_offset);
        if (previous != std::numeric_limits<std::uint64_t>::max() && previous != word) {
            ++m_stats.evictions;
        }
        WriteLE64(m_arena.data() + entry_offset, word);
        WriteLE64(m_arena.data() + entry_offset + 8, value);
        MarkWritten(word);
        ++m_stats.writes;
    }

    const BoundedProbeStats& Stats() const { return m_stats; }

private:
    std::size_t EntryOffset(std::size_t slot) const
    {
        return m_cache_offset + slot * BOUNDED_CACHE_ENTRY_BYTES;
    }

    bool WasWritten(std::size_t word) const
    {
        return (m_arena[word / 8] & (std::uint8_t{1} << (word & 7))) != 0;
    }

    void MarkWritten(std::size_t word)
    {
        m_arena[word / 8] |= std::uint8_t{1} << (word & 7);
    }

    std::size_t m_word_count;
    std::uint64_t m_total_iterations;
    std::size_t m_cache_offset{0};
    Bytes m_arena;
    BoundedProbeStats m_stats;
};

class ReplayWorkspaceExhausted final : public std::runtime_error {
public:
    ReplayWorkspaceExhausted()
        : std::runtime_error("bounded sparse replay workspace is full")
    {
    }
};

class BoundedReconstructionArena {
public:
    BoundedReconstructionArena(std::size_t scratchpad_bytes, std::size_t budget_bytes)
        : m_word_count(scratchpad_bytes / 8)
    {
        m_stats.budget_bytes = budget_bytes;
        m_stats.fixed_state_reserve_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES;
        m_stats.write_bitmap_bytes = (m_word_count + 7) / 8;
        m_stats.cache_entry_bytes = BOUNDED_CACHE_ENTRY_BYTES;
        if (budget_bytes <= BOUNDED_FIXED_STATE_RESERVE_BYTES) {
            throw std::invalid_argument("bounded reconstruction budget cannot hold the fixed reserve");
        }
        m_stats.arena_bytes = budget_bytes - BOUNDED_FIXED_STATE_RESERVE_BYTES;
        if (m_stats.arena_bytes <= m_stats.write_bitmap_bytes + BOUNDED_CACHE_ENTRY_BYTES * 2) {
            throw std::invalid_argument("bounded reconstruction budget cannot hold primary and replay entries");
        }
        const std::size_t total_slots =
            (m_stats.arena_bytes - m_stats.write_bitmap_bytes) / BOUNDED_CACHE_ENTRY_BYTES;
        m_stats.replay_capacity = total_slots * REPLAY_NUMERATOR / REPLAY_DENOMINATOR;
        m_stats.primary_cache_capacity = total_slots - m_stats.replay_capacity;
        if (m_stats.replay_capacity == 0 || m_stats.primary_cache_capacity == 0) {
            throw std::invalid_argument("bounded reconstruction cannot split primary and replay capacities");
        }
        m_stats.primary_cache_bytes = m_stats.primary_cache_capacity * BOUNDED_CACHE_ENTRY_BYTES;
        m_stats.replay_workspace_bytes = m_stats.replay_capacity * BOUNDED_CACHE_ENTRY_BYTES;
        m_stats.unused_arena_bytes =
            m_stats.arena_bytes - m_stats.write_bitmap_bytes -
            m_stats.primary_cache_bytes - m_stats.replay_workspace_bytes;
        m_stats.admitted_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES + m_stats.arena_bytes;
        m_primary_offset = m_stats.write_bitmap_bytes;
        m_replay_offset = m_primary_offset + m_stats.primary_cache_bytes;
        m_arena.resize(m_stats.arena_bytes, 0);
        for (std::size_t slot{0}; slot < m_stats.primary_cache_capacity; ++slot) {
            WriteLE64(m_arena.data() + PrimaryEntryOffset(slot), EmptyTag());
        }
    }

    void SetConsumer(std::uint64_t consumer)
    {
        m_consumer = consumer;
        m_slot = 0;
    }

    std::uint64_t Read(std::uint64_t selector)
    {
        const std::size_t word = Word(selector);
        const std::uint8_t slot = m_slot++;
        ++m_stats.canonical_reads;
        const std::size_t offset = PrimaryEntryOffset(word % m_stats.primary_cache_capacity);
        if (ReadLE64(m_arena.data() + offset) == word) {
            ++m_stats.cache_hits;
            return ReadLE64(m_arena.data() + offset + 8);
        }
        if (!WasWritten(word)) {
            ++m_stats.initial_zero_reads;
            return 0;
        }
        ++m_stats.materialized_misses;
        throw BoundedReadMiss{0, m_consumer, slot, word};
    }

    void Write(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = Word(selector);
        StorePrimary(word, value, true);
        MarkWritten(word);
        ++m_stats.writes;
    }

    void RetainReconstructed(std::uint64_t word, std::uint64_t value)
    {
        StorePrimary(static_cast<std::size_t>(word), value, true);
    }

    void ResetReplay()
    {
        m_replay_distinct = 0;
        m_stats.replay_peak_entries = 0;
        m_stats.replay_hash_probes = 0;
        for (std::size_t slot{0}; slot < m_stats.replay_capacity; ++slot) {
            WriteLE64(m_arena.data() + ReplayEntryOffset(slot), EmptyTag());
        }
    }

    std::uint64_t ReplayRead(std::uint64_t selector)
    {
        const std::size_t word = Word(selector);
        const auto [found, offset] = FindReplay(word, false);
        return found ? ReadLE64(m_arena.data() + offset + 8) : 0;
    }

    std::uint64_t ReplayReadExact(std::uint64_t word)
    {
        const auto [found, offset] = FindReplay(static_cast<std::size_t>(word), false);
        if (!found) {
            throw std::logic_error("materialized word is absent from the exact replay state");
        }
        return ReadLE64(m_arena.data() + offset + 8);
    }

    void ReplayWrite(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = Word(selector);
        const auto [found, offset] = FindReplay(word, true);
        if (!found && ReadLE64(m_arena.data() + offset) == EmptyTag()) {
            ++m_replay_distinct;
            m_stats.replay_peak_entries =
                std::max<std::uint64_t>(m_stats.replay_peak_entries, m_replay_distinct);
        }
        WriteLE64(m_arena.data() + offset, word);
        WriteLE64(m_arena.data() + offset + 8, value);
    }

    const BoundedReconstructionStats& Stats() const { return m_stats; }

private:
    static constexpr std::uint64_t EmptyTag()
    {
        return std::numeric_limits<std::uint64_t>::max();
    }

    std::size_t Word(std::uint64_t selector) const
    {
        return static_cast<std::size_t>(selector) & (m_word_count - 1);
    }

    std::size_t PrimaryEntryOffset(std::size_t slot) const
    {
        return m_primary_offset + slot * BOUNDED_CACHE_ENTRY_BYTES;
    }

    std::size_t ReplayEntryOffset(std::size_t slot) const
    {
        return m_replay_offset + slot * BOUNDED_CACHE_ENTRY_BYTES;
    }

    bool WasWritten(std::size_t word) const
    {
        return (m_arena[word / 8] & (std::uint8_t{1} << (word & 7))) != 0;
    }

    void MarkWritten(std::size_t word)
    {
        m_arena[word / 8] |= std::uint8_t{1} << (word & 7);
    }

    void StorePrimary(std::size_t word, std::uint64_t value, bool count_eviction)
    {
        const std::size_t offset = PrimaryEntryOffset(word % m_stats.primary_cache_capacity);
        const std::uint64_t previous = ReadLE64(m_arena.data() + offset);
        if (count_eviction && previous != EmptyTag() && previous != word) {
            ++m_stats.evictions;
        }
        WriteLE64(m_arena.data() + offset, word);
        WriteLE64(m_arena.data() + offset + 8, value);
    }

    std::pair<bool, std::size_t> FindReplay(std::size_t word, bool for_write)
    {
        constexpr std::uint64_t HASH_MULTIPLIER{0x9E3779B97F4A7C15ULL};
        const std::size_t start =
            static_cast<std::size_t>(
                static_cast<std::uint64_t>(word) * HASH_MULTIPLIER % m_stats.replay_capacity);
        for (std::size_t distance{0}; distance < m_stats.replay_capacity; ++distance) {
            ++m_stats.replay_hash_probes;
            const std::size_t offset =
                ReplayEntryOffset((start + distance) % m_stats.replay_capacity);
            const std::uint64_t tag = ReadLE64(m_arena.data() + offset);
            if (tag == word) return {true, offset};
            if (tag == EmptyTag()) {
                return {false, for_write ? offset : std::size_t{0}};
            }
        }
        if (for_write) throw ReplayWorkspaceExhausted{};
        return {false, 0};
    }

    std::size_t m_word_count;
    std::size_t m_primary_offset{0};
    std::size_t m_replay_offset{0};
    std::uint64_t m_consumer{0};
    std::uint8_t m_slot{0};
    std::uint64_t m_replay_distinct{0};
    Bytes m_arena;
    BoundedReconstructionStats m_stats;
};

class SparseReplayView {
public:
    explicit SparseReplayView(BoundedReconstructionArena& arena) : m_arena(arena) {}

    std::uint64_t Read(std::uint64_t selector) { return m_arena.ReplayRead(selector); }
    void Write(std::uint64_t selector, std::uint64_t value) { m_arena.ReplayWrite(selector, value); }

private:
    BoundedReconstructionArena& m_arena;
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

    void ExportRecomputationStats(RecomputationStats*) const {}

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

MachineState InitializeMachineState(
    const EpochContext& context,
    std::span<const std::uint8_t> header_digest,
    std::span<const std::uint8_t> nonce_bytes,
    std::span<const std::uint8_t> params_bytes)
{
    Bytes initial_input = DomainBytes(DOMAIN_REGISTERS);
    Append(initial_input, context.seed);
    Append(initial_input, header_digest);
    Append(initial_input, nonce_bytes);
    Append(initial_input, params_bytes);
    const Bytes initial_state = Shake256(initial_input, REGISTER_COUNT * 8 + 8);

    MachineState state{};
    for (std::size_t i{0}; i < REGISTER_COUNT; ++i) {
        state.registers[i] = ReadLE64(initial_state.data() + i * 8);
    }
    state.accumulator = ReadLE64(initial_state.data() + REGISTER_COUNT * 8);
    return state;
}

template <typename Scratchpad>
void ExecuteMixIteration(
    const EpochContext& context,
    Scratchpad& scratchpad,
    MachineState& state,
    std::uint64_t iteration)
{
    const std::size_t scratchpad_words = context.params.scratchpad_bytes / 8;
    const std::size_t pass = static_cast<std::size_t>(iteration) / scratchpad_words;
    const std::size_t word = static_cast<std::size_t>(iteration) & (scratchpad_words - 1);
    const std::size_t lane = static_cast<std::size_t>(iteration) & (REGISTER_COUNT - 1);
    const ScheduleEntry& entry = context.schedule[static_cast<std::size_t>(iteration) & (SCHEDULE_LENGTH - 1)];
    const std::uint64_t x = state.registers[lane];
    const std::uint64_t y = state.registers[(lane + 1) & (REGISTER_COUNT - 1)];
    const std::uint64_t z = state.registers[(lane + 3) & (REGISTER_COUNT - 1)];

    const std::uint64_t first_selector =
        x ^ std::rotl(y, static_cast<int>(iteration & 63)) ^ state.accumulator ^ entry.immediate;
    const std::uint64_t first_scratch = scratchpad.Read(first_selector);
    const std::uint64_t dataset_selector =
        first_scratch ^ z ^
        std::rotl(state.accumulator, static_cast<int>((lane + pass) & 63)) ^
        iteration;
    const std::uint64_t dataset_word = ReadMemory(context.dataset, dataset_selector);
    const std::uint64_t second_selector =
        dataset_word ^ state.registers[(lane + 5) & (REGISTER_COUNT - 1)] ^
        std::rotl(first_scratch + state.accumulator, static_cast<int>(entry.immediate & 63));
    const std::uint64_t second_scratch = scratchpad.Read(second_selector);

    const std::uint64_t mixed = ExecuteOperation(
        entry.opcode, x, y, first_scratch, second_scratch, dataset_word, entry.immediate);
    state.accumulator =
        std::rotl(
            state.accumulator ^ mixed ^ dataset_word,
            static_cast<int>((first_scratch ^ second_scratch ^ entry.immediate) & 63)) +
        first_scratch + entry.immediate + iteration;
    const std::uint64_t sequential_value = mixed ^ state.accumulator ^ second_scratch;
    const std::uint64_t dependent_value =
        second_scratch ^ std::rotl(mixed + state.accumulator, static_cast<int>(dataset_word & 63));
    scratchpad.Write(word, sequential_value);
    scratchpad.Write(second_selector, dependent_value);

    state.registers[lane] = mixed + state.accumulator + first_scratch;
    const std::size_t neighbor = (lane + 2) & (REGISTER_COUNT - 1);
    state.registers[neighbor] ^=
        std::rotl(dataset_word + first_scratch, static_cast<int>(second_scratch & 63));
}

std::uint64_t ReplayScratchWord(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce,
    std::uint64_t completed_iterations,
    std::uint64_t selector)
{
    const Bytes params_bytes = EncodeParams(context.params);
    Bytes nonce_bytes;
    AppendLE64(nonce_bytes, nonce);
    const Bytes header_digest = Sha3_384(header);
    MachineState state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
    FullScratchpad replay(context.params.scratchpad_bytes);
    for (std::uint64_t iteration{0}; iteration < completed_iterations; ++iteration) {
        ExecuteMixIteration(context, replay, state, iteration);
    }
    return replay.Read(selector);
}

class StaticHalfRecomputeScratchpad {
public:
    StaticHalfRecomputeScratchpad(
        std::size_t bytes,
        const EpochContext& context,
        const Bytes& header,
        std::uint64_t nonce)
        : m_word_count(bytes / 8),
          m_total_iterations(context.params.passes * m_word_count),
          m_retained(bytes / 2, 0),
          m_context(context),
          m_header(header),
          m_nonce(nonce)
    {
        if (bytes % 16 != 0) {
            throw std::invalid_argument("half-recompute scratchpad must contain an even number of words");
        }
        m_stats.logical_retained_bytes = m_retained.size();
        m_stats.replay_workspace_bytes = bytes;
        m_stats.peak_scratch_bytes = bytes + m_retained.size();
    }

    std::uint64_t Read(std::uint64_t selector)
    {
        const std::size_t word = static_cast<std::size_t>(selector) & (m_word_count - 1);
        const std::uint64_t completed_iterations =
            std::min<std::uint64_t>(m_reads / 2, m_total_iterations);
        ++m_reads;
        if ((word & 1) == 0) {
            ++m_stats.retained_reads;
            return ReadLE64(m_retained.data() + (word / 2) * 8);
        }

        ++m_stats.recomputed_reads;
        m_stats.replayed_iterations += completed_iterations;
        return ReplayScratchWord(m_context, m_header, m_nonce, completed_iterations, word);
    }

    void Write(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = static_cast<std::size_t>(selector) & (m_word_count - 1);
        if ((word & 1) == 0) {
            ++m_stats.retained_writes;
            WriteLE64(m_retained.data() + (word / 2) * 8, value);
        } else {
            ++m_stats.discarded_writes;
        }
    }

    void ExportStats(SpillStats*) const {}

    void ExportRecomputationStats(RecomputationStats* output) const
    {
        if (output != nullptr) *output = m_stats;
    }

private:
    std::size_t m_word_count;
    std::uint64_t m_total_iterations;
    std::uint64_t m_reads{0};
    Bytes m_retained;
    const EpochContext& m_context;
    const Bytes& m_header;
    std::uint64_t m_nonce;
    RecomputationStats m_stats;
};

template <typename Scratchpad, typename... ScratchpadArgs>
ExecutionResult EvaluateWithScratchpad(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce,
    ExecutionTiming* timing,
    SpillStats* spill_stats,
    RecomputationStats* recomputation_stats,
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
    MachineState state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
    const auto scratchpad_started = Clock::now();
    Scratchpad scratchpad(
        context.params.scratchpad_bytes,
        std::forward<ScratchpadArgs>(scratchpad_args)...);
    const std::size_t scratchpad_words = context.params.scratchpad_bytes / 8;
    const auto mix_started = Clock::now();

    for (std::size_t pass{0}; pass < context.params.passes; ++pass) {
        for (std::size_t word{0}; word < scratchpad_words; ++word) {
            const std::uint64_t iteration = pass * scratchpad_words + word;
            ExecuteMixIteration(context, scratchpad, state, iteration);
        }
    }

    const auto finalize_started = Clock::now();
    std::array<std::uint64_t, FINAL_SAMPLE_WORDS> samples{};
    std::uint64_t selector = state.accumulator ^ state.registers[0] ^ state.registers[4];
    for (std::size_t i{0}; i < FINAL_SAMPLE_WORDS; ++i) {
        selector =
            std::rotl(selector ^ state.registers[i & (REGISTER_COUNT - 1)], static_cast<int>((i + 1) & 63)) +
            0x9E3779B97F4A7C15ULL + i;
        samples[i] = scratchpad.Read(selector);
        selector ^= samples[i];
    }

    Bytes encoded_registers;
    encoded_registers.reserve(REGISTER_COUNT * 8);
    for (const std::uint64_t value : state.registers) AppendLE64(encoded_registers, value);
    Bytes encoded_accumulator;
    AppendLE64(encoded_accumulator, state.accumulator);
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
        state.registers,
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
    scratchpad.ExportRecomputationStats(recomputation_stats);
    return result;
}

ExecutionResult Evaluate(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce,
    ExecutionTiming* timing = nullptr)
{
    return EvaluateWithScratchpad<FullScratchpad>(
        context, header, nonce, timing, nullptr, nullptr);
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
        context, header, nonce, timing, spill_stats, nullptr, spill_directory, nonce);
}

ExecutionResult EvaluateHalfRecompute(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce,
    ExecutionTiming* timing = nullptr,
    RecomputationStats* recomputation_stats = nullptr)
{
    return EvaluateWithScratchpad<StaticHalfRecomputeScratchpad>(
        context,
        header,
        nonce,
        timing,
        nullptr,
        recomputation_stats,
        context,
        header,
        nonce);
}

BoundedProbeResult ProbeBounded(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce)
{
    Validate(context.seed, context.params);
    if (header.empty() || header.size() > MAX_HEADER_BYTES) {
        throw std::invalid_argument("header size is outside the v1 research envelope");
    }
    const Bytes params_bytes = EncodeParams(context.params);
    Bytes nonce_bytes;
    AppendLE64(nonce_bytes, nonce);
    const Bytes header_digest = Sha3_384(header);
    MachineState state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
    const std::size_t scratchpad_words = context.params.scratchpad_bytes / 8;
    const std::uint64_t total_iterations = context.params.passes * scratchpad_words;
    BoundedArenaScratchpad scratchpad(
        context.params.scratchpad_bytes,
        context.params.scratchpad_bytes / 2,
        total_iterations);
    BoundedProbeResult probe{};

    try {
        for (std::uint64_t iteration{0}; iteration < total_iterations; ++iteration) {
            ExecuteMixIteration(context, scratchpad, state, iteration);
            ++probe.completed_iterations;
        }

        std::array<std::uint64_t, FINAL_SAMPLE_WORDS> samples{};
        std::uint64_t selector = state.accumulator ^ state.registers[0] ^ state.registers[4];
        for (std::size_t i{0}; i < FINAL_SAMPLE_WORDS; ++i) {
            selector =
                std::rotl(selector ^ state.registers[i & (REGISTER_COUNT - 1)], static_cast<int>((i + 1) & 63)) +
                0x9E3779B97F4A7C15ULL + i;
            samples[i] = scratchpad.Read(selector);
            selector ^= samples[i];
        }

        Bytes encoded_registers;
        encoded_registers.reserve(REGISTER_COUNT * 8);
        for (const std::uint64_t value : state.registers) AppendLE64(encoded_registers, value);
        Bytes encoded_accumulator;
        AppendLE64(encoded_accumulator, state.accumulator);
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
        probe.exact_complete = true;
        probe.execution_result = {
            Sha3_384(result_input),
            state.registers,
            context.schedule_digest,
            context.dataset_digest,
            memory_commitment,
        };
    } catch (const BoundedReadMiss& miss) {
        probe.miss_consumer_kind = miss.consumer_kind;
        probe.miss_consumer = miss.consumer;
        probe.miss_slot = miss.slot;
        probe.miss_word = miss.word;
        Bytes encoded = DomainBytes(DOMAIN_BOUNDED_STATE);
        Append(encoded, context.seed);
        Append(encoded, header_digest);
        Append(encoded, nonce_bytes);
        Append(encoded, params_bytes);
        AppendLE64(encoded, miss.consumer);
        encoded.push_back(miss.slot);
        AppendLE64(encoded, miss.word);
        encoded.push_back(miss.consumer_kind);
        for (const std::uint64_t value : state.registers) AppendLE64(encoded, value);
        AppendLE64(encoded, state.accumulator);
        probe.state_commitment = Sha3_384(encoded);
    }
    probe.stats = scratchpad.Stats();
    return probe;
}

BoundedReconstructionResult ProbeFirstReconstruction(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce)
{
    Validate(context.seed, context.params);
    if (header.empty() || header.size() > MAX_HEADER_BYTES) {
        throw std::invalid_argument("header size is outside the v1 research envelope");
    }
    const Bytes params_bytes = EncodeParams(context.params);
    Bytes nonce_bytes;
    AppendLE64(nonce_bytes, nonce);
    const Bytes header_digest = Sha3_384(header);
    MachineState state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
    const std::size_t scratchpad_words = context.params.scratchpad_bytes / 8;
    const std::uint64_t total_iterations = context.params.passes * scratchpad_words;
    BoundedReconstructionArena arena(
        context.params.scratchpad_bytes,
        context.params.scratchpad_bytes / 2);
    BoundedReconstructionResult result{};

    auto boundary_commitment = [&](bool reconstruction,
                                   const BoundedReadMiss& miss,
                                   const std::uint64_t* value) {
        Bytes encoded = reconstruction
            ? DomainBytes(DOMAIN_RECONSTRUCTION)
            : DomainBytes(DOMAIN_BOUNDED_STATE);
        Append(encoded, context.seed);
        Append(encoded, header_digest);
        Append(encoded, nonce_bytes);
        Append(encoded, params_bytes);
        AppendLE64(encoded, miss.consumer);
        encoded.push_back(miss.slot);
        AppendLE64(encoded, miss.word);
        for (const std::uint64_t item : state.registers) AppendLE64(encoded, item);
        AppendLE64(encoded, state.accumulator);
        if (value != nullptr) AppendLE64(encoded, *value);
        return Sha3_384(encoded);
    };

    auto refuse = [&](const BoundedReadMiss& miss) {
        result.status = "refused_after_one_reconstruction";
        result.refusal_consumer = miss.consumer;
        result.refusal_slot = miss.slot;
        result.refusal_word = miss.word;
        result.refusal_state_commitment = boundary_commitment(false, miss, nullptr);
        result.stats = arena.Stats();
    };

    auto reconstruct = [&](const BoundedReadMiss& miss) {
        if (miss.consumer >= total_iterations) {
            throw ReplayWorkspaceExhausted{};
        }
        arena.ResetReplay();
        SparseReplayView replay{arena};
        MachineState replay_state = InitializeMachineState(
            context, header_digest, nonce_bytes, params_bytes);
        for (std::uint64_t iteration{0}; iteration < miss.consumer; ++iteration) {
            ExecuteMixIteration(context, replay, replay_state, iteration);
        }
        result.replayed_iterations += miss.consumer;
        result.replay_state_matched =
            replay_state.registers == state.registers &&
            replay_state.accumulator == state.accumulator;
        if (!result.replay_state_matched) {
            throw std::logic_error("replayed machine state does not match the live prefix");
        }
        const std::uint64_t value = arena.ReplayReadExact(miss.word);
        result.reconstructed_misses = 1;
        result.reconstruction_consumer = miss.consumer;
        result.reconstruction_slot = miss.slot;
        result.reconstruction_word = miss.word;
        result.reconstruction_value = value;
        result.reconstruction_commitment = boundary_commitment(true, miss, &value);
        arena.RetainReconstructed(miss.word, value);
    };

    try {
        for (std::uint64_t iteration{0}; iteration < total_iterations; ++iteration) {
            while (true) {
                arena.SetConsumer(iteration);
                try {
                    ExecuteMixIteration(context, arena, state, iteration);
                    break;
                } catch (const BoundedReadMiss& miss) {
                    if (result.reconstructed_misses != 0) {
                        refuse(miss);
                        return result;
                    }
                    reconstruct(miss);
                }
            }
            ++result.completed_iterations;
        }

        std::array<std::uint64_t, FINAL_SAMPLE_WORDS> samples{};
        std::uint64_t selector = state.accumulator ^ state.registers[0] ^ state.registers[4];
        for (std::size_t i{0}; i < FINAL_SAMPLE_WORDS; ++i) {
            selector =
                std::rotl(selector ^ state.registers[i & (REGISTER_COUNT - 1)], static_cast<int>((i + 1) & 63)) +
                0x9E3779B97F4A7C15ULL + i;
            while (true) {
                arena.SetConsumer(total_iterations + i);
                try {
                    samples[i] = arena.Read(selector);
                    break;
                } catch (const BoundedReadMiss& miss) {
                    if (result.reconstructed_misses != 0) {
                        refuse(miss);
                        return result;
                    }
                    reconstruct(miss);
                }
            }
            selector ^= samples[i];
        }

        Bytes encoded_registers;
        encoded_registers.reserve(REGISTER_COUNT * 8);
        for (const std::uint64_t value : state.registers) AppendLE64(encoded_registers, value);
        Bytes encoded_accumulator;
        AppendLE64(encoded_accumulator, state.accumulator);
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
        result.status = "exact_complete";
        result.execution_result = {
            Sha3_384(result_input),
            state.registers,
            context.schedule_digest,
            context.dataset_digest,
            memory_commitment,
        };
    } catch (const ReplayWorkspaceExhausted&) {
        result.status = "refused_replay_workspace_exhausted";
    }
    result.stats = arena.Stats();
    return result;
}

RepeatedReconstructionResult ProbeRepeatedReconstruction(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce)
{
    Validate(context.seed, context.params);
    if (header.empty() || header.size() > MAX_HEADER_BYTES) {
        throw std::invalid_argument("header size is outside the v1 research envelope");
    }
    const Bytes params_bytes = EncodeParams(context.params);
    Bytes nonce_bytes;
    AppendLE64(nonce_bytes, nonce);
    const Bytes header_digest = Sha3_384(header);
    MachineState state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
    const std::size_t scratchpad_words = context.params.scratchpad_bytes / 8;
    const std::uint64_t total_iterations = context.params.passes * scratchpad_words;
    BoundedReconstructionArena arena(
        context.params.scratchpad_bytes,
        context.params.scratchpad_bytes / 2);
    RepeatedReconstructionResult result{};
    Bytes transcript_input = DomainBytes(DOMAIN_REPEATED_TRANSCRIPT);

    auto boundary_commitment = [&](const BoundedReadMiss& miss,
                                   const std::uint64_t* value) {
        Bytes encoded = DomainBytes(DOMAIN_RECONSTRUCTION);
        Append(encoded, context.seed);
        Append(encoded, header_digest);
        Append(encoded, nonce_bytes);
        Append(encoded, params_bytes);
        AppendLE64(encoded, miss.consumer);
        encoded.push_back(miss.slot);
        AppendLE64(encoded, miss.word);
        for (const std::uint64_t item : state.registers) AppendLE64(encoded, item);
        AppendLE64(encoded, state.accumulator);
        if (value != nullptr) AppendLE64(encoded, *value);
        return Sha3_384(encoded);
    };

    auto reconstruct = [&](const BoundedReadMiss& miss) {
        ++result.reconstruction_attempts;
        result.max_reconstruction_depth = 1;
        arena.ResetReplay();
        SparseReplayView replay{arena};
        MachineState replay_state = InitializeMachineState(
            context, header_digest, nonce_bytes, params_bytes);
        const std::uint64_t replay_limit = std::min(miss.consumer, total_iterations);
        std::uint64_t replay_completed{0};
        try {
            for (std::uint64_t iteration{0}; iteration < replay_limit; ++iteration) {
                ExecuteMixIteration(context, replay, replay_state, iteration);
                ++replay_completed;
            }
        } catch (const ReplayWorkspaceExhausted&) {
            const BoundedReconstructionStats& stats = arena.Stats();
            result.attempted_replay_iterations += replay_completed;
            result.cumulative_replay_hash_probes += stats.replay_hash_probes;
            result.max_replay_peak_entries = std::max(
                result.max_replay_peak_entries, stats.replay_peak_entries);
            result.has_exhaustion = true;
            result.exhaustion = {
                miss.consumer,
                miss.slot,
                miss.word,
                replay_completed,
                stats.replay_peak_entries,
                stats.replay_hash_probes,
                boundary_commitment(miss, nullptr),
            };
            return false;
        }
        result.attempted_replay_iterations += replay_completed;
        result.successful_replayed_iterations += replay_completed;
        result.all_replay_states_matched =
            result.all_replay_states_matched &&
            replay_state.registers == state.registers &&
            replay_state.accumulator == state.accumulator;
        if (!result.all_replay_states_matched) {
            throw std::logic_error("replayed machine state does not match the live prefix");
        }
        const std::uint64_t value = arena.ReplayReadExact(miss.word);
        const BoundedReconstructionStats& stats = arena.Stats();
        result.cumulative_replay_hash_probes += stats.replay_hash_probes;
        result.max_replay_peak_entries = std::max(
            result.max_replay_peak_entries, stats.replay_peak_entries);
        ReconstructionBoundary boundary{
            miss.consumer,
            miss.slot,
            miss.word,
            value,
            replay_completed,
            stats.replay_peak_entries,
            stats.replay_hash_probes,
            boundary_commitment(miss, &value),
        };
        Append(transcript_input, boundary.commitment);
        if (!result.has_first) {
            result.has_first = true;
            result.first_reconstruction = boundary;
        }
        result.last_reconstruction = boundary;
        ++result.reconstructed_misses;
        arena.RetainReconstructed(miss.word, value);
        return true;
    };

    bool stopped{false};
    for (std::uint64_t iteration{0}; iteration < total_iterations; ++iteration) {
        while (true) {
            arena.SetConsumer(iteration);
            try {
                ExecuteMixIteration(context, arena, state, iteration);
                break;
            } catch (const BoundedReadMiss& miss) {
                if (!reconstruct(miss)) {
                    stopped = true;
                    break;
                }
            }
        }
        if (stopped) break;
        ++result.completed_iterations;
    }

    std::array<std::uint64_t, FINAL_SAMPLE_WORDS> samples{};
    if (!stopped) {
        std::uint64_t selector = state.accumulator ^ state.registers[0] ^ state.registers[4];
        for (std::size_t i{0}; i < FINAL_SAMPLE_WORDS; ++i) {
            selector =
                std::rotl(selector ^ state.registers[i & (REGISTER_COUNT - 1)], static_cast<int>((i + 1) & 63)) +
                0x9E3779B97F4A7C15ULL + i;
            while (true) {
                arena.SetConsumer(total_iterations + i);
                try {
                    samples[i] = arena.Read(selector);
                    break;
                } catch (const BoundedReadMiss& miss) {
                    if (!reconstruct(miss)) {
                        stopped = true;
                        break;
                    }
                }
            }
            if (stopped) break;
            selector ^= samples[i];
        }
    }

    if (!stopped) {
        Bytes encoded_registers;
        encoded_registers.reserve(REGISTER_COUNT * 8);
        for (const std::uint64_t value : state.registers) AppendLE64(encoded_registers, value);
        Bytes encoded_accumulator;
        AppendLE64(encoded_accumulator, state.accumulator);
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
        result.status = "exact_complete";
        result.execution_result = {
            Sha3_384(result_input),
            state.registers,
            context.schedule_digest,
            context.dataset_digest,
            memory_commitment,
        };
    }
    result.transcript_commitment = Sha3_384(transcript_input);
    result.stats = arena.Stats();
    return result;
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

void PrintBoundedProbe(
    const Bytes& seed,
    const Bytes& header,
    std::uint64_t nonce,
    const Params& params)
{
    const BoundedProbeResult probe = ProbeBounded(PrepareEpoch(seed, params), header, nonce);
    const BoundedProbeStats& stats = probe.stats;
    std::cout << "{\n"
              << "  \"format\": \"soveroot-pow-v1-online-bounded-probe-v0\",\n"
              << "  \"warning\": \"NON-CONSENSUS FAIL-CLOSED PREFIX PROBE; not an exact reduced-memory evaluator or gate result\",\n"
              << "  \"status\": \"" << (probe.exact_complete ? "exact_complete" : "refused_materialized_miss") << "\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes
              << ", \"scratchpad_bytes\": " << params.scratchpad_bytes
              << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"layout\": {\"budget_bytes\": " << stats.budget_bytes
              << ", \"fixed_state_reserve_bytes\": " << stats.fixed_state_reserve_bytes
              << ", \"arena_bytes\": " << stats.arena_bytes
              << ", \"write_bitmap_bytes\": " << stats.write_bitmap_bytes
              << ", \"cache_entry_bytes\": " << stats.cache_entry_bytes
              << ", \"cache_capacity\": " << stats.cache_capacity
              << ", \"cache_payload_bytes\": " << stats.cache_payload_bytes
              << ", \"unused_arena_bytes\": " << stats.unused_arena_bytes
              << ", \"admitted_bytes\": " << stats.admitted_bytes << "},\n"
              << "  \"completed_iterations\": " << probe.completed_iterations << ",\n"
              << "  \"reads\": " << stats.reads << ",\n"
              << "  \"cache_hits\": " << stats.cache_hits << ",\n"
              << "  \"initial_zero_reads\": " << stats.initial_zero_reads << ",\n"
              << "  \"materialized_misses\": " << stats.materialized_misses << ",\n"
              << "  \"writes\": " << stats.writes << ",\n"
              << "  \"evictions\": " << stats.evictions << ",\n";
    if (probe.exact_complete) {
        std::cout << "  \"miss\": null,\n"
                  << "  \"state_commitment\": null,\n"
                  << "  \"digest\": \"" << Hex(probe.execution_result.digest) << "\",\n"
                  << "  \"memory_commitment\": \"" << Hex(probe.execution_result.memory_commitment) << "\"\n";
    } else {
        std::cout << "  \"miss\": {\"consumer_kind\": " << static_cast<unsigned>(probe.miss_consumer_kind)
                  << ", \"consumer\": " << probe.miss_consumer
                  << ", \"slot\": " << static_cast<unsigned>(probe.miss_slot)
                  << ", \"word\": " << probe.miss_word << "},\n"
                  << "  \"state_commitment\": \"" << Hex(probe.state_commitment) << "\",\n"
                  << "  \"digest\": null,\n"
                  << "  \"memory_commitment\": null\n";
    }
    std::cout << "}\n";
}

void PrintBoundedReconstruction(
    const Bytes& seed,
    const Bytes& header,
    std::uint64_t nonce,
    const Params& params)
{
    const BoundedReconstructionResult result =
        ProbeFirstReconstruction(PrepareEpoch(seed, params), header, nonce);
    const BoundedReconstructionStats& stats = result.stats;
    std::cout << "{\n"
              << "  \"format\": \"soveroot-pow-v1-bounded-first-reconstruction-v0\",\n"
              << "  \"warning\": \"NON-CONSENSUS ONE-MISS RECONSTRUCTION; no completed proof, throughput, or gate result\",\n"
              << "  \"status\": \"" << result.status << "\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes
              << ", \"scratchpad_bytes\": " << params.scratchpad_bytes
              << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"layout\": {\"budget_bytes\": " << stats.budget_bytes
              << ", \"fixed_state_reserve_bytes\": " << stats.fixed_state_reserve_bytes
              << ", \"arena_bytes\": " << stats.arena_bytes
              << ", \"write_bitmap_bytes\": " << stats.write_bitmap_bytes
              << ", \"cache_entry_bytes\": " << stats.cache_entry_bytes
              << ", \"primary_cache_capacity\": " << stats.primary_cache_capacity
              << ", \"primary_cache_bytes\": " << stats.primary_cache_bytes
              << ", \"replay_capacity\": " << stats.replay_capacity
              << ", \"replay_workspace_bytes\": " << stats.replay_workspace_bytes
              << ", \"unused_arena_bytes\": " << stats.unused_arena_bytes
              << ", \"admitted_bytes\": " << stats.admitted_bytes << "},\n"
              << "  \"completed_iterations\": " << result.completed_iterations << ",\n"
              << "  \"canonical_reads\": " << stats.canonical_reads << ",\n"
              << "  \"cache_hits\": " << stats.cache_hits << ",\n"
              << "  \"initial_zero_reads\": " << stats.initial_zero_reads << ",\n"
              << "  \"materialized_misses\": " << stats.materialized_misses << ",\n"
              << "  \"writes\": " << stats.writes << ",\n"
              << "  \"evictions\": " << stats.evictions << ",\n"
              << "  \"reconstructed_misses\": " << result.reconstructed_misses << ",\n"
              << "  \"replayed_iterations\": " << result.replayed_iterations << ",\n"
              << "  \"replay_peak_entries\": " << stats.replay_peak_entries << ",\n"
              << "  \"replay_hash_probes\": " << stats.replay_hash_probes << ",\n";
    if (result.reconstructed_misses != 0) {
        std::cout << "  \"reconstruction\": {\"consumer\": " << result.reconstruction_consumer
                  << ", \"slot\": " << static_cast<unsigned>(result.reconstruction_slot)
                  << ", \"word\": " << result.reconstruction_word
                  << ", \"value\": " << result.reconstruction_value
                  << ", \"commitment\": \"" << Hex(result.reconstruction_commitment) << "\"},\n";
    } else {
        std::cout << "  \"reconstruction\": null,\n";
    }
    std::cout << "  \"replay_state_matched\": "
              << (result.replay_state_matched ? "true" : "false") << ",\n";
    if (!result.refusal_state_commitment.empty()) {
        std::cout << "  \"refusal\": {\"consumer\": " << result.refusal_consumer
                  << ", \"slot\": " << static_cast<unsigned>(result.refusal_slot)
                  << ", \"word\": " << result.refusal_word
                  << ", \"state_commitment\": \"" << Hex(result.refusal_state_commitment) << "\"},\n";
    } else {
        std::cout << "  \"refusal\": null,\n";
    }
    if (result.status == "exact_complete") {
        std::cout << "  \"digest\": \"" << Hex(result.execution_result.digest) << "\",\n"
                  << "  \"memory_commitment\": \"" << Hex(result.execution_result.memory_commitment) << "\"\n";
    } else {
        std::cout << "  \"digest\": null,\n"
                  << "  \"memory_commitment\": null\n";
    }
    std::cout << "}\n";
}

void PrintRepeatedReconstruction(
    const Bytes& seed,
    const Bytes& header,
    std::uint64_t nonce,
    const Params& params)
{
    const RepeatedReconstructionResult result =
        ProbeRepeatedReconstruction(PrepareEpoch(seed, params), header, nonce);
    const BoundedReconstructionStats& stats = result.stats;
    auto print_boundary = [](const ReconstructionBoundary& boundary) {
        std::cout << "{\"consumer\": " << boundary.consumer
                  << ", \"slot\": " << static_cast<unsigned>(boundary.slot)
                  << ", \"word\": " << boundary.word
                  << ", \"value\": " << boundary.value
                  << ", \"replayed_iterations\": " << boundary.replayed_iterations
                  << ", \"replay_peak_entries\": " << boundary.replay_peak_entries
                  << ", \"replay_hash_probes\": " << boundary.replay_hash_probes
                  << ", \"commitment\": \"" << Hex(boundary.commitment) << "\"}";
    };
    std::cout << "{\n"
              << "  \"format\": \"soveroot-pow-v1-bounded-repeated-reconstruction-v0\",\n"
              << "  \"warning\": \"NON-CONSENSUS REPEATED RECONSTRUCTION; no completed proof, throughput, or gate result\",\n"
              << "  \"status\": \"" << result.status << "\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes
              << ", \"scratchpad_bytes\": " << params.scratchpad_bytes
              << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"layout\": {\"budget_bytes\": " << stats.budget_bytes
              << ", \"fixed_state_reserve_bytes\": " << stats.fixed_state_reserve_bytes
              << ", \"arena_bytes\": " << stats.arena_bytes
              << ", \"write_bitmap_bytes\": " << stats.write_bitmap_bytes
              << ", \"cache_entry_bytes\": " << stats.cache_entry_bytes
              << ", \"primary_cache_capacity\": " << stats.primary_cache_capacity
              << ", \"primary_cache_bytes\": " << stats.primary_cache_bytes
              << ", \"replay_capacity\": " << stats.replay_capacity
              << ", \"replay_workspace_bytes\": " << stats.replay_workspace_bytes
              << ", \"unused_arena_bytes\": " << stats.unused_arena_bytes
              << ", \"admitted_bytes\": " << stats.admitted_bytes << "},\n"
              << "  \"completed_iterations\": " << result.completed_iterations << ",\n"
              << "  \"canonical_reads\": " << stats.canonical_reads << ",\n"
              << "  \"cache_hits\": " << stats.cache_hits << ",\n"
              << "  \"initial_zero_reads\": " << stats.initial_zero_reads << ",\n"
              << "  \"materialized_misses\": " << stats.materialized_misses << ",\n"
              << "  \"writes\": " << stats.writes << ",\n"
              << "  \"evictions\": " << stats.evictions << ",\n"
              << "  \"reconstruction_attempts\": " << result.reconstruction_attempts << ",\n"
              << "  \"reconstructed_misses\": " << result.reconstructed_misses << ",\n"
              << "  \"successful_replayed_iterations\": " << result.successful_replayed_iterations << ",\n"
              << "  \"attempted_replay_iterations\": " << result.attempted_replay_iterations << ",\n"
              << "  \"cumulative_replay_hash_probes\": " << result.cumulative_replay_hash_probes << ",\n"
              << "  \"max_replay_peak_entries\": " << result.max_replay_peak_entries << ",\n"
              << "  \"max_reconstruction_depth\": " << result.max_reconstruction_depth << ",\n"
              << "  \"all_replay_states_matched\": "
              << (result.all_replay_states_matched ? "true" : "false") << ",\n"
              << "  \"transcript_commitment\": \"" << Hex(result.transcript_commitment) << "\",\n"
              << "  \"first_reconstruction\": ";
    if (result.has_first) print_boundary(result.first_reconstruction);
    else std::cout << "null";
    std::cout << ",\n  \"last_reconstruction\": ";
    if (result.has_first) print_boundary(result.last_reconstruction);
    else std::cout << "null";
    std::cout << ",\n  \"exhaustion\": ";
    if (result.has_exhaustion) {
        const ReplayExhaustionBoundary& boundary = result.exhaustion;
        std::cout << "{\"consumer\": " << boundary.consumer
                  << ", \"slot\": " << static_cast<unsigned>(boundary.slot)
                  << ", \"word\": " << boundary.word
                  << ", \"replay_completed_iterations\": " << boundary.replay_completed_iterations
                  << ", \"replay_peak_entries\": " << boundary.replay_peak_entries
                  << ", \"replay_hash_probes\": " << boundary.replay_hash_probes
                  << ", \"state_commitment\": \"" << Hex(boundary.state_commitment) << "\"}";
    } else {
        std::cout << "null";
    }
    if (result.status == "exact_complete") {
        std::cout << ",\n  \"digest\": \"" << Hex(result.execution_result.digest) << "\",\n"
                  << "  \"memory_commitment\": \"" << Hex(result.execution_result.memory_commitment) << "\"\n";
    } else {
        std::cout << ",\n  \"digest\": null,\n"
                  << "  \"memory_commitment\": null\n";
    }
    std::cout << "}\n";
}

void PrintTrace(
    const Bytes& seed,
    const Bytes& header,
    std::uint64_t nonce,
    const Params& params)
{
    const EpochContext context = PrepareEpoch(seed, params);
    TraceRecorder recorder(params.scratchpad_bytes / 8);
    const ExecutionResult result = EvaluateWithScratchpad<FullScratchpad>(
        context, header, nonce, nullptr, nullptr, nullptr, &recorder);
    const TraceSummary trace = recorder.Summarize();
    auto print_cache = [](std::string_view name, const CacheTraceStats& cache, bool comma) {
        std::cout << "    \"" << name << "\": {\"capacity_words\": " << cache.capacity_words
                  << ", \"materialized_read_hits\": " << cache.materialized_read_hits
                  << ", \"materialized_read_misses\": " << cache.materialized_read_misses
                  << ", \"evictions\": " << cache.evictions << "}"
                  << (comma ? "," : "") << '\n';
    };
    auto print_budget_cache = [](std::string_view name, const BudgetCacheScenario& scenario, bool comma) {
        auto fields = [](const CacheTraceStats& stats) {
            std::ostringstream output;
            output << "{\"capacity_words\": " << stats.capacity_words
                   << ", \"materialized_read_hits\": " << stats.materialized_read_hits
                   << ", \"materialized_read_misses\": " << stats.materialized_read_misses
                   << ", \"evictions\": " << stats.evictions << "}";
            return output.str();
        };
        std::cout << "    \"" << name << "\": {\"budget_bytes\": " << scenario.budget_bytes
                  << ", \"entry_bytes\": " << scenario.entry_bytes
                  << ", \"lru\": " << fields(scenario.lru)
                  << ", \"offline_optimal\": " << fields(scenario.offline_optimal) << "}"
                  << (comma ? "," : "") << '\n';
    };

    std::cout << "{\n"
              << "  \"format\": \"soveroot-pow-v1-access-trace-v0\",\n"
              << "  \"warning\": \"NON-CONSENSUS OBSERVATIONAL TRACE; this is not a bounded-memory attack or a gate result\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes
              << ", \"scratchpad_bytes\": " << params.scratchpad_bytes
              << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"digest\": \"" << Hex(result.digest) << "\",\n"
              << "  \"memory_commitment\": \"" << Hex(result.memory_commitment) << "\",\n"
              << "  \"trace\": {\n"
              << "    \"trace_commitment\": \"" << Hex(trace.trace_commitment) << "\",\n"
              << "    \"reads\": " << trace.reads << ",\n"
              << "    \"writes\": " << trace.writes << ",\n"
              << "    \"initial_zero_reads\": " << trace.initial_zero_reads << ",\n"
              << "    \"materialized_reads\": " << trace.materialized_reads << ",\n"
              << "    \"distinct_read_words\": " << trace.distinct_read_words << ",\n"
              << "    \"distinct_written_words\": " << trace.distinct_written_words << ",\n"
              << "    \"maximum_live_values\": " << trace.maximum_live_values << ",\n"
              << "    \"cache_simulations\": {\n";
    print_cache("half_capacity_lru", trace.half_capacity, true);
    print_cache("quarter_capacity_lru", trace.quarter_capacity, true);
    print_budget_cache("compact_half_budget", trace.compact_half_budget, true);
    print_budget_cache("conservative_half_budget", trace.conservative_half_budget, false);
    std::cout << "    }\n"
              << "  }\n"
              << "}\n";
}

void PrintVersionedGraph(
    const Bytes& seed,
    const Bytes& header,
    std::uint64_t nonce,
    const Params& params)
{
    const EpochContext context = PrepareEpoch(seed, params);
    TraceRecorder recorder(params.scratchpad_bytes / 8);
    const ExecutionResult result = EvaluateWithScratchpad<FullScratchpad>(
        context, header, nonce, nullptr, nullptr, nullptr, &recorder);
    const VersionedGraphSummary graph = recorder.SummarizeVersionedGraph();
    auto print_layout = [](std::string_view name, const GraphLayoutEstimate& layout, bool comma) {
        std::cout << "      \"" << name << "\": {"
                  << "\"read_edge_bytes\": " << layout.read_edge_bytes
                  << ", \"write_version_bytes\": " << layout.write_version_bytes
                  << ", \"version_table_entry_bytes\": " << layout.version_table_entry_bytes
                  << ", \"graph_records_bytes\": " << layout.graph_records_bytes
                  << ", \"version_table_bytes\": " << layout.version_table_bytes
                  << ", \"logical_model_bytes\": " << layout.logical_model_bytes << "}"
                  << (comma ? "," : "") << '\n';
    };

    std::cout << "{\n"
              << "  \"format\": \"soveroot-pow-v1-versioned-graph-v0\",\n"
              << "  \"warning\": \"NON-CONSENSUS FULL-MEMORY OFFLINE GRAPH; this is not an executable reduced-memory attack or a gate result\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes
              << ", \"scratchpad_bytes\": " << params.scratchpad_bytes
              << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"digest\": \"" << Hex(result.digest) << "\",\n"
              << "  \"memory_commitment\": \"" << Hex(result.memory_commitment) << "\",\n"
              << "  \"graph\": {\n"
              << "    \"graph_commitment\": \"" << Hex(graph.graph_commitment) << "\",\n"
              << "    \"mix_iterations\": " << graph.mix_iterations << ",\n"
              << "    \"read_edges\": " << graph.read_edges << ",\n"
              << "    \"write_versions\": " << graph.write_versions << ",\n"
              << "    \"initial_zero_edges\": " << graph.initial_zero_edges << ",\n"
              << "    \"materialized_edges\": " << graph.materialized_edges << ",\n"
              << "    \"overwrite_edges\": " << graph.overwrite_edges << ",\n"
              << "    \"canonical_encoding\": {\"header_bytes\": " << graph.canonical_header_bytes
              << ", \"read_edge_bytes\": " << graph.canonical_read_edge_bytes
              << ", \"write_version_bytes\": " << graph.canonical_write_version_bytes
              << ", \"encoded_bytes\": " << graph.canonical_encoded_bytes << "},\n"
              << "    \"logical_layouts\": {\n";
    print_layout("packed", graph.packed, true);
    print_layout("conservative", graph.conservative, false);
    std::cout << "    }\n"
              << "  }\n"
              << "}\n";
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
    const std::filesystem::path* spill_directory = nullptr,
    bool recompute_half = false)
{
    if (attempts < 1 || attempts > 10000) throw std::invalid_argument("attempts must be in [1, 10000]");
    if (attempts - 1 > std::numeric_limits<std::uint64_t>::max() - first_nonce) {
        throw std::invalid_argument("nonce range exceeds uint64");
    }
    if (spill_directory != nullptr && recompute_half) {
        throw std::invalid_argument("spill and recomputation backends are mutually exclusive");
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
    RecomputationStats aggregate_recomputation_stats{};
    for (std::size_t attempt{0}; attempt < attempts; ++attempt) {
        ExecutionTiming timing{};
        SpillStats attempt_spill_stats{};
        RecomputationStats attempt_recomputation_stats{};
        const auto started = Clock::now();
        ExecutionResult result{};
        if (recompute_half) {
            result = EvaluateHalfRecompute(
                context,
                header,
                first_nonce + attempt,
                &timing,
                &attempt_recomputation_stats);
        } else if (spill_directory != nullptr) {
            result = EvaluateHalfSpill(
                context,
                header,
                first_nonce + attempt,
                *spill_directory,
                &timing,
                &attempt_spill_stats);
        } else {
            result = Evaluate(context, header, first_nonce + attempt, &timing);
        }
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
        aggregate_recomputation_stats.retained_reads += attempt_recomputation_stats.retained_reads;
        aggregate_recomputation_stats.retained_writes += attempt_recomputation_stats.retained_writes;
        aggregate_recomputation_stats.recomputed_reads += attempt_recomputation_stats.recomputed_reads;
        aggregate_recomputation_stats.discarded_writes += attempt_recomputation_stats.discarded_writes;
        aggregate_recomputation_stats.replayed_iterations += attempt_recomputation_stats.replayed_iterations;
        aggregate_recomputation_stats.logical_retained_bytes = attempt_recomputation_stats.logical_retained_bytes;
        aggregate_recomputation_stats.replay_workspace_bytes = attempt_recomputation_stats.replay_workspace_bytes;
        aggregate_recomputation_stats.peak_scratch_bytes = attempt_recomputation_stats.peak_scratch_bytes;
    }
    const std::size_t working_set =
        params.dataset_bytes +
        (recompute_half
                ? params.scratchpad_bytes + params.scratchpad_bytes / 2
                : (spill_directory == nullptr ? params.scratchpad_bytes : params.scratchpad_bytes / 2)) +
        SCHEDULE_LENGTH * 9 + REGISTER_COUNT * 8;

    std::cout << "{\n"
              << "  \"format\": \""
              << (recompute_half
                      ? "soveroot-pow-research-cpp-half-recompute-benchmark-v1"
                      : (spill_directory == nullptr
                              ? "soveroot-pow-research-cpp-benchmark-v1"
                              : "soveroot-pow-research-cpp-half-spill-benchmark-v1"))
              << "\",\n"
              << "  \"warning\": \"NON-CONSENSUS V1 CANDIDATE; timings do not establish memory hardness, mining economics, or specialization resistance\",\n"
              << "  \"compiler\": \"" << CompilerDescription() << "\",\n"
              << "  \"steady_clock\": true,\n"
              << "  \"scratchpad_backend\": \""
              << (recompute_half
                      ? "static-even-words-half-retained-full-replay"
                      : (spill_directory == nullptr ? "full-in-process" : "static-even-words-half-spill"))
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
    if (recompute_half) {
        std::cout << "  \"recomputation_stats\": {\"logical_retained_bytes\": "
                  << aggregate_recomputation_stats.logical_retained_bytes
                  << ", \"replay_workspace_bytes\": " << aggregate_recomputation_stats.replay_workspace_bytes
                  << ", \"peak_scratch_bytes\": " << aggregate_recomputation_stats.peak_scratch_bytes
                  << ", \"retained_reads\": " << aggregate_recomputation_stats.retained_reads
                  << ", \"retained_writes\": " << aggregate_recomputation_stats.retained_writes
                  << ", \"recomputed_reads\": " << aggregate_recomputation_stats.recomputed_reads
                  << ", \"discarded_writes\": " << aggregate_recomputation_stats.discarded_writes
                  << ", \"replayed_iterations\": " << aggregate_recomputation_stats.replayed_iterations
                  << ", \"external_storage_bytes\": 0},\n";
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
        if (argc == 8 && std::string_view{argv[1]} == "bounded-reconstruct-repeated") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintRepeatedReconstruction(seed, header, nonce, params);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "bounded-reconstruct-one") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintBoundedReconstruction(seed, header, nonce, params);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "bounded-probe") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintBoundedProbe(seed, header, nonce, params);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "graph") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintVersionedGraph(seed, header, nonce, params);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "trace") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintTrace(seed, header, nonce, params);
            return 0;
        }
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
        if (argc == 9 && std::string_view{argv[1]} == "benchmark-half-recompute") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t first_nonce = std::stoull(argv[4]);
            const std::size_t attempts = ParseSize(argv[5]);
            const Params params{ParseSize(argv[6]), ParseSize(argv[7]), ParseSize(argv[8])};
            PrintBenchmark(seed, header, first_nonce, attempts, params, nullptr, true);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "half-recompute") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintResult(EvaluateHalfRecompute(PrepareEpoch(seed, params), header, nonce));
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
                      << "   or: powvm_v1_cpp trace SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp graph SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp bounded-probe SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp bounded-reconstruct-one SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp bounded-reconstruct-repeated SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp half-spill SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES SPILL_DIRECTORY\n"
                      << "   or: powvm_v1_cpp benchmark-half-spill SEED_HEX HEADER_HEX FIRST_NONCE ATTEMPTS DATASET_BYTES SCRATCHPAD_BYTES PASSES SPILL_DIRECTORY\n"
                      << "   or: powvm_v1_cpp half-recompute SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp benchmark-half-recompute SEED_HEX HEADER_HEX FIRST_NONCE ATTEMPTS DATASET_BYTES SCRATCHPAD_BYTES PASSES\n";
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
