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
constexpr char DOMAIN_PACKED_RECONSTRUCTION[] = "Soveroot/PowResearch/PackedReconstruction/v1\0";
constexpr char DOMAIN_PACKED_TRANSCRIPT[] = "Soveroot/PowResearch/PackedTranscript/v1\0";
constexpr char DOMAIN_PAGED_RECONSTRUCTION[] = "Soveroot/PowResearch/PagedGapReconstruction/v1\0";
constexpr char DOMAIN_PAGED_TRANSCRIPT[] = "Soveroot/PowResearch/PagedGapTranscript/v1\0";
constexpr char DOMAIN_INDEXED_GAP_RECONSTRUCTION[] = "Soveroot/PowResearch/IndexedGapReconstruction/v1\0";
constexpr char DOMAIN_INDEXED_GAP_TRANSCRIPT[] = "Soveroot/PowResearch/IndexedGapTranscript/v1\0";
constexpr char DOMAIN_TIME_CHECKPOINT_SCREEN[] = "Soveroot/PowResearch/TimeCheckpointScreen/v1\0";
constexpr char DOMAIN_RECURSIVE_REGENERATION[] = "Soveroot/PowResearch/RecursiveRegeneration/v1\0";
constexpr char DOMAIN_REPEATED_RECURSIVE_REGENERATION[] = "Soveroot/PowResearch/RepeatedRecursiveRegeneration/v1\0";
constexpr char DOMAIN_CHECKPOINT_REGENERATION[] = "Soveroot/PowResearch/CheckpointRegeneration/v1\0";
constexpr char DOMAIN_TARGET_CHECKPOINT_REGENERATION[] = "Soveroot/PowResearch/TargetCheckpointRegeneration/v1\0";
constexpr char DOMAIN_DEPENDENCY_BUNDLE_REGENERATION[] = "Soveroot/PowResearch/DependencyBundleRegeneration/v1\0";
constexpr char DOMAIN_OPERATION_BOUNDED_DEPENDENCY_BUNDLE_REGENERATION[] = "Soveroot/PowResearch/OperationBoundedDependencyBundleRegeneration/v1\0";
constexpr char DOMAIN_PHYSICALLY_ACCOUNTED_DEPENDENCY_BUNDLE_REGENERATION[] = "Soveroot/PowResearch/PhysicallyAccountedDependencyBundleRegeneration/v1\0";
constexpr char DOMAIN_ITERATIVE_WORK_STACK_DEPENDENCY_BUNDLE_REGENERATION[] = "Soveroot/PowResearch/IterativeWorkStackDependencyBundleRegeneration/v1\0";
constexpr std::size_t BOUNDED_FIXED_STATE_RESERVE_BYTES{512};
constexpr std::size_t BOUNDED_CACHE_ENTRY_BYTES{16};
constexpr std::size_t REPLAY_NUMERATOR{5};
constexpr std::size_t REPLAY_DENOMINATOR{8};
constexpr std::size_t PACKED_RANK_CHUNK_WORDS{256};
constexpr std::size_t PACKED_PRIMARY_NUMERATOR{1};
constexpr std::size_t PACKED_PRIMARY_DENOMINATOR{4};
constexpr std::size_t PAGED_SLOTS{32};
constexpr std::size_t PAGED_BYTES{PAGED_SLOTS * 8};
constexpr std::size_t PAGED_METADATA_BYTES{4};
constexpr std::size_t CHECKPOINT_DIVISIONS{16};
constexpr std::size_t RECURSIVE_FRAME_BYTES{104};
constexpr std::size_t RECURSIVE_MEMO_ENTRY_BYTES{12};
constexpr std::size_t RECURSIVE_MEMO_WAYS{4};
constexpr std::size_t RECURSIVE_MEMO_WORD_BITS{15};
constexpr std::size_t RECURSIVE_PRIMARY_NUMERATOR{1};
constexpr std::size_t RECURSIVE_PRIMARY_DENOMINATOR{64};
constexpr std::size_t RECURSIVE_MAXIMUM_FRAMES{20};
constexpr std::uint64_t RECURSIVE_WORK_LIMIT{1'000'000};
constexpr std::uint64_t REGENERATION_OPERATION_LIMIT{5'000'000};
constexpr std::size_t NATIVE_STACK_FRAME_ALLOWANCE_BYTES{2'048};
constexpr std::size_t NATIVE_STACK_DEPTH_CAPACITY{20};
constexpr std::size_t NATIVE_STACK_RESERVE_BYTES{
    NATIVE_STACK_FRAME_ALLOWANCE_BYTES * NATIVE_STACK_DEPTH_CAPACITY};
constexpr std::size_t ALLOCATOR_ALLOWANCE_BYTES{4'096};
constexpr std::size_t PHYSICAL_EXTERNAL_RESERVE_BYTES{
    NATIVE_STACK_RESERVE_BYTES + ALLOCATOR_ALLOWANCE_BYTES};
constexpr std::size_t ITERATIVE_EXTERNAL_RESERVE_BYTES{ALLOCATOR_ALLOWANCE_BYTES};
constexpr std::uint32_t RECURSIVE_EMPTY_MEMO_KEY{std::numeric_limits<std::uint32_t>::max()};
constexpr std::size_t CHECKPOINT_ENTRY_BYTES{80};
constexpr std::size_t TARGET_CHECKPOINT_ENTRY_BYTES{88};
constexpr std::size_t DEPENDENCY_BUNDLE_WIDTH{4};
constexpr std::size_t DEPENDENCY_BUNDLE_VALUE_OFFSET{16};
constexpr std::size_t DEPENDENCY_BUNDLE_STATE_OFFSET{48};
constexpr std::size_t DEPENDENCY_BUNDLE_ENTRY_BYTES{120};
constexpr std::size_t CHECKPOINT_CAPACITY{4};
constexpr std::size_t DEPENDENCY_BUNDLE_CAPACITY{12};
constexpr std::size_t CHECKPOINT_STRIDE{8};
constexpr std::uint32_t EMPTY_CHECKPOINT_STOP{std::numeric_limits<std::uint32_t>::max()};
constexpr std::uint16_t EMPTY_BUNDLE_WORD{std::numeric_limits<std::uint16_t>::max()};

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

struct PackedLayout {
    std::size_t budget_bytes{0};
    std::size_t fixed_state_reserve_bytes{0};
    std::size_t arena_bytes{0};
    std::size_t canonical_write_bitmap_bytes{0};
    std::size_t primary_cache_capacity{0};
    std::size_t primary_cache_bytes{0};
    std::size_t replay_bitmap_bytes{0};
    std::size_t rank_directory_bytes{0};
    std::size_t replay_value_capacity{0};
    std::size_t replay_value_bytes{0};
    std::size_t unused_arena_bytes{0};
    std::size_t admitted_bytes{0};
};

struct PackedBoundary {
    std::uint64_t consumer{0};
    std::uint8_t slot{0};
    std::uint64_t word{0};
    std::uint64_t value{0};
    std::uint64_t replayed_iterations{0};
    std::uint64_t replay_peak_entries{0};
    std::uint64_t replay_rank_probes{0};
    std::uint64_t replay_shifted_bytes{0};
    Bytes commitment;
};

struct PackedExhaustionBoundary {
    std::uint64_t consumer{0};
    std::uint8_t slot{0};
    std::uint64_t word{0};
    std::uint64_t replay_completed_iterations{0};
    std::uint64_t replay_peak_entries{0};
    std::uint64_t replay_rank_probes{0};
    std::uint64_t replay_shifted_bytes{0};
    Bytes state_commitment;
};

struct PackedReconstructionResult {
    std::string status{"refused_packed_checkpoint_exhausted"};
    std::uint64_t completed_iterations{0};
    std::uint64_t reconstruction_attempts{0};
    std::uint64_t reconstructed_misses{0};
    std::uint64_t successful_replayed_iterations{0};
    std::uint64_t attempted_replay_iterations{0};
    std::uint64_t cumulative_rank_probes{0};
    std::uint64_t cumulative_shifted_bytes{0};
    std::uint64_t max_replay_peak_entries{0};
    std::uint64_t max_reconstruction_depth{0};
    bool all_replay_states_matched{true};
    Bytes transcript_commitment;
    bool has_first{false};
    PackedBoundary first_reconstruction{};
    PackedBoundary last_reconstruction{};
    bool has_exhaustion{false};
    PackedExhaustionBoundary exhaustion{};
    ExecutionResult execution_result{};
    PackedLayout layout{};
    BoundedReconstructionStats stats{};
};

struct PagedLayout {
    std::size_t budget_bytes{0}, fixed_state_reserve_bytes{0}, arena_bytes{0};
    std::size_t canonical_write_bitmap_bytes{0}, primary_cache_capacity{0}, primary_cache_bytes{0};
    std::size_t replay_bitmap_bytes{0}, rank_directory_bytes{0}, page_slots{0};
    std::size_t max_pages{0}, page_directory_bytes{0}, page_count_bytes{0};
    std::size_t replay_value_slots{0}, replay_value_bytes{0}, unused_arena_bytes{0}, admitted_bytes{0};
};

struct PagedBoundary {
    std::uint64_t consumer{0}, word{0}, value{0}, replayed_iterations{0};
    std::uint64_t replay_peak_values{0}, replay_peak_pages{0}, replay_rank_probes{0};
    std::uint64_t replay_directory_probes{0}, replay_shifted_bytes{0};
    std::uint8_t slot{0};
    Bytes commitment;
};

struct PagedExhaustionBoundary {
    std::uint64_t consumer{0}, word{0}, replay_completed_iterations{0};
    std::uint64_t replay_occupied_values{0}, replay_allocated_pages{0}, replay_rank_probes{0};
    std::uint64_t replay_directory_probes{0}, replay_shifted_bytes{0};
    std::uint8_t slot{0};
    Bytes state_commitment;
};

struct PagedReconstructionResult {
    std::string status{"refused_paged_gap_exhausted"};
    std::uint64_t completed_iterations{0}, reconstruction_attempts{0}, reconstructed_misses{0};
    std::uint64_t successful_replayed_iterations{0}, attempted_replay_iterations{0};
    std::uint64_t cumulative_rank_probes{0}, cumulative_directory_probes{0}, cumulative_shifted_bytes{0};
    std::uint64_t max_replay_peak_values{0}, max_replay_peak_pages{0}, max_reconstruction_depth{0};
    bool all_replay_states_matched{true}, has_first{false}, has_exhaustion{false};
    Bytes transcript_commitment;
    PagedBoundary first_reconstruction{}, last_reconstruction{};
    PagedExhaustionBoundary exhaustion{};
    ExecutionResult execution_result{};
    PagedLayout layout{};
    BoundedReconstructionStats stats{};
};

struct IndexedGapLayout {
    std::size_t budget_bytes{0}, fixed_state_reserve_bytes{0}, arena_bytes{0};
    std::size_t canonical_write_bitmap_bytes{0}, primary_cache_capacity{0}, primary_cache_bytes{0};
    std::size_t replay_bitmap_bytes{0}, rank_directory_bytes{0}, page_slots{0};
    std::size_t max_pages{0}, page_directory_bytes{0}, page_count_bytes{0}, page_index_bytes{0};
    std::size_t replay_value_slots{0}, replay_value_bytes{0}, unused_arena_bytes{0}, admitted_bytes{0};
};

struct IndexedGapBoundary {
    std::uint64_t consumer{0}, word{0}, value{0}, replayed_iterations{0};
    std::uint64_t replay_peak_values{0}, replay_peak_pages{0}, replay_rank_probes{0};
    std::uint64_t replay_index_probes{0}, replay_directory_probes{0}, replay_rebalances{0};
    std::uint64_t replay_shifted_bytes{0};
    std::uint8_t slot{0};
    Bytes commitment;
};

struct IndexedGapExhaustionBoundary {
    std::uint64_t consumer{0}, word{0}, replay_completed_iterations{0};
    std::uint64_t replay_occupied_values{0}, replay_allocated_pages{0}, replay_rank_probes{0};
    std::uint64_t replay_index_probes{0}, replay_directory_probes{0}, replay_rebalances{0};
    std::uint64_t replay_shifted_bytes{0};
    std::uint8_t slot{0};
    Bytes state_commitment;
};

struct IndexedGapReconstructionResult {
    std::string status{"refused_indexed_gap_exhausted"};
    std::uint64_t completed_iterations{0}, reconstruction_attempts{0}, reconstructed_misses{0};
    std::uint64_t successful_replayed_iterations{0}, attempted_replay_iterations{0};
    std::uint64_t cumulative_rank_probes{0}, cumulative_index_probes{0}, cumulative_directory_probes{0};
    std::uint64_t cumulative_rebalances{0}, cumulative_shifted_bytes{0};
    std::uint64_t max_replay_peak_values{0}, max_replay_peak_pages{0}, max_reconstruction_depth{0};
    bool all_replay_states_matched{true}, has_first{false}, has_exhaustion{false};
    Bytes transcript_commitment;
    IndexedGapBoundary first_reconstruction{}, last_reconstruction{};
    IndexedGapExhaustionBoundary exhaustion{};
    ExecutionResult execution_result{};
    IndexedGapLayout layout{};
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

struct CheckpointStoreLayout {
    std::size_t budget_bytes{0}, fixed_state_reserve_bytes{0};
    std::size_t bitmap_bytes_per_nonempty_store{0}, rank_directory_bytes_per_nonempty_store{0};
    std::size_t value_bytes{8}, checkpoint_divisions{CHECKPOINT_DIVISIONS};
};

struct CheckpointCut {
    std::uint64_t checkpoint_iteration{0}, snapshot_materialized_values{0};
    std::uint64_t suffix_distinct_write_values{0}, duplicated_snapshot_delta_values{0};
    std::uint64_t checkpoint_frontier_values{0}, capture_peak_live_values{0};
    std::uint64_t resume_peak_live_values{0}, staged_peak_live_values{0};
    std::uint64_t full_checkpoint_bytes{0}, naive_snapshot_delta_bytes{0}, optimistic_staged_bytes{0};
    bool full_checkpoint_fits{false}, naive_snapshot_delta_fits{false}, optimistic_staged_fits{false};
};

struct TimeCheckpointScreenResult {
    CheckpointStoreLayout layout{};
    std::uint64_t total_iterations{0}, trace_reads{0}, trace_writes{0};
    std::uint64_t global_maximum_live_values{0};
    std::vector<CheckpointCut> cuts;
    bool any_naive_snapshot_delta_fits{false}, any_optimistic_staged_fits{false};
    Bytes screen_commitment;
};

struct RecursiveLayout {
    std::size_t budget_bytes{0}, fixed_state_reserve_bytes{0}, arena_bytes{0};
    std::size_t write_bitmap_bytes{0}, primary_cache_capacity{0}, primary_cache_bytes{0};
    std::size_t frame_bytes{0}, frame_capacity{0}, frame_reserve_bytes{0};
    std::size_t memo_entry_bytes{0}, memo_capacity{0}, memo_bytes{0};
    std::size_t checkpoint_entry_bytes{0}, checkpoint_capacity{0}, checkpoint_bytes{0};
    std::size_t checkpoint_stride{0};
    std::size_t unused_arena_bytes{0}, admitted_bytes{0};
};

struct RecursiveBoundary {
    std::uint64_t consumer{0}, word{0}, value{0};
    std::uint64_t regeneration_calls{0}, regeneration_cache_hits{0};
    std::uint64_t regeneration_completed_values{0}, regeneration_iterations{0};
    std::uint64_t maximum_depth{0}, memo_peak_entries{0}, memo_evictions{0};
    std::uint64_t memo_probes{0}, memo_shifted_bytes{0};
    std::uint8_t slot{0};
    Bytes commitment;
    std::uint64_t checkpoint_lookups{0}, checkpoint_hits{0}, checkpoint_captures{0};
    std::uint64_t checkpoint_replacements{0}, checkpoint_probes{0};
};

struct RecursiveExhaustion {
    std::string reason;
    std::uint64_t stop_iteration{0}, word{0}, attempted_depth{0}, regeneration_iterations{0};
};

struct RecursiveRegenerationResult {
    std::string status{"refused_recursive_regeneration_exhausted"};
    RecursiveLayout layout{};
    std::uint64_t work_limit{RECURSIVE_WORK_LIMIT}, completed_iterations{0};
    std::uint64_t canonical_reads{0}, cache_hits{0}, initial_zero_reads{0};
    std::uint64_t materialized_misses{0}, writes{0}, evictions{0};
    std::uint64_t reconstruction_attempts{0}, reconstructed_misses{0};
    std::uint64_t regeneration_calls{0}, regeneration_cache_hits{0};
    std::uint64_t regeneration_completed_values{0}, regeneration_iterations{0};
    std::uint64_t maximum_depth{0}, memo_peak_entries{0}, memo_evictions{0};
    std::uint64_t memo_probes{0}, memo_shifted_bytes{0};
    bool has_first{false}, has_refusal{false}, has_exhaustion{false};
    RecursiveBoundary first_reconstruction{};
    std::uint64_t refusal_consumer{0}, refusal_word{0};
    std::uint8_t refusal_slot{0};
    Bytes refusal_state_commitment;
    RecursiveExhaustion exhaustion{};
    Bytes transcript_commitment;
};

struct RepeatedRecursiveExhaustion {
    std::string reason;
    std::uint64_t consumer{0}, word{0}, stop_iteration{0}, attempted_depth{0};
    std::uint64_t regeneration_iterations{0};
    std::uint8_t slot{0};
    Bytes state_commitment;
};

struct RepeatedRecursiveRegenerationResult {
    std::string status{"refused_recursive_regeneration_exhausted"};
    RecursiveLayout layout{};
    std::uint64_t primary_numerator{1}, primary_denominator{64};
    std::uint64_t work_limit{RECURSIVE_WORK_LIMIT}, completed_iterations{0};
    std::uint64_t canonical_reads{0}, cache_hits{0}, initial_zero_reads{0};
    std::uint64_t materialized_misses{0}, writes{0}, evictions{0};
    std::uint64_t reconstruction_attempts{0}, reconstructed_misses{0};
    std::uint64_t regeneration_calls{0}, regeneration_cache_hits{0};
    std::uint64_t regeneration_completed_values{0}, regeneration_iterations{0};
    std::uint64_t maximum_depth{0}, memo_peak_entries{0}, memo_evictions{0};
    std::uint64_t memo_probes{0}, memo_shifted_bytes{0};
    bool has_first{false}, has_last{false}, has_exhaustion{false}, has_execution{false};
    RecursiveBoundary first_reconstruction{}, last_reconstruction{};
    RepeatedRecursiveExhaustion exhaustion{};
    Bytes transcript_commitment;
    ExecutionResult execution_result{};
    std::uint64_t checkpoint_lookups{0}, checkpoint_hits{0}, checkpoint_captures{0};
    std::uint64_t checkpoint_replacements{0}, checkpoint_probes{0};
    std::uint64_t operation_limit{0}, total_operations{0};
    bool physical_accounting{false};
    bool iterative_accounting{false};
    std::size_t physical_total_budget_bytes{0}, physical_arena_allocation_bytes{0};
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
    TimeCheckpointScreenResult ScreenTimeCheckpoints(std::size_t budget_bytes) const;

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

std::uint32_t ReadLE32(const std::uint8_t* data)
{
    std::uint32_t value{0};
    for (unsigned i{0}; i < 4; ++i) value |= std::uint32_t{data[i]} << (8 * i);
    return value;
}

std::uint16_t ReadLE16(const std::uint8_t* data)
{
    return std::uint16_t{data[0]} | (std::uint16_t{data[1]} << 8);
}

void AppendLE64(Bytes& output, std::uint64_t value)
{
    for (unsigned i{0}; i < 8; ++i) output.push_back(static_cast<std::uint8_t>(value >> (8 * i)));
}

void WriteLE64(std::uint8_t* output, std::uint64_t value)
{
    for (unsigned i{0}; i < 8; ++i) output[i] = static_cast<std::uint8_t>(value >> (8 * i));
}

void WriteLE32(std::uint8_t* output, std::uint32_t value)
{
    for (unsigned i{0}; i < 4; ++i) output[i] = static_cast<std::uint8_t>(value >> (8 * i));
}

void WriteLE16(std::uint8_t* output, std::uint16_t value)
{
    output[0] = static_cast<std::uint8_t>(value);
    output[1] = static_cast<std::uint8_t>(value >> 8);
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

TimeCheckpointScreenResult TraceRecorder::ScreenTimeCheckpoints(std::size_t budget_bytes) const
{
    constexpr std::size_t FINAL_READS{FINAL_SAMPLE_WORDS};
    constexpr std::size_t EVENTS_PER_ITERATION{4};
    if (m_events.size() < FINAL_READS || (m_events.size() - FINAL_READS) % EVENTS_PER_ITERATION != 0) {
        throw std::logic_error("trace does not match the v1 iteration/finalization shape");
    }
    TimeCheckpointScreenResult result{};
    result.total_iterations = (m_events.size() - FINAL_READS) / EVENTS_PER_ITERATION;
    result.layout.budget_bytes = budget_bytes;
    result.layout.fixed_state_reserve_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES;
    result.layout.bitmap_bytes_per_nonempty_store = (m_word_count + 7) / 8;
    const std::size_t rank_chunks = (m_word_count + PACKED_RANK_CHUNK_WORDS - 1) / PACKED_RANK_CHUNK_WORDS;
    result.layout.rank_directory_bytes_per_nonempty_store = (rank_chunks + 1) * 2;
    result.cuts.reserve(CHECKPOINT_DIVISIONS + 1);

    std::vector<bool> materialized(m_events.size(), false), forward_written(m_word_count, false);
    for (std::size_t index{0}; index < m_events.size(); ++index) {
        const TraceEvent& event = m_events[index];
        if (event.is_write) {
            forward_written[event.word] = true;
            ++result.trace_writes;
        } else {
            materialized[index] = forward_written[event.word];
            ++result.trace_reads;
        }
    }
    auto backward_live = [&](std::size_t start, std::size_t stop, std::vector<bool> live) {
        std::size_t live_count = static_cast<std::size_t>(std::count(live.begin(), live.end(), true));
        std::size_t peak = live_count;
        for (std::size_t index{stop}; index > start; --index) {
            const TraceEvent& event = m_events[index - 1];
            if (event.is_write) {
                if (live[event.word]) { live[event.word] = false; --live_count; }
            } else if (materialized[index - 1] && !live[event.word]) {
                live[event.word] = true; ++live_count;
            }
            peak = std::max(peak, live_count);
        }
        return std::pair<std::vector<bool>, std::size_t>{std::move(live), peak};
    };
    auto store_bytes = [&](std::size_t values) {
        if (values == 0) return std::size_t{0};
        return result.layout.bitmap_bytes_per_nonempty_store +
            result.layout.rank_directory_bytes_per_nonempty_store + values * result.layout.value_bytes;
    };
    Bytes transcript = DomainBytes(DOMAIN_TIME_CHECKPOINT_SCREEN);
    AppendLE64(transcript, m_word_count); AppendLE64(transcript, result.total_iterations);
    AppendLE64(transcript, budget_bytes); AppendLE64(transcript, CHECKPOINT_DIVISIONS);
    const std::size_t mix_event_count = result.total_iterations * EVENTS_PER_ITERATION;
    for (std::size_t division{0}; division <= CHECKPOINT_DIVISIONS; ++division) {
        const std::size_t checkpoint = result.total_iterations * division / CHECKPOINT_DIVISIONS;
        const std::size_t boundary = checkpoint * EVENTS_PER_ITERATION;
        std::vector<bool> prefix_written(m_word_count, false), suffix_written(m_word_count, false);
        for (std::size_t index{0}; index < boundary; ++index) if (m_events[index].is_write) prefix_written[m_events[index].word] = true;
        for (std::size_t index{boundary}; index < mix_event_count; ++index) if (m_events[index].is_write) suffix_written[m_events[index].word] = true;
        auto [frontier, resume_peak] = backward_live(boundary, m_events.size(), std::vector<bool>(m_word_count, false));
        auto [unused, capture_peak] = backward_live(0, boundary, frontier);
        static_cast<void>(unused);
        const std::size_t snapshot = static_cast<std::size_t>(std::count(prefix_written.begin(), prefix_written.end(), true));
        const std::size_t delta = static_cast<std::size_t>(std::count(suffix_written.begin(), suffix_written.end(), true));
        const std::size_t frontier_count = static_cast<std::size_t>(std::count(frontier.begin(), frontier.end(), true));
        std::size_t duplicated{0};
        for (std::size_t word{0}; word < m_word_count; ++word) if (prefix_written[word] && suffix_written[word]) ++duplicated;
        const std::size_t staged_peak = std::max(capture_peak, resume_peak);
        CheckpointCut cut{};
        cut.checkpoint_iteration = checkpoint; cut.snapshot_materialized_values = snapshot;
        cut.suffix_distinct_write_values = delta; cut.duplicated_snapshot_delta_values = duplicated;
        cut.checkpoint_frontier_values = frontier_count; cut.capture_peak_live_values = capture_peak;
        cut.resume_peak_live_values = resume_peak; cut.staged_peak_live_values = staged_peak;
        cut.full_checkpoint_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES + store_bytes(snapshot);
        cut.naive_snapshot_delta_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES + store_bytes(snapshot) + store_bytes(delta);
        cut.optimistic_staged_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES + store_bytes(staged_peak);
        cut.full_checkpoint_fits = cut.full_checkpoint_bytes <= budget_bytes;
        cut.naive_snapshot_delta_fits = cut.naive_snapshot_delta_bytes <= budget_bytes;
        cut.optimistic_staged_fits = cut.optimistic_staged_bytes <= budget_bytes;
        result.any_naive_snapshot_delta_fits = result.any_naive_snapshot_delta_fits || cut.naive_snapshot_delta_fits;
        result.any_optimistic_staged_fits = result.any_optimistic_staged_fits || cut.optimistic_staged_fits;
        for (const std::uint64_t value : std::array<std::uint64_t, 11>{
                 cut.checkpoint_iteration, cut.snapshot_materialized_values,
                 cut.suffix_distinct_write_values, cut.duplicated_snapshot_delta_values,
                 cut.checkpoint_frontier_values, cut.capture_peak_live_values,
                 cut.resume_peak_live_values, cut.staged_peak_live_values,
                 cut.full_checkpoint_bytes, cut.naive_snapshot_delta_bytes,
                 cut.optimistic_staged_bytes}) AppendLE64(transcript, value);
        transcript.push_back(cut.full_checkpoint_fits); transcript.push_back(cut.naive_snapshot_delta_fits);
        transcript.push_back(cut.optimistic_staged_fits);
        result.cuts.push_back(cut);
    }
    result.global_maximum_live_values = result.cuts.front().resume_peak_live_values;
    result.screen_commitment = Sha3_384(transcript);
    return result;
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

class RecursiveRegenerationExhausted final : public std::runtime_error {
public:
    RecursiveRegenerationExhausted(
        std::string reason_in,
        std::uint64_t stop_in,
        std::uint64_t word_in,
        std::uint64_t depth_in)
        : std::runtime_error(reason_in), reason(std::move(reason_in)), stop(stop_in),
          word(word_in), depth(depth_in)
    {
    }

    std::string reason;
    std::uint64_t stop, word, depth;
};

class RecursiveArena {
public:
    RecursiveArena(
        std::size_t scratchpad_bytes,
        std::size_t budget_bytes,
        std::size_t primary_numerator = RECURSIVE_PRIMARY_NUMERATOR,
        std::size_t primary_denominator = RECURSIVE_PRIMARY_DENOMINATOR,
        std::size_t checkpoint_capacity = 0,
        std::size_t checkpoint_stride = 0,
        bool target_checkpoints = false,
        bool dependency_bundles = false,
        std::size_t external_reserve_bytes = 0)
        : m_word_count(scratchpad_bytes / 8)
    {
        if (primary_numerator == 0 || primary_denominator == 0 ||
            primary_numerator > primary_denominator) {
            throw std::invalid_argument("recursive primary allocation ratio is invalid");
        }
        m_layout.budget_bytes = budget_bytes;
        m_layout.fixed_state_reserve_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES;
        if (budget_bytes <= BOUNDED_FIXED_STATE_RESERVE_BYTES) {
            throw std::invalid_argument("recursive budget cannot hold fixed state");
        }
        if (budget_bytes <= BOUNDED_FIXED_STATE_RESERVE_BYTES + external_reserve_bytes) {
            throw std::invalid_argument("recursive budget cannot hold external reserves");
        }
        m_layout.arena_bytes =
            budget_bytes - BOUNDED_FIXED_STATE_RESERVE_BYTES - external_reserve_bytes;
        m_layout.write_bitmap_bytes = (m_word_count + 7) / 8;
        if (m_layout.arena_bytes <=
            m_layout.write_bitmap_bytes + BOUNDED_CACHE_ENTRY_BYTES +
                RECURSIVE_FRAME_BYTES + RECURSIVE_MEMO_ENTRY_BYTES * RECURSIVE_MEMO_WAYS) {
            throw std::invalid_argument("budget cannot hold recursive regeneration structures");
        }
        const std::size_t total_primary_slots =
            (m_layout.arena_bytes - m_layout.write_bitmap_bytes) /
            BOUNDED_CACHE_ENTRY_BYTES;
        m_layout.primary_cache_capacity =
            total_primary_slots * primary_numerator / primary_denominator;
        if (m_layout.primary_cache_capacity == 0) {
            throw std::invalid_argument("recursive budget cannot hold one primary entry");
        }
        m_layout.primary_cache_bytes =
            m_layout.primary_cache_capacity * BOUNDED_CACHE_ENTRY_BYTES;
        const std::size_t auxiliary_bytes =
            m_layout.arena_bytes - m_layout.write_bitmap_bytes - m_layout.primary_cache_bytes;
        m_layout.checkpoint_entry_bytes = dependency_bundles
            ? DEPENDENCY_BUNDLE_ENTRY_BYTES
            : (target_checkpoints ? TARGET_CHECKPOINT_ENTRY_BYTES : CHECKPOINT_ENTRY_BYTES);
        m_layout.checkpoint_capacity = checkpoint_capacity;
        m_layout.checkpoint_bytes = checkpoint_capacity * m_layout.checkpoint_entry_bytes;
        m_layout.checkpoint_stride = checkpoint_stride;
        if ((checkpoint_capacity == 0) != (checkpoint_stride == 0)) {
            throw std::invalid_argument("checkpoint capacity and stride must both be zero or positive");
        }
        if (auxiliary_bytes <=
            m_layout.checkpoint_bytes + RECURSIVE_FRAME_BYTES +
                RECURSIVE_MEMO_ENTRY_BYTES * RECURSIVE_MEMO_WAYS) {
            throw std::invalid_argument("budget cannot hold checkpoints and recursive structures");
        }
        m_layout.frame_bytes = RECURSIVE_FRAME_BYTES;
        m_layout.frame_capacity = std::min(
            RECURSIVE_MAXIMUM_FRAMES,
            (auxiliary_bytes - RECURSIVE_MEMO_ENTRY_BYTES * RECURSIVE_MEMO_WAYS -
             m_layout.checkpoint_bytes) /
                RECURSIVE_FRAME_BYTES);
        if (m_layout.frame_capacity == 0) {
            throw std::invalid_argument("recursive budget cannot hold one frame");
        }
        m_layout.frame_reserve_bytes = m_layout.frame_capacity * RECURSIVE_FRAME_BYTES;
        m_layout.memo_entry_bytes = RECURSIVE_MEMO_ENTRY_BYTES;
        m_layout.memo_capacity =
            ((auxiliary_bytes - m_layout.frame_reserve_bytes - m_layout.checkpoint_bytes) /
             RECURSIVE_MEMO_ENTRY_BYTES /
             RECURSIVE_MEMO_WAYS) * RECURSIVE_MEMO_WAYS;
        if (m_layout.memo_capacity == 0) {
            throw std::invalid_argument("recursive budget cannot hold one memo set");
        }
        m_layout.memo_bytes = m_layout.memo_capacity * RECURSIVE_MEMO_ENTRY_BYTES;
        m_layout.unused_arena_bytes =
            auxiliary_bytes - m_layout.frame_reserve_bytes - m_layout.memo_bytes -
            m_layout.checkpoint_bytes;
        m_layout.admitted_bytes = budget_bytes;
        m_primary_offset = m_layout.write_bitmap_bytes;
        m_frame_offset = m_primary_offset + m_layout.primary_cache_bytes;
        m_memo_offset = m_frame_offset + m_layout.frame_reserve_bytes;
        m_checkpoint_offset = m_memo_offset + m_layout.memo_bytes;
        m_arena.resize(m_layout.arena_bytes, 0);
        for (std::size_t slot{0}; slot < m_layout.primary_cache_capacity; ++slot) {
            WriteLE64(m_arena.data() + PrimaryOffset(slot), EmptyTag());
        }
        for (std::size_t slot{0}; slot < m_layout.memo_capacity; ++slot) {
            WriteLE32(m_arena.data() + MemoOffset(slot), RECURSIVE_EMPTY_MEMO_KEY);
        }
        for (std::size_t slot{0}; slot < m_layout.checkpoint_capacity; ++slot) {
            WriteLE32(m_arena.data() + CheckpointOffset(slot), EMPTY_CHECKPOINT_STOP);
        }
    }

    void SetConsumer(std::uint64_t consumer) { m_consumer = consumer; m_slot = 0; }

    std::uint64_t Read(std::uint64_t selector)
    {
        const std::size_t word = Word(selector);
        const std::uint8_t slot = m_slot++;
        ++canonical_reads;
        const std::size_t offset = PrimaryOffset(word % m_layout.primary_cache_capacity);
        if (ReadLE64(m_arena.data() + offset) == word) {
            ++cache_hits;
            return ReadLE64(m_arena.data() + offset + 8);
        }
        if (!WasWritten(word)) {
            ++initial_zero_reads;
            return 0;
        }
        ++materialized_misses;
        throw BoundedReadMiss{0, m_consumer, slot, word};
    }

    void Write(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = Word(selector);
        StorePrimary(word, value);
        m_arena[word / 8] |= std::uint8_t{1} << (word & 7);
        ++writes;
    }

    void Retain(std::uint64_t word, std::uint64_t value)
    {
        StorePrimary(static_cast<std::size_t>(word), value);
    }

    std::uint32_t MemoKey(std::uint64_t stop, std::uint64_t word) const
    {
        if (stop >= (std::uint64_t{1} << (32 - RECURSIVE_MEMO_WORD_BITS)) ||
            word >= (std::uint64_t{1} << RECURSIVE_MEMO_WORD_BITS)) {
            throw std::invalid_argument("recursive memo key exceeds the packed v1 range");
        }
        return static_cast<std::uint32_t>((stop << RECURSIVE_MEMO_WORD_BITS) | word);
    }

    std::size_t MemoSet(std::uint32_t key) const
    {
        const std::uint32_t mixed = key * std::uint32_t{0x9E3779B1U};
        return mixed % (m_layout.memo_capacity / RECURSIVE_MEMO_WAYS);
    }

    std::size_t MemoSetOffset(std::size_t set_index, std::size_t way) const
    {
        return MemoOffset(set_index * RECURSIVE_MEMO_WAYS + way);
    }

    std::size_t CheckpointOffset(std::size_t slot) const
    {
        return m_checkpoint_offset + slot * m_layout.checkpoint_entry_bytes;
    }

    std::size_t FrameOffset(std::size_t slot) const
    {
        return m_frame_offset + slot * RECURSIVE_FRAME_BYTES;
    }

    Bytes& Arena() { return m_arena; }
    const RecursiveLayout& Layout() const { return m_layout; }
    std::size_t WordCount() const { return m_word_count; }
    std::size_t ArenaCapacityBytes() const { return m_arena.capacity(); }

    std::uint64_t canonical_reads{0}, cache_hits{0}, initial_zero_reads{0};
    std::uint64_t materialized_misses{0}, writes{0}, evictions{0};

private:
    static constexpr std::uint64_t EmptyTag()
    {
        return std::numeric_limits<std::uint64_t>::max();
    }

    std::size_t Word(std::uint64_t selector) const
    {
        return static_cast<std::size_t>(selector) & (m_word_count - 1);
    }

    std::size_t PrimaryOffset(std::size_t slot) const
    {
        return m_primary_offset + slot * BOUNDED_CACHE_ENTRY_BYTES;
    }

    std::size_t MemoOffset(std::size_t slot) const
    {
        return m_memo_offset + slot * RECURSIVE_MEMO_ENTRY_BYTES;
    }

    bool WasWritten(std::size_t word) const
    {
        return (m_arena[word / 8] & (std::uint8_t{1} << (word & 7))) != 0;
    }

    void StorePrimary(std::size_t word, std::uint64_t value)
    {
        const std::size_t offset = PrimaryOffset(word % m_layout.primary_cache_capacity);
        const std::uint64_t previous = ReadLE64(m_arena.data() + offset);
        if (previous != EmptyTag() && previous != word) ++evictions;
        WriteLE64(m_arena.data() + offset, word);
        WriteLE64(m_arena.data() + offset + 8, value);
    }

    std::size_t m_word_count, m_primary_offset{0}, m_frame_offset{0}, m_memo_offset{0};
    std::size_t m_checkpoint_offset{0};
    std::uint64_t m_consumer{0};
    std::uint8_t m_slot{0};
    Bytes m_arena;
    RecursiveLayout m_layout{};
};

std::uint64_t ExecuteOperation(
    std::uint8_t opcode,
    std::uint64_t x,
    std::uint64_t y,
    std::uint64_t first_scratch,
    std::uint64_t second_scratch,
    std::uint64_t dataset_word,
    std::uint64_t immediate);

MachineState InitializeMachineState(
    const EpochContext& context,
    std::span<const std::uint8_t> header_digest,
    std::span<const std::uint8_t> nonce_bytes,
    std::span<const std::uint8_t> params_bytes);

class RecursiveRegenerator {
public:
    RecursiveRegenerator(
        RecursiveArena& owner,
        const EpochContext& context,
        const Bytes& header_digest,
        const Bytes& nonce_bytes,
        const Bytes& params_bytes,
        std::uint64_t work_limit,
        std::uint64_t operation_limit = 0)
        : m_owner(owner), m_context(context), m_header_digest(header_digest),
          m_nonce_bytes(nonce_bytes), m_params_bytes(params_bytes), m_work_limit(work_limit),
          m_operation_limit(operation_limit)
    {
    }

    std::uint64_t ValueAt(std::uint64_t target_word, std::uint64_t stop, std::uint64_t depth = 1)
    {
        ChargeOperation(stop, target_word, depth);
        ++calls;
        if (stop == 0) {
            ++completed_values;
            return 0;
        }
        maximum_depth = std::max(maximum_depth, depth);
        if (depth > m_owner.Layout().frame_capacity) {
            throw RecursiveRegenerationExhausted{"frame_capacity", stop, target_word, depth};
        }
        std::uint64_t cached{0};
        if (MemoGet(stop, target_word, depth, cached)) return cached;
        MachineState state{};
        std::uint64_t start{0};
        std::uint64_t target_value{0};
        bool target_value_restored{false};
        if (CheckpointFind(
                target_word, stop, depth, start, target_value,
                target_value_restored, state)) {
            if (!target_value_restored) {
                target_value = ValueAt(target_word, start, depth + 1);
            }
        } else {
            state = InitializeMachineState(
                m_context, m_header_digest, m_nonce_bytes, m_params_bytes);
        }
        const std::size_t word_count = m_owner.WordCount();
        for (std::uint64_t iteration{start}; iteration < stop; ++iteration) {
            if (iterations >= m_work_limit) {
                throw RecursiveRegenerationExhausted{"work_limit", stop, target_word, depth};
            }
            ChargeOperation(stop, target_word, depth);
            ++iterations;
            const std::size_t pass = static_cast<std::size_t>(iteration) / word_count;
            const std::size_t word = static_cast<std::size_t>(iteration) & (word_count - 1);
            const std::size_t lane = static_cast<std::size_t>(iteration) & (REGISTER_COUNT - 1);
            const ScheduleEntry& entry =
                m_context.schedule[static_cast<std::size_t>(iteration) & (SCHEDULE_LENGTH - 1)];
            const std::uint64_t x = state.registers[lane];
            const std::uint64_t y = state.registers[(lane + 1) & (REGISTER_COUNT - 1)];
            const std::uint64_t z = state.registers[(lane + 3) & (REGISTER_COUNT - 1)];
            const std::uint64_t first_selector =
                x ^ std::rotl(y, static_cast<int>(iteration & 63)) ^
                state.accumulator ^ entry.immediate;
            const std::uint64_t first_word = first_selector & (word_count - 1);
            const std::uint64_t first_scratch = ValueAt(first_word, iteration, depth + 1);
            const std::uint64_t dataset_selector =
                first_scratch ^ z ^
                std::rotl(state.accumulator, static_cast<int>((lane + pass) & 63)) ^ iteration;
            const std::uint64_t dataset_word = ReadMemory(m_context.dataset, dataset_selector);
            const std::uint64_t second_selector =
                dataset_word ^ state.registers[(lane + 5) & (REGISTER_COUNT - 1)] ^
                std::rotl(first_scratch + state.accumulator, static_cast<int>(entry.immediate & 63));
            const std::uint64_t second_word = second_selector & (word_count - 1);
            const std::uint64_t second_scratch = ValueAt(second_word, iteration, depth + 1);
            const std::uint64_t mixed = ExecuteOperation(
                entry.opcode, x, y, first_scratch, second_scratch,
                dataset_word, entry.immediate);
            state.accumulator =
                std::rotl(
                    state.accumulator ^ mixed ^ dataset_word,
                    static_cast<int>((first_scratch ^ second_scratch ^ entry.immediate) & 63)) +
                first_scratch + entry.immediate + iteration;
            const std::uint64_t first_write = mixed ^ state.accumulator ^ second_scratch;
            const std::uint64_t second_write =
                second_scratch ^ std::rotl(mixed + state.accumulator, static_cast<int>(dataset_word & 63));
            if (word == target_word) target_value = first_write;
            if (second_word == target_word) target_value = second_write;
            state.registers[lane] = mixed + state.accumulator + first_scratch;
            const std::size_t neighbor = (lane + 2) & (REGISTER_COUNT - 1);
            state.registers[neighbor] ^=
                std::rotl(dataset_word + first_scratch, static_cast<int>(second_scratch & 63));
            CheckpointPut(
                target_word, target_value, first_word, first_scratch,
                second_word, word, first_write, second_write,
                iteration + 1, state);
        }
        MemoPut(stop, target_word, target_value, depth);
        ++completed_values;
        return target_value;
    }

    std::uint64_t ValueAtIterative(
        std::uint64_t target_word, std::uint64_t stop, std::uint64_t depth = 1)
    {
        std::size_t stack_size{1};
        if (!PushEnter(0, target_word, stop, depth)) return 0;
        std::uint64_t returned_value{0};
        const std::size_t word_count = m_owner.WordCount();
        while (stack_size != 0) {
            const std::size_t slot = stack_size - 1;
            IterativeFrame frame = ReadFrame(slot);
            if (frame.phase == FRAME_ENTER) {
                ChargeOperation(frame.stop, frame.target_word, frame.depth);
                ++calls;
                if (frame.stop == 0) {
                    ++completed_values;
                    returned_value = 0;
                    --stack_size;
                    continue;
                }
                maximum_depth = std::max(maximum_depth, std::uint64_t{frame.depth});
                if (frame.depth > m_owner.Layout().frame_capacity) {
                    throw RecursiveRegenerationExhausted{
                        "frame_capacity", frame.stop, frame.target_word, frame.depth};
                }
                std::uint64_t cached{0};
                if (MemoGet(frame.stop, frame.target_word, frame.depth, cached)) {
                    returned_value = cached;
                    --stack_size;
                    continue;
                }
                std::uint64_t start{0};
                bool target_value_restored{false};
                if (!CheckpointFind(
                        frame.target_word, frame.stop, frame.depth, start,
                        frame.target_value, target_value_restored, frame.state)) {
                    frame.state = InitializeMachineState(
                        m_context, m_header_digest, m_nonce_bytes, m_params_bytes);
                    frame.target_value = 0;
                } else if (!target_value_restored) {
                    throw std::logic_error(
                        "iterative dependency bundle did not restore target value");
                }
                frame.iteration = static_cast<std::uint32_t>(start);
                frame.phase = FRAME_NEED_FIRST;
                WriteFrame(slot, frame);
                continue;
            }
            if (frame.phase == FRAME_NEED_FIRST) {
                if (frame.iteration >= frame.stop) {
                    MemoPut(
                        frame.stop, frame.target_word, frame.target_value, frame.depth);
                    ++completed_values;
                    returned_value = frame.target_value;
                    --stack_size;
                    continue;
                }
                if (iterations >= m_work_limit) {
                    throw RecursiveRegenerationExhausted{
                        "work_limit", frame.stop, frame.target_word, frame.depth};
                }
                ChargeOperation(frame.stop, frame.target_word, frame.depth);
                ++iterations;
                const std::size_t lane = frame.iteration & (REGISTER_COUNT - 1);
                const ScheduleEntry& entry =
                    m_context.schedule[frame.iteration & (SCHEDULE_LENGTH - 1)];
                const std::uint64_t first_selector =
                    frame.state.registers[lane] ^
                    std::rotl(
                        frame.state.registers[(lane + 1) & (REGISTER_COUNT - 1)],
                        static_cast<int>(frame.iteration & 63)) ^
                    frame.state.accumulator ^ entry.immediate;
                const std::uint64_t first_word = first_selector & (word_count - 1);
                frame.phase = FRAME_HAVE_FIRST;
                WriteFrame(slot, frame);
                if (PushEnter(
                        stack_size, first_word, frame.iteration, frame.depth + 1)) {
                    ++stack_size;
                } else {
                    returned_value = 0;
                }
                continue;
            }

            const std::size_t lane = frame.iteration & (REGISTER_COUNT - 1);
            const std::size_t pass = frame.iteration / word_count;
            const ScheduleEntry& entry =
                m_context.schedule[frame.iteration & (SCHEDULE_LENGTH - 1)];
            const std::uint64_t x = frame.state.registers[lane];
            const std::uint64_t y =
                frame.state.registers[(lane + 1) & (REGISTER_COUNT - 1)];
            const std::uint64_t z =
                frame.state.registers[(lane + 3) & (REGISTER_COUNT - 1)];
            const std::uint64_t first_selector =
                x ^ std::rotl(y, static_cast<int>(frame.iteration & 63)) ^
                frame.state.accumulator ^ entry.immediate;
            const std::uint64_t first_word = first_selector & (word_count - 1);
            if (frame.phase == FRAME_HAVE_FIRST) {
                frame.first_scratch = returned_value;
                const std::uint64_t dataset_selector =
                    frame.first_scratch ^ z ^
                    std::rotl(
                        frame.state.accumulator,
                        static_cast<int>((lane + pass) & 63)) ^
                    frame.iteration;
                const std::uint64_t dataset_word =
                    ReadMemory(m_context.dataset, dataset_selector);
                const std::uint64_t second_selector =
                    dataset_word ^
                    frame.state.registers[(lane + 5) & (REGISTER_COUNT - 1)] ^
                    std::rotl(
                        frame.first_scratch + frame.state.accumulator,
                        static_cast<int>(entry.immediate & 63));
                const std::uint64_t second_word = second_selector & (word_count - 1);
                frame.phase = FRAME_HAVE_SECOND;
                WriteFrame(slot, frame);
                if (PushEnter(
                        stack_size, second_word, frame.iteration, frame.depth + 1)) {
                    ++stack_size;
                } else {
                    returned_value = 0;
                }
                continue;
            }
            if (frame.phase != FRAME_HAVE_SECOND) {
                throw std::logic_error("invalid iterative work-stack phase");
            }
            const std::uint64_t second_scratch = returned_value;
            const std::uint64_t dataset_selector =
                frame.first_scratch ^ z ^
                std::rotl(
                    frame.state.accumulator,
                    static_cast<int>((lane + pass) & 63)) ^
                frame.iteration;
            const std::uint64_t dataset_word =
                ReadMemory(m_context.dataset, dataset_selector);
            const std::uint64_t second_selector =
                dataset_word ^
                frame.state.registers[(lane + 5) & (REGISTER_COUNT - 1)] ^
                std::rotl(
                    frame.first_scratch + frame.state.accumulator,
                    static_cast<int>(entry.immediate & 63));
            const std::uint64_t second_word = second_selector & (word_count - 1);
            const std::uint64_t mixed = ExecuteOperation(
                entry.opcode, x, y, frame.first_scratch, second_scratch,
                dataset_word, entry.immediate);
            frame.state.accumulator =
                std::rotl(
                    frame.state.accumulator ^ mixed ^ dataset_word,
                    static_cast<int>(
                        (frame.first_scratch ^ second_scratch ^ entry.immediate) & 63)) +
                frame.first_scratch + entry.immediate + frame.iteration;
            const std::uint64_t first_write =
                mixed ^ frame.state.accumulator ^ second_scratch;
            const std::uint64_t second_write =
                second_scratch ^ std::rotl(
                    mixed + frame.state.accumulator,
                    static_cast<int>(dataset_word & 63));
            const std::uint64_t sequential_word = frame.iteration & (word_count - 1);
            if (sequential_word == frame.target_word) frame.target_value = first_write;
            if (second_word == frame.target_word) frame.target_value = second_write;
            frame.state.registers[lane] =
                mixed + frame.state.accumulator + frame.first_scratch;
            const std::size_t neighbor = (lane + 2) & (REGISTER_COUNT - 1);
            frame.state.registers[neighbor] ^=
                std::rotl(
                    dataset_word + frame.first_scratch,
                    static_cast<int>(second_scratch & 63));
            CheckpointPut(
                frame.target_word, frame.target_value, first_word,
                frame.first_scratch, second_word, sequential_word,
                first_write, second_write, frame.iteration + 1, frame.state);
            ++frame.iteration;
            frame.phase = FRAME_NEED_FIRST;
            frame.first_scratch = 0;
            WriteFrame(slot, frame);
        }
        return returned_value;
    }

    std::uint64_t calls{0}, cache_hits{0}, completed_values{0}, iterations{0};
    std::uint64_t maximum_depth{0}, memo_entries{0}, memo_peak_entries{0};
    std::uint64_t memo_evictions{0}, memo_probes{0}, memo_shifted_bytes{0};
    std::uint64_t checkpoint_lookups{0}, checkpoint_hits{0}, checkpoint_captures{0};
    std::uint64_t checkpoint_replacements{0}, checkpoint_probes{0};
    std::uint64_t total_operations{0};

private:
    static constexpr std::uint8_t FRAME_ENTER{0};
    static constexpr std::uint8_t FRAME_NEED_FIRST{1};
    static constexpr std::uint8_t FRAME_HAVE_FIRST{2};
    static constexpr std::uint8_t FRAME_HAVE_SECOND{3};

    struct IterativeFrame {
        std::uint32_t target_word{0}, stop{0}, iteration{0};
        std::uint16_t depth{0};
        std::uint8_t phase{FRAME_ENTER};
        std::uint64_t target_value{0};
        MachineState state{};
        std::uint64_t first_scratch{0};
    };

    IterativeFrame ReadFrame(std::size_t slot) const
    {
        const std::size_t offset = m_owner.FrameOffset(slot);
        const std::uint8_t* data = m_owner.Arena().data() + offset;
        IterativeFrame frame{};
        frame.target_word = ReadLE32(data);
        frame.stop = ReadLE32(data + 4);
        frame.iteration = ReadLE32(data + 8);
        frame.depth = ReadLE16(data + 12);
        frame.phase = data[14];
        frame.target_value = ReadLE64(data + 16);
        for (std::size_t lane{0}; lane < REGISTER_COUNT; ++lane) {
            frame.state.registers[lane] = ReadLE64(data + 24 + lane * 8);
        }
        frame.state.accumulator = ReadLE64(data + 88);
        frame.first_scratch = ReadLE64(data + 96);
        return frame;
    }

    void WriteFrame(std::size_t slot, const IterativeFrame& frame)
    {
        const std::size_t offset = m_owner.FrameOffset(slot);
        std::uint8_t* data = m_owner.Arena().data() + offset;
        WriteLE32(data, frame.target_word);
        WriteLE32(data + 4, frame.stop);
        WriteLE32(data + 8, frame.iteration);
        WriteLE16(data + 12, frame.depth);
        data[14] = frame.phase;
        data[15] = 0;
        WriteLE64(data + 16, frame.target_value);
        for (std::size_t lane{0}; lane < REGISTER_COUNT; ++lane) {
            WriteLE64(data + 24 + lane * 8, frame.state.registers[lane]);
        }
        WriteLE64(data + 88, frame.state.accumulator);
        WriteLE64(data + 96, frame.first_scratch);
    }

    bool PushEnter(
        std::size_t slot, std::uint64_t target_word,
        std::uint64_t stop, std::uint64_t depth)
    {
        if (stop == 0) {
            ChargeOperation(stop, target_word, depth);
            ++calls;
            ++completed_values;
            return false;
        }
        if (slot >= m_owner.Layout().frame_capacity) {
            ChargeOperation(stop, target_word, depth);
            ++calls;
            maximum_depth = std::max(maximum_depth, depth);
            throw RecursiveRegenerationExhausted{
                "frame_capacity", stop, target_word, depth};
        }
        if (target_word > std::numeric_limits<std::uint32_t>::max() ||
            stop > std::numeric_limits<std::uint32_t>::max() ||
            depth > std::numeric_limits<std::uint16_t>::max()) {
            throw std::invalid_argument("iterative frame field exceeds packed range");
        }
        IterativeFrame frame{};
        frame.target_word = static_cast<std::uint32_t>(target_word);
        frame.stop = static_cast<std::uint32_t>(stop);
        frame.depth = static_cast<std::uint16_t>(depth);
        WriteFrame(slot, frame);
        return true;
    }

    void ChargeOperation(
        std::uint64_t stop, std::uint64_t word, std::uint64_t depth)
    {
        if (m_operation_limit != 0 && total_operations >= m_operation_limit) {
            throw RecursiveRegenerationExhausted{
                "operation_limit", stop, word, depth};
        }
        ++total_operations;
    }

    bool CheckpointFind(
        std::uint64_t target_word,
        std::uint64_t stop,
        std::uint64_t depth,
        std::uint64_t& selected_stop,
        std::uint64_t& target_value,
        bool& target_value_restored,
        MachineState& state)
    {
        const RecursiveLayout& layout = m_owner.Layout();
        if (layout.checkpoint_capacity == 0) return false;
        ++checkpoint_lookups;
        if (layout.checkpoint_entry_bytes == DEPENDENCY_BUNDLE_ENTRY_BYTES) {
            bool found{false};
            std::size_t selected_offset{0};
            std::size_t selected_value_index{0};
            for (std::size_t slot{0}; slot < layout.checkpoint_capacity; ++slot) {
                ChargeOperation(stop, target_word, depth);
                ++checkpoint_probes;
                const std::size_t offset = m_owner.CheckpointOffset(slot);
                const std::uint32_t stored_stop = ReadLE32(m_owner.Arena().data() + offset);
                if (stored_stop == EMPTY_CHECKPOINT_STOP || stored_stop >= stop ||
                    (found && stored_stop <= selected_stop)) continue;
                for (std::size_t i{0}; i < DEPENDENCY_BUNDLE_WIDTH; ++i) {
                    if (ReadLE16(m_owner.Arena().data() + offset + 4 + i * 2) == target_word) {
                        found = true;
                        selected_stop = stored_stop;
                        selected_offset = offset;
                        selected_value_index = i;
                        break;
                    }
                }
            }
            if (!found) return false;
            target_value = ReadLE64(
                m_owner.Arena().data() + selected_offset +
                DEPENDENCY_BUNDLE_VALUE_OFFSET + selected_value_index * 8);
            for (std::size_t lane{0}; lane < REGISTER_COUNT; ++lane) {
                state.registers[lane] = ReadLE64(
                    m_owner.Arena().data() + selected_offset +
                    DEPENDENCY_BUNDLE_STATE_OFFSET + lane * 8);
            }
            state.accumulator = ReadLE64(
                m_owner.Arena().data() + selected_offset +
                DEPENDENCY_BUNDLE_STATE_OFFSET + REGISTER_COUNT * 8);
            target_value_restored = true;
            ++checkpoint_hits;
            return true;
        }
        if (layout.checkpoint_entry_bytes == TARGET_CHECKPOINT_ENTRY_BYTES) {
            ChargeOperation(stop, target_word, depth);
            ++checkpoint_probes;
            const std::size_t slot =
                static_cast<std::size_t>(target_word) % layout.checkpoint_capacity;
            const std::size_t offset = m_owner.CheckpointOffset(slot);
            const std::uint32_t stored_stop = ReadLE32(m_owner.Arena().data() + offset);
            const std::uint32_t stored_word = ReadLE32(m_owner.Arena().data() + offset + 4);
            if (stored_stop == EMPTY_CHECKPOINT_STOP || stored_word != target_word ||
                stored_stop >= stop) return false;
            selected_stop = stored_stop;
            target_value = ReadLE64(m_owner.Arena().data() + offset + 8);
            for (std::size_t lane{0}; lane < REGISTER_COUNT; ++lane) {
                state.registers[lane] =
                    ReadLE64(m_owner.Arena().data() + offset + 16 + lane * 8);
            }
            state.accumulator =
                ReadLE64(m_owner.Arena().data() + offset + 16 + REGISTER_COUNT * 8);
            target_value_restored = true;
            ++checkpoint_hits;
            return true;
        }
        bool found{false};
        std::size_t selected_offset{0};
        for (std::size_t slot{0}; slot < layout.checkpoint_capacity; ++slot) {
            ChargeOperation(stop, target_word, depth);
            ++checkpoint_probes;
            const std::size_t offset = m_owner.CheckpointOffset(slot);
            const std::uint32_t stored_stop = ReadLE32(m_owner.Arena().data() + offset);
            if (stored_stop != EMPTY_CHECKPOINT_STOP && stored_stop < stop &&
                (!found || stored_stop > selected_stop)) {
                found = true;
                selected_stop = stored_stop;
                selected_offset = offset;
            }
        }
        if (!found) return false;
        ++checkpoint_hits;
        for (std::size_t lane{0}; lane < REGISTER_COUNT; ++lane) {
            state.registers[lane] =
                ReadLE64(m_owner.Arena().data() + selected_offset + 8 + lane * 8);
        }
        state.accumulator =
            ReadLE64(m_owner.Arena().data() + selected_offset + 8 + REGISTER_COUNT * 8);
        return true;
    }

    void CheckpointPut(
        std::uint64_t target_word,
        std::uint64_t target_value,
        std::uint64_t first_word,
        std::uint64_t first_scratch,
        std::uint64_t second_word,
        std::uint64_t sequential_word,
        std::uint64_t first_write,
        std::uint64_t second_write,
        std::uint64_t stop,
        const MachineState& state)
    {
        const RecursiveLayout& layout = m_owner.Layout();
        if (layout.checkpoint_capacity == 0 || stop == 0 ||
            stop % layout.checkpoint_stride != 0) return;
        const bool dependency_bundles =
            layout.checkpoint_entry_bytes == DEPENDENCY_BUNDLE_ENTRY_BYTES;
        if (dependency_bundles) {
            const std::size_t slot =
                static_cast<std::size_t>(target_word) % layout.checkpoint_capacity;
            const std::size_t offset = m_owner.CheckpointOffset(slot);
            const std::uint32_t stored_stop = ReadLE32(m_owner.Arena().data() + offset);
            const std::uint16_t stored_anchor = ReadLE16(m_owner.Arena().data() + offset + 4);
            if (stored_stop != EMPTY_CHECKPOINT_STOP &&
                (stored_stop != stop || stored_anchor != target_word)) {
                ++checkpoint_replacements;
            }
            std::array<std::uint16_t, DEPENDENCY_BUNDLE_WIDTH> words{};
            words.fill(EMPTY_BUNDLE_WORD);
            std::array<std::uint64_t, DEPENDENCY_BUNDLE_WIDTH> values{};
            std::size_t count{0};
            const auto add = [&](std::uint64_t word, std::uint64_t value) {
                for (std::size_t i{0}; i < count; ++i) {
                    if (words[i] == word) {
                        values[i] = value;
                        return;
                    }
                }
                if (count == DEPENDENCY_BUNDLE_WIDTH) return;
                words[count] = static_cast<std::uint16_t>(word);
                values[count] = value;
                ++count;
            };
            std::uint64_t first_value = first_scratch;
            if (first_word == sequential_word) first_value = first_write;
            if (first_word == second_word) first_value = second_write;
            add(target_word, target_value);
            add(first_word, first_value);
            add(second_word, second_write);
            add(sequential_word, sequential_word == second_word ? second_write : first_write);
            WriteLE32(m_owner.Arena().data() + offset, static_cast<std::uint32_t>(stop));
            for (std::size_t i{0}; i < DEPENDENCY_BUNDLE_WIDTH; ++i) {
                WriteLE16(m_owner.Arena().data() + offset + 4 + i * 2, words[i]);
                WriteLE64(
                    m_owner.Arena().data() + offset +
                    DEPENDENCY_BUNDLE_VALUE_OFFSET + i * 8,
                    values[i]);
            }
            for (std::size_t i{12}; i < DEPENDENCY_BUNDLE_VALUE_OFFSET; ++i) {
                m_owner.Arena()[offset + i] = 0;
            }
            for (std::size_t lane{0}; lane < REGISTER_COUNT; ++lane) {
                WriteLE64(
                    m_owner.Arena().data() + offset +
                    DEPENDENCY_BUNDLE_STATE_OFFSET + lane * 8,
                    state.registers[lane]);
            }
            WriteLE64(
                m_owner.Arena().data() + offset +
                DEPENDENCY_BUNDLE_STATE_OFFSET + REGISTER_COUNT * 8,
                state.accumulator);
            ++checkpoint_captures;
            return;
        }
        const bool target_aware =
            layout.checkpoint_entry_bytes == TARGET_CHECKPOINT_ENTRY_BYTES;
        const std::size_t slot = target_aware
            ? static_cast<std::size_t>(target_word) % layout.checkpoint_capacity
            : static_cast<std::size_t>(stop / layout.checkpoint_stride) % layout.checkpoint_capacity;
        const std::size_t offset = m_owner.CheckpointOffset(slot);
        const std::uint32_t stored_stop = ReadLE32(m_owner.Arena().data() + offset);
        const std::uint32_t stored_word = target_aware
            ? ReadLE32(m_owner.Arena().data() + offset + 4) : 0;
        if (stored_stop != EMPTY_CHECKPOINT_STOP &&
            (stored_stop != stop || (target_aware && stored_word != target_word))) {
            ++checkpoint_replacements;
        }
        WriteLE32(m_owner.Arena().data() + offset, static_cast<std::uint32_t>(stop));
        const std::size_t state_offset = target_aware ? 16 : 8;
        if (target_aware) {
            WriteLE32(m_owner.Arena().data() + offset + 4, static_cast<std::uint32_t>(target_word));
            WriteLE64(m_owner.Arena().data() + offset + 8, target_value);
        }
        for (std::size_t lane{0}; lane < REGISTER_COUNT; ++lane) {
            WriteLE64(
                m_owner.Arena().data() + offset + state_offset + lane * 8,
                state.registers[lane]);
        }
        WriteLE64(
            m_owner.Arena().data() + offset + state_offset + REGISTER_COUNT * 8,
            state.accumulator);
        ++checkpoint_captures;
    }

    bool MemoGet(
        std::uint64_t stop, std::uint64_t word, std::uint64_t depth,
        std::uint64_t& value)
    {
        ChargeOperation(stop, word, depth);
        ++memo_probes;
        const std::uint32_t key = m_owner.MemoKey(stop, word);
        const std::size_t set = m_owner.MemoSet(key);
        for (std::size_t way{0}; way < RECURSIVE_MEMO_WAYS; ++way) {
            const std::size_t offset = m_owner.MemoSetOffset(set, way);
            if (ReadLE32(m_owner.Arena().data() + offset) == key) {
                value = ReadLE64(m_owner.Arena().data() + offset + 4);
                ++cache_hits;
                return true;
            }
        }
        return false;
    }

    void MemoPut(
        std::uint64_t stop, std::uint64_t word, std::uint64_t value,
        std::uint64_t depth)
    {
        ChargeOperation(stop, word, depth);
        ++memo_probes;
        const std::uint32_t key = m_owner.MemoKey(stop, word);
        const std::size_t set = m_owner.MemoSet(key);
        std::size_t selected = RECURSIVE_MEMO_WAYS;
        for (std::size_t way{0}; way < RECURSIVE_MEMO_WAYS; ++way) {
            const std::uint32_t stored =
                ReadLE32(m_owner.Arena().data() + m_owner.MemoSetOffset(set, way));
            if (stored == key) { selected = way; break; }
            if (stored == RECURSIVE_EMPTY_MEMO_KEY && selected == RECURSIVE_MEMO_WAYS) {
                selected = way;
            }
        }
        if (selected == RECURSIVE_MEMO_WAYS) {
            selected = ((key >> 16) ^ key) & (RECURSIVE_MEMO_WAYS - 1);
            ++memo_evictions;
        }
        const std::size_t offset = m_owner.MemoSetOffset(set, selected);
        if (ReadLE32(m_owner.Arena().data() + offset) == RECURSIVE_EMPTY_MEMO_KEY) {
            ++memo_entries;
            memo_peak_entries = std::max(memo_peak_entries, memo_entries);
        }
        WriteLE32(m_owner.Arena().data() + offset, key);
        WriteLE64(m_owner.Arena().data() + offset + 4, value);
    }

    RecursiveArena& m_owner;
    const EpochContext& m_context;
    const Bytes& m_header_digest;
    const Bytes& m_nonce_bytes;
    const Bytes& m_params_bytes;
    std::uint64_t m_work_limit;
    std::uint64_t m_operation_limit;
};

class PackedReplayExhausted final : public std::runtime_error {
public:
    PackedReplayExhausted() : std::runtime_error("packed replay value area is full") {}
};

class PackedReconstructionArena {
public:
    PackedReconstructionArena(std::size_t scratchpad_bytes, std::size_t budget_bytes)
        : m_word_count(scratchpad_bytes / 8)
    {
        m_layout.budget_bytes = budget_bytes;
        m_layout.fixed_state_reserve_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES;
        m_layout.arena_bytes = budget_bytes - BOUNDED_FIXED_STATE_RESERVE_BYTES;
        m_layout.canonical_write_bitmap_bytes = (m_word_count + 7) / 8;
        m_layout.replay_bitmap_bytes = m_layout.canonical_write_bitmap_bytes;
        m_rank_chunks = (m_word_count + PACKED_RANK_CHUNK_WORDS - 1) / PACKED_RANK_CHUNK_WORDS;
        m_layout.rank_directory_bytes = (m_rank_chunks + 1) * 2;
        const std::size_t fixed = m_layout.canonical_write_bitmap_bytes +
            m_layout.replay_bitmap_bytes + m_layout.rank_directory_bytes;
        if (m_layout.arena_bytes <= fixed + BOUNDED_CACHE_ENTRY_BYTES + 8) {
            throw std::invalid_argument("budget cannot hold packed replay and primary cache");
        }
        const std::size_t available = m_layout.arena_bytes - fixed;
        m_layout.primary_cache_bytes =
            available * PACKED_PRIMARY_NUMERATOR / PACKED_PRIMARY_DENOMINATOR;
        m_layout.primary_cache_bytes -=
            m_layout.primary_cache_bytes % BOUNDED_CACHE_ENTRY_BYTES;
        m_layout.primary_cache_capacity =
            m_layout.primary_cache_bytes / BOUNDED_CACHE_ENTRY_BYTES;
        const std::size_t replay_bytes = available - m_layout.primary_cache_bytes;
        m_layout.replay_value_capacity = replay_bytes / 8;
        m_layout.replay_value_bytes = m_layout.replay_value_capacity * 8;
        m_layout.unused_arena_bytes = replay_bytes - m_layout.replay_value_bytes;
        m_layout.admitted_bytes = budget_bytes;
        if (m_layout.primary_cache_capacity == 0 || m_layout.replay_value_capacity == 0) {
            throw std::invalid_argument("budget cannot split packed replay and primary cache");
        }
        m_primary_offset = m_layout.canonical_write_bitmap_bytes;
        m_replay_bitmap_offset = m_primary_offset + m_layout.primary_cache_bytes;
        m_rank_offset = m_replay_bitmap_offset + m_layout.replay_bitmap_bytes;
        m_values_offset = m_rank_offset + m_layout.rank_directory_bytes;
        m_arena.resize(m_layout.arena_bytes, 0);
        for (std::size_t slot{0}; slot < m_layout.primary_cache_capacity; ++slot) {
            WriteLE64(m_arena.data() + PrimaryOffset(slot), EmptyTag());
        }
        m_stats.budget_bytes = m_layout.budget_bytes;
        m_stats.fixed_state_reserve_bytes = m_layout.fixed_state_reserve_bytes;
        m_stats.arena_bytes = m_layout.arena_bytes;
        m_stats.write_bitmap_bytes = m_layout.canonical_write_bitmap_bytes;
        m_stats.cache_entry_bytes = BOUNDED_CACHE_ENTRY_BYTES;
        m_stats.primary_cache_capacity = m_layout.primary_cache_capacity;
        m_stats.primary_cache_bytes = m_layout.primary_cache_bytes;
        m_stats.replay_capacity = m_layout.replay_value_capacity;
        m_stats.replay_workspace_bytes = m_layout.replay_bitmap_bytes +
            m_layout.rank_directory_bytes + m_layout.replay_value_bytes;
        m_stats.unused_arena_bytes = m_layout.unused_arena_bytes;
        m_stats.admitted_bytes = m_layout.admitted_bytes;
    }

    void SetConsumer(std::uint64_t consumer) { m_consumer = consumer; m_slot = 0; }

    std::uint64_t Read(std::uint64_t selector)
    {
        const std::size_t word = Word(selector);
        const std::uint8_t slot = m_slot++;
        ++m_stats.canonical_reads;
        const std::size_t offset = PrimaryOffset(word % m_layout.primary_cache_capacity);
        if (ReadLE64(m_arena.data() + offset) == word) {
            ++m_stats.cache_hits;
            return ReadLE64(m_arena.data() + offset + 8);
        }
        if (!CanonicalWritten(word)) {
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
        m_arena[word / 8] |= std::uint8_t{1} << (word & 7);
        ++m_stats.writes;
    }

    void Retain(std::uint64_t word, std::uint64_t value)
    {
        StorePrimary(static_cast<std::size_t>(word), value, true);
    }

    void ResetReplay()
    {
        std::fill(
            m_arena.begin() + static_cast<std::ptrdiff_t>(m_replay_bitmap_offset),
            m_arena.begin() + static_cast<std::ptrdiff_t>(m_values_offset),
            std::uint8_t{0});
        m_replay_distinct = 0;
        m_replay_rank_probes = 0;
        m_replay_shifted_bytes = 0;
        m_stats.replay_peak_entries = 0;
    }

    std::uint64_t ReplayRead(std::uint64_t selector)
    {
        const std::size_t word = Word(selector);
        if (!ReplayPresent(word)) return 0;
        return ReadLE64(m_arena.data() + m_values_offset + ReplayRank(word) * 8);
    }

    std::uint64_t ReplayReadExact(std::uint64_t word)
    {
        const std::size_t exact = static_cast<std::size_t>(word);
        if (!ReplayPresent(exact)) {
            throw std::logic_error("materialized word is absent from packed replay state");
        }
        return ReadLE64(m_arena.data() + m_values_offset + ReplayRank(exact) * 8);
    }

    void ReplayWrite(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = Word(selector);
        const bool present = ReplayPresent(word);
        const std::size_t rank = ReplayRank(word);
        if (present) {
            WriteLE64(m_arena.data() + m_values_offset + rank * 8, value);
            return;
        }
        if (m_replay_distinct == m_layout.replay_value_capacity) {
            throw PackedReplayExhausted{};
        }
        const std::size_t move_bytes = (m_replay_distinct - rank) * 8;
        if (move_bytes != 0) {
            auto first = m_arena.begin() + static_cast<std::ptrdiff_t>(m_values_offset + rank * 8);
            auto last = first + static_cast<std::ptrdiff_t>(move_bytes);
            std::copy_backward(first, last, last + 8);
            m_replay_shifted_bytes += move_bytes;
        }
        WriteLE64(m_arena.data() + m_values_offset + rank * 8, value);
        m_arena[m_replay_bitmap_offset + word / 8] |= std::uint8_t{1} << (word & 7);
        FenwickAdd(word / PACKED_RANK_CHUNK_WORDS);
        ++m_replay_distinct;
        m_stats.replay_peak_entries = std::max<std::uint64_t>(
            m_stats.replay_peak_entries, m_replay_distinct);
    }

    const PackedLayout& Layout() const { return m_layout; }
    const BoundedReconstructionStats& Stats() const { return m_stats; }
    std::uint64_t ReplayRankProbes() const { return m_replay_rank_probes; }
    std::uint64_t ReplayShiftedBytes() const { return m_replay_shifted_bytes; }

private:
    static constexpr std::uint64_t EmptyTag() { return std::numeric_limits<std::uint64_t>::max(); }
    std::size_t Word(std::uint64_t selector) const { return static_cast<std::size_t>(selector) & (m_word_count - 1); }
    std::size_t PrimaryOffset(std::size_t slot) const { return m_primary_offset + slot * BOUNDED_CACHE_ENTRY_BYTES; }
    bool CanonicalWritten(std::size_t word) const { return (m_arena[word / 8] & (std::uint8_t{1} << (word & 7))) != 0; }
    bool ReplayPresent(std::size_t word) const { return (m_arena[m_replay_bitmap_offset + word / 8] & (std::uint8_t{1} << (word & 7))) != 0; }

    std::uint16_t ReadRank(std::size_t index) const
    {
        const std::size_t offset = m_rank_offset + index * 2;
        return static_cast<std::uint16_t>(m_arena[offset]) |
            static_cast<std::uint16_t>(m_arena[offset + 1] << 8);
    }

    void WriteRank(std::size_t index, std::uint16_t value)
    {
        const std::size_t offset = m_rank_offset + index * 2;
        m_arena[offset] = static_cast<std::uint8_t>(value);
        m_arena[offset + 1] = static_cast<std::uint8_t>(value >> 8);
    }

    std::size_t FenwickPrefix(std::size_t chunk)
    {
        std::size_t total{0};
        for (std::size_t index{chunk}; index > 0; index -= index & (~index + 1)) {
            total += ReadRank(index);
            ++m_replay_rank_probes;
        }
        return total;
    }

    void FenwickAdd(std::size_t chunk)
    {
        for (std::size_t index{chunk + 1}; index <= m_rank_chunks; index += index & (~index + 1)) {
            WriteRank(index, static_cast<std::uint16_t>(ReadRank(index) + 1));
            ++m_replay_rank_probes;
        }
    }

    std::size_t ReplayRank(std::size_t word)
    {
        const std::size_t chunk = word / PACKED_RANK_CHUNK_WORDS;
        std::size_t total = FenwickPrefix(chunk);
        const std::size_t first_byte = chunk * PACKED_RANK_CHUNK_WORDS / 8;
        const std::size_t final_byte = word / 8;
        for (std::size_t byte{first_byte}; byte < final_byte; ++byte) {
            total += std::popcount(m_arena[m_replay_bitmap_offset + byte]);
            ++m_replay_rank_probes;
        }
        const std::uint8_t partial = m_arena[m_replay_bitmap_offset + final_byte];
        const std::uint8_t mask = static_cast<std::uint8_t>((std::uint16_t{1} << (word & 7)) - 1);
        total += std::popcount(static_cast<std::uint8_t>(partial & mask));
        ++m_replay_rank_probes;
        return total;
    }

    void StorePrimary(std::size_t word, std::uint64_t value, bool count_eviction)
    {
        const std::size_t offset = PrimaryOffset(word % m_layout.primary_cache_capacity);
        const std::uint64_t previous = ReadLE64(m_arena.data() + offset);
        if (count_eviction && previous != EmptyTag() && previous != word) ++m_stats.evictions;
        WriteLE64(m_arena.data() + offset, word);
        WriteLE64(m_arena.data() + offset + 8, value);
    }

    std::size_t m_word_count;
    std::size_t m_rank_chunks{0};
    std::size_t m_primary_offset{0};
    std::size_t m_replay_bitmap_offset{0};
    std::size_t m_rank_offset{0};
    std::size_t m_values_offset{0};
    std::uint64_t m_consumer{0};
    std::uint8_t m_slot{0};
    std::uint64_t m_replay_distinct{0};
    std::uint64_t m_replay_rank_probes{0};
    std::uint64_t m_replay_shifted_bytes{0};
    Bytes m_arena;
    PackedLayout m_layout;
    BoundedReconstructionStats m_stats;
};

class PackedReplayView {
public:
    explicit PackedReplayView(PackedReconstructionArena& arena) : m_arena(arena) {}
    std::uint64_t Read(std::uint64_t selector) { return m_arena.ReplayRead(selector); }
    void Write(std::uint64_t selector, std::uint64_t value) { m_arena.ReplayWrite(selector, value); }
private:
    PackedReconstructionArena& m_arena;
};

class PagedReplayExhausted final : public std::runtime_error {
public:
    PagedReplayExhausted() : std::runtime_error("paged replay has no free physical page") {}
};

class PagedReconstructionArena {
public:
    PagedReconstructionArena(std::size_t scratchpad_bytes, std::size_t budget_bytes)
        : m_word_count(scratchpad_bytes / 8)
    {
        m_layout.budget_bytes = budget_bytes;
        m_layout.fixed_state_reserve_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES;
        m_layout.arena_bytes = budget_bytes - BOUNDED_FIXED_STATE_RESERVE_BYTES;
        m_layout.canonical_write_bitmap_bytes = (m_word_count + 7) / 8;
        m_layout.replay_bitmap_bytes = m_layout.canonical_write_bitmap_bytes;
        m_rank_chunks = (m_word_count + PACKED_RANK_CHUNK_WORDS - 1) / PACKED_RANK_CHUNK_WORDS;
        m_layout.rank_directory_bytes = (m_rank_chunks + 1) * 2;
        const std::size_t base = m_layout.arena_bytes - 2 * m_layout.canonical_write_bitmap_bytes - m_layout.rank_directory_bytes;
        m_layout.primary_cache_bytes = base * PACKED_PRIMARY_NUMERATOR / PACKED_PRIMARY_DENOMINATOR;
        m_layout.primary_cache_bytes -= m_layout.primary_cache_bytes % BOUNDED_CACHE_ENTRY_BYTES;
        m_layout.primary_cache_capacity = m_layout.primary_cache_bytes / BOUNDED_CACHE_ENTRY_BYTES;
        const std::size_t replay_budget = base - m_layout.primary_cache_bytes;
        m_layout.page_slots = PAGED_SLOTS;
        m_layout.max_pages = replay_budget / (PAGED_BYTES + PAGED_METADATA_BYTES);
        m_layout.page_directory_bytes = m_layout.max_pages * 2;
        m_layout.page_count_bytes = m_layout.max_pages * 2;
        m_layout.replay_value_slots = m_layout.max_pages * PAGED_SLOTS;
        m_layout.replay_value_bytes = m_layout.max_pages * PAGED_BYTES;
        m_layout.unused_arena_bytes = replay_budget - m_layout.page_directory_bytes - m_layout.page_count_bytes - m_layout.replay_value_bytes;
        m_layout.admitted_bytes = budget_bytes;
        if (m_layout.primary_cache_capacity == 0 || m_layout.max_pages == 0) {
            throw std::invalid_argument("budget cannot hold paged replay and primary cache");
        }
        m_primary_offset = m_layout.canonical_write_bitmap_bytes;
        m_replay_bitmap_offset = m_primary_offset + m_layout.primary_cache_bytes;
        m_rank_offset = m_replay_bitmap_offset + m_layout.replay_bitmap_bytes;
        m_order_offset = m_rank_offset + m_layout.rank_directory_bytes;
        m_count_offset = m_order_offset + m_layout.page_directory_bytes;
        m_values_offset = m_count_offset + m_layout.page_count_bytes;
        m_arena.resize(m_layout.arena_bytes, 0);
        for (std::size_t slot{0}; slot < m_layout.primary_cache_capacity; ++slot) {
            WriteLE64(m_arena.data() + PrimaryOffset(slot), EmptyTag());
        }
        m_stats.budget_bytes = budget_bytes;
        m_stats.fixed_state_reserve_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES;
        m_stats.arena_bytes = m_layout.arena_bytes;
        m_stats.write_bitmap_bytes = m_layout.canonical_write_bitmap_bytes;
        m_stats.cache_entry_bytes = BOUNDED_CACHE_ENTRY_BYTES;
        m_stats.primary_cache_capacity = m_layout.primary_cache_capacity;
        m_stats.primary_cache_bytes = m_layout.primary_cache_bytes;
        m_stats.replay_capacity = m_layout.replay_value_slots;
        m_stats.replay_workspace_bytes = m_layout.replay_bitmap_bytes + m_layout.rank_directory_bytes + m_layout.page_directory_bytes + m_layout.page_count_bytes + m_layout.replay_value_bytes;
        m_stats.unused_arena_bytes = m_layout.unused_arena_bytes;
        m_stats.admitted_bytes = budget_bytes;
    }

    void SetConsumer(std::uint64_t consumer) { m_consumer = consumer; m_slot = 0; }
    std::uint64_t Read(std::uint64_t selector)
    {
        const std::size_t word = Word(selector);
        const std::uint8_t slot = m_slot++;
        ++m_stats.canonical_reads;
        const std::size_t offset = PrimaryOffset(word % m_layout.primary_cache_capacity);
        if (ReadLE64(m_arena.data() + offset) == word) { ++m_stats.cache_hits; return ReadLE64(m_arena.data() + offset + 8); }
        if ((m_arena[word / 8] & (std::uint8_t{1} << (word & 7))) == 0) { ++m_stats.initial_zero_reads; return 0; }
        ++m_stats.materialized_misses;
        throw BoundedReadMiss{0, m_consumer, slot, word};
    }
    void Write(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = Word(selector);
        StorePrimary(word, value);
        m_arena[word / 8] |= std::uint8_t{1} << (word & 7);
        ++m_stats.writes;
    }
    void Retain(std::uint64_t word, std::uint64_t value) { StorePrimary(static_cast<std::size_t>(word), value); }
    void ResetReplay()
    {
        std::fill(m_arena.begin() + static_cast<std::ptrdiff_t>(m_replay_bitmap_offset),
                  m_arena.begin() + static_cast<std::ptrdiff_t>(m_values_offset), std::uint8_t{0});
        m_logical_pages = m_allocated_pages = m_distinct = 0;
        m_peak_values = m_peak_pages = m_rank_probes = m_directory_probes = m_shifted_bytes = 0;
    }
    std::uint64_t ReplayRead(std::uint64_t selector)
    {
        const std::size_t word = Word(selector);
        if (!Present(word)) return 0;
        const Location location = Locate(Rank(word), false);
        return ReadLE64(m_arena.data() + PageOffset(location.page, location.local));
    }
    std::uint64_t ReplayReadExact(std::uint64_t word)
    {
        const std::size_t exact = static_cast<std::size_t>(word);
        if (!Present(exact)) throw std::logic_error("materialized word is absent from paged replay state");
        const Location location = Locate(Rank(exact), false);
        return ReadLE64(m_arena.data() + PageOffset(location.page, location.local));
    }
    void ReplayWrite(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = Word(selector);
        const bool present = Present(word);
        const std::size_t rank = Rank(word);
        Location location = m_logical_pages == 0 ? AllocateFirst() : Locate(rank, true);
        if (present) { WriteLE64(m_arena.data() + PageOffset(location.page, location.local), value); return; }
        std::size_t count = Count(location.page);
        if (count == PAGED_SLOTS) { location = Split(location); count = Count(location.page); }
        const std::size_t move_bytes = (count - location.local) * 8;
        if (move_bytes != 0) {
            auto first = m_arena.begin() + static_cast<std::ptrdiff_t>(PageOffset(location.page, location.local));
            auto last = first + static_cast<std::ptrdiff_t>(move_bytes);
            std::copy_backward(first, last, last + 8);
            m_shifted_bytes += move_bytes;
        }
        WriteLE64(m_arena.data() + PageOffset(location.page, location.local), value);
        SetCount(location.page, count + 1);
        m_arena[m_replay_bitmap_offset + word / 8] |= std::uint8_t{1} << (word & 7);
        RankAdd(word);
        ++m_distinct;
        m_peak_values = std::max(m_peak_values, m_distinct);
    }
    const PagedLayout& Layout() const { return m_layout; }
    const BoundedReconstructionStats& Stats() const { return m_stats; }
    std::uint64_t Distinct() const { return m_distinct; }
    std::uint64_t AllocatedPages() const { return m_allocated_pages; }
    std::uint64_t PeakValues() const { return m_peak_values; }
    std::uint64_t PeakPages() const { return m_peak_pages; }
    std::uint64_t RankProbes() const { return m_rank_probes; }
    std::uint64_t DirectoryProbes() const { return m_directory_probes; }
    std::uint64_t ShiftedBytes() const { return m_shifted_bytes; }

private:
    struct Location { std::size_t position, page, local; };
    static constexpr std::uint64_t EmptyTag() { return std::numeric_limits<std::uint64_t>::max(); }
    std::size_t Word(std::uint64_t selector) const { return static_cast<std::size_t>(selector) & (m_word_count - 1); }
    std::size_t PrimaryOffset(std::size_t slot) const { return m_primary_offset + slot * BOUNDED_CACHE_ENTRY_BYTES; }
    std::size_t PageOffset(std::size_t page, std::size_t slot = 0) const { return m_values_offset + (page * PAGED_SLOTS + slot) * 8; }
    std::uint16_t U16(std::size_t offset) const { return static_cast<std::uint16_t>(m_arena[offset]) | static_cast<std::uint16_t>(m_arena[offset + 1] << 8); }
    void SetU16(std::size_t offset, std::uint16_t value) { m_arena[offset] = static_cast<std::uint8_t>(value); m_arena[offset + 1] = static_cast<std::uint8_t>(value >> 8); }
    std::size_t Order(std::size_t position) { ++m_directory_probes; return U16(m_order_offset + position * 2); }
    std::size_t Count(std::size_t page) { ++m_directory_probes; return U16(m_count_offset + page * 2); }
    void SetCount(std::size_t page, std::size_t count) { SetU16(m_count_offset + page * 2, static_cast<std::uint16_t>(count)); }
    bool Present(std::size_t word) const { return (m_arena[m_replay_bitmap_offset + word / 8] & (std::uint8_t{1} << (word & 7))) != 0; }
    std::size_t Rank(std::size_t word)
    {
        const std::size_t chunk = word / PACKED_RANK_CHUNK_WORDS;
        std::size_t total{0};
        for (std::size_t index{chunk}; index > 0; index -= index & (~index + 1)) { total += U16(m_rank_offset + index * 2); ++m_rank_probes; }
        const std::size_t first_byte = chunk * PACKED_RANK_CHUNK_WORDS / 8;
        const std::size_t final_byte = word / 8;
        for (std::size_t byte{first_byte}; byte < final_byte; ++byte) { total += std::popcount(m_arena[m_replay_bitmap_offset + byte]); ++m_rank_probes; }
        const std::uint8_t mask = static_cast<std::uint8_t>((std::uint16_t{1} << (word & 7)) - 1);
        total += std::popcount(static_cast<std::uint8_t>(m_arena[m_replay_bitmap_offset + final_byte] & mask));
        ++m_rank_probes;
        return total;
    }
    void RankAdd(std::size_t word)
    {
        for (std::size_t index{word / PACKED_RANK_CHUNK_WORDS + 1}; index <= m_rank_chunks; index += index & (~index + 1)) {
            SetU16(m_rank_offset + index * 2, static_cast<std::uint16_t>(U16(m_rank_offset + index * 2) + 1));
            ++m_rank_probes;
        }
    }
    Location Locate(std::size_t rank, bool for_insert)
    {
        std::size_t cumulative{0};
        for (std::size_t position{0}; position < m_logical_pages; ++position) {
            const std::size_t page = Order(position), count = Count(page);
            if (rank < cumulative + count) return {position, page, rank - cumulative};
            cumulative += count;
        }
        if (for_insert && m_logical_pages != 0 && rank == cumulative) {
            const std::size_t position = m_logical_pages - 1, page = Order(position);
            return {position, page, Count(page)};
        }
        throw std::logic_error("paged replay rank is outside occupied values");
    }
    Location AllocateFirst()
    {
        if (m_allocated_pages == m_layout.max_pages) throw PagedReplayExhausted{};
        const std::size_t page = m_allocated_pages++;
        m_logical_pages = 1;
        SetU16(m_order_offset, static_cast<std::uint16_t>(page));
        SetCount(page, 0);
        m_peak_pages = std::max(m_peak_pages, m_allocated_pages);
        return {0, page, 0};
    }
    Location Split(Location location)
    {
        if (m_allocated_pages == m_layout.max_pages) throw PagedReplayExhausted{};
        const std::size_t new_page = m_allocated_pages++, split = PAGED_SLOTS / 2, moved = PAGED_SLOTS - split;
        std::copy_n(m_arena.begin() + static_cast<std::ptrdiff_t>(PageOffset(location.page, split)), moved * 8,
                    m_arena.begin() + static_cast<std::ptrdiff_t>(PageOffset(new_page)));
        m_shifted_bytes += moved * 8;
        SetCount(location.page, split); SetCount(new_page, moved);
        const std::size_t insert_position = location.position + 1;
        const std::size_t directory_move = (m_logical_pages - insert_position) * 2;
        if (directory_move != 0) {
            auto first = m_arena.begin() + static_cast<std::ptrdiff_t>(m_order_offset + insert_position * 2);
            auto last = first + static_cast<std::ptrdiff_t>(directory_move);
            std::copy_backward(first, last, last + 2);
            m_shifted_bytes += directory_move;
        }
        SetU16(m_order_offset + insert_position * 2, static_cast<std::uint16_t>(new_page));
        ++m_logical_pages;
        m_peak_pages = std::max(m_peak_pages, m_allocated_pages);
        if (location.local >= split) return {insert_position, new_page, location.local - split};
        return location;
    }
    void StorePrimary(std::size_t word, std::uint64_t value)
    {
        const std::size_t offset = PrimaryOffset(word % m_layout.primary_cache_capacity);
        const std::uint64_t previous = ReadLE64(m_arena.data() + offset);
        if (previous != EmptyTag() && previous != word) ++m_stats.evictions;
        WriteLE64(m_arena.data() + offset, word); WriteLE64(m_arena.data() + offset + 8, value);
    }
    std::size_t m_word_count, m_rank_chunks{0}, m_primary_offset{0}, m_replay_bitmap_offset{0};
    std::size_t m_rank_offset{0}, m_order_offset{0}, m_count_offset{0}, m_values_offset{0};
    std::uint64_t m_consumer{0}, m_logical_pages{0}, m_allocated_pages{0}, m_distinct{0};
    std::uint64_t m_peak_values{0}, m_peak_pages{0}, m_rank_probes{0}, m_directory_probes{0}, m_shifted_bytes{0};
    std::uint8_t m_slot{0};
    Bytes m_arena;
    PagedLayout m_layout;
    BoundedReconstructionStats m_stats;
};

class PagedReplayView {
public:
    explicit PagedReplayView(PagedReconstructionArena& arena) : m_arena(arena) {}
    std::uint64_t Read(std::uint64_t selector) { return m_arena.ReplayRead(selector); }
    void Write(std::uint64_t selector, std::uint64_t value) { m_arena.ReplayWrite(selector, value); }
private:
    PagedReconstructionArena& m_arena;
};

class IndexedGapReplayExhausted final : public std::runtime_error {
public:
    IndexedGapReplayExhausted() : std::runtime_error("indexed-gap replay has no free physical page") {}
};

class IndexedGapReconstructionArena {
public:
    IndexedGapReconstructionArena(std::size_t scratchpad_bytes, std::size_t budget_bytes)
        : m_word_count(scratchpad_bytes / 8)
    {
        m_layout.budget_bytes = budget_bytes;
        m_layout.fixed_state_reserve_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES;
        m_layout.arena_bytes = budget_bytes - BOUNDED_FIXED_STATE_RESERVE_BYTES;
        m_layout.canonical_write_bitmap_bytes = (m_word_count + 7) / 8;
        m_layout.replay_bitmap_bytes = m_layout.canonical_write_bitmap_bytes;
        m_rank_chunks = (m_word_count + PACKED_RANK_CHUNK_WORDS - 1) / PACKED_RANK_CHUNK_WORDS;
        m_layout.rank_directory_bytes = (m_rank_chunks + 1) * 2;
        const std::size_t base = m_layout.arena_bytes - 2 * m_layout.canonical_write_bitmap_bytes - m_layout.rank_directory_bytes;
        m_layout.primary_cache_bytes = base * PACKED_PRIMARY_NUMERATOR / PACKED_PRIMARY_DENOMINATOR;
        m_layout.primary_cache_bytes -= m_layout.primary_cache_bytes % BOUNDED_CACHE_ENTRY_BYTES;
        m_layout.primary_cache_capacity = m_layout.primary_cache_bytes / BOUNDED_CACHE_ENTRY_BYTES;
        const std::size_t replay_budget = base - m_layout.primary_cache_bytes;
        m_layout.page_slots = PAGED_SLOTS;
        m_layout.max_pages = (replay_budget - 2) / (PAGED_BYTES + PAGED_METADATA_BYTES + 2);
        m_layout.page_directory_bytes = m_layout.max_pages * 2;
        m_layout.page_count_bytes = m_layout.max_pages * 2;
        m_layout.page_index_bytes = (m_layout.max_pages + 1) * 2;
        m_layout.replay_value_slots = m_layout.max_pages * PAGED_SLOTS;
        m_layout.replay_value_bytes = m_layout.max_pages * PAGED_BYTES;
        m_layout.unused_arena_bytes = replay_budget - m_layout.page_directory_bytes - m_layout.page_count_bytes - m_layout.page_index_bytes - m_layout.replay_value_bytes;
        m_layout.admitted_bytes = budget_bytes;
        if (m_layout.primary_cache_capacity == 0 || m_layout.max_pages == 0) {
            throw std::invalid_argument("budget cannot hold indexed-gap replay and primary cache");
        }
        m_primary_offset = m_layout.canonical_write_bitmap_bytes;
        m_replay_bitmap_offset = m_primary_offset + m_layout.primary_cache_bytes;
        m_rank_offset = m_replay_bitmap_offset + m_layout.replay_bitmap_bytes;
        m_order_offset = m_rank_offset + m_layout.rank_directory_bytes;
        m_count_offset = m_order_offset + m_layout.page_directory_bytes;
        m_index_offset = m_count_offset + m_layout.page_count_bytes;
        m_values_offset = m_index_offset + m_layout.page_index_bytes;
        m_arena.resize(m_layout.arena_bytes, 0);
        for (std::size_t slot{0}; slot < m_layout.primary_cache_capacity; ++slot) {
            WriteLE64(m_arena.data() + PrimaryOffset(slot), EmptyTag());
        }
        m_stats.budget_bytes = budget_bytes;
        m_stats.fixed_state_reserve_bytes = BOUNDED_FIXED_STATE_RESERVE_BYTES;
        m_stats.arena_bytes = m_layout.arena_bytes;
        m_stats.write_bitmap_bytes = m_layout.canonical_write_bitmap_bytes;
        m_stats.cache_entry_bytes = BOUNDED_CACHE_ENTRY_BYTES;
        m_stats.primary_cache_capacity = m_layout.primary_cache_capacity;
        m_stats.primary_cache_bytes = m_layout.primary_cache_bytes;
        m_stats.replay_capacity = m_layout.replay_value_slots;
        m_stats.replay_workspace_bytes = m_layout.replay_bitmap_bytes + m_layout.rank_directory_bytes + m_layout.page_directory_bytes + m_layout.page_count_bytes + m_layout.page_index_bytes + m_layout.replay_value_bytes;
        m_stats.unused_arena_bytes = m_layout.unused_arena_bytes;
        m_stats.admitted_bytes = budget_bytes;
    }

    void SetConsumer(std::uint64_t consumer) { m_consumer = consumer; m_slot = 0; }
    std::uint64_t Read(std::uint64_t selector)
    {
        const std::size_t word = Word(selector);
        const std::uint8_t slot = m_slot++;
        ++m_stats.canonical_reads;
        const std::size_t offset = PrimaryOffset(word % m_layout.primary_cache_capacity);
        if (ReadLE64(m_arena.data() + offset) == word) { ++m_stats.cache_hits; return ReadLE64(m_arena.data() + offset + 8); }
        if ((m_arena[word / 8] & (std::uint8_t{1} << (word & 7))) == 0) { ++m_stats.initial_zero_reads; return 0; }
        ++m_stats.materialized_misses;
        throw BoundedReadMiss{0, m_consumer, slot, word};
    }
    void Write(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = Word(selector);
        StorePrimary(word, value);
        m_arena[word / 8] |= std::uint8_t{1} << (word & 7);
        ++m_stats.writes;
    }
    void Retain(std::uint64_t word, std::uint64_t value) { StorePrimary(static_cast<std::size_t>(word), value); }
    void ResetReplay()
    {
        std::fill(m_arena.begin() + static_cast<std::ptrdiff_t>(m_replay_bitmap_offset),
                  m_arena.begin() + static_cast<std::ptrdiff_t>(m_values_offset), std::uint8_t{0});
        m_logical_pages = m_allocated_pages = m_distinct = 0;
        m_peak_values = m_peak_pages = m_rank_probes = m_index_probes = 0;
        m_directory_probes = m_rebalances = m_shifted_bytes = 0;
    }
    std::uint64_t ReplayRead(std::uint64_t selector)
    {
        const std::size_t word = Word(selector);
        if (!Present(word)) return 0;
        const Location location = Locate(Rank(word), false);
        return ReadLE64(m_arena.data() + PageOffset(location.page, location.local));
    }
    std::uint64_t ReplayReadExact(std::uint64_t word)
    {
        const std::size_t exact = static_cast<std::size_t>(word);
        if (!Present(exact)) throw std::logic_error("materialized word is absent from indexed-gap replay state");
        const Location location = Locate(Rank(exact), false);
        return ReadLE64(m_arena.data() + PageOffset(location.page, location.local));
    }
    void ReplayWrite(std::uint64_t selector, std::uint64_t value)
    {
        const std::size_t word = Word(selector);
        const bool present = Present(word);
        const std::size_t rank = Rank(word);
        Location location = m_logical_pages == 0 ? AllocateFirst() : Locate(rank, true);
        if (present) { WriteLE64(m_arena.data() + PageOffset(location.page, location.local), value); return; }
        std::size_t count = Count(location.page);
        if (count == PAGED_SLOTS && Rebalance(location, value)) {
            // The value was inserted while an adjacent page absorbed one existing boundary value.
        } else {
            if (count == PAGED_SLOTS) { location = Split(location); count = Count(location.page); }
            const std::size_t move_bytes = (count - location.local) * 8;
            if (move_bytes != 0) {
                auto first = m_arena.begin() + static_cast<std::ptrdiff_t>(PageOffset(location.page, location.local));
                auto last = first + static_cast<std::ptrdiff_t>(move_bytes);
                std::copy_backward(first, last, last + 8);
                m_shifted_bytes += move_bytes;
            }
            WriteLE64(m_arena.data() + PageOffset(location.page, location.local), value);
            ChangeCount(location.position, location.page, count + 1);
        }
        m_arena[m_replay_bitmap_offset + word / 8] |= std::uint8_t{1} << (word & 7);
        RankAdd(word);
        ++m_distinct;
        m_peak_values = std::max(m_peak_values, m_distinct);
    }
    const IndexedGapLayout& Layout() const { return m_layout; }
    const BoundedReconstructionStats& Stats() const { return m_stats; }
    std::uint64_t Distinct() const { return m_distinct; }
    std::uint64_t AllocatedPages() const { return m_allocated_pages; }
    std::uint64_t PeakValues() const { return m_peak_values; }
    std::uint64_t PeakPages() const { return m_peak_pages; }
    std::uint64_t RankProbes() const { return m_rank_probes; }
    std::uint64_t IndexProbes() const { return m_index_probes; }
    std::uint64_t DirectoryProbes() const { return m_directory_probes; }
    std::uint64_t Rebalances() const { return m_rebalances; }
    std::uint64_t ShiftedBytes() const { return m_shifted_bytes; }

private:
    struct Location { std::size_t position, page, local; };
    static constexpr std::uint64_t EmptyTag() { return std::numeric_limits<std::uint64_t>::max(); }
    std::size_t Word(std::uint64_t selector) const { return static_cast<std::size_t>(selector) & (m_word_count - 1); }
    std::size_t PrimaryOffset(std::size_t slot) const { return m_primary_offset + slot * BOUNDED_CACHE_ENTRY_BYTES; }
    std::size_t PageOffset(std::size_t page, std::size_t slot = 0) const { return m_values_offset + (page * PAGED_SLOTS + slot) * 8; }
    std::uint16_t U16(std::size_t offset) const { return static_cast<std::uint16_t>(m_arena[offset]) | static_cast<std::uint16_t>(m_arena[offset + 1] << 8); }
    void SetU16(std::size_t offset, std::uint16_t value) { m_arena[offset] = static_cast<std::uint8_t>(value); m_arena[offset + 1] = static_cast<std::uint8_t>(value >> 8); }
    std::size_t Order(std::size_t position) { ++m_directory_probes; return U16(m_order_offset + position * 2); }
    std::size_t Count(std::size_t page) { ++m_directory_probes; return U16(m_count_offset + page * 2); }
    void SetCount(std::size_t page, std::size_t count) { SetU16(m_count_offset + page * 2, static_cast<std::uint16_t>(count)); }
    bool Present(std::size_t word) const { return (m_arena[m_replay_bitmap_offset + word / 8] & (std::uint8_t{1} << (word & 7))) != 0; }
    void IndexAdd(std::size_t position, std::ptrdiff_t delta)
    {
        for (std::size_t index{position + 1}; index <= m_layout.max_pages; index += index & (~index + 1)) {
            const std::size_t offset = m_index_offset + index * 2;
            SetU16(offset, static_cast<std::uint16_t>(static_cast<std::ptrdiff_t>(U16(offset)) + delta));
            ++m_index_probes;
        }
    }
    void ChangeCount(std::size_t position, std::size_t page, std::size_t count)
    {
        const std::size_t previous = Count(page);
        SetCount(page, count);
        IndexAdd(position, static_cast<std::ptrdiff_t>(count) - static_cast<std::ptrdiff_t>(previous));
    }
    void RebuildIndex()
    {
        std::fill(m_arena.begin() + static_cast<std::ptrdiff_t>(m_index_offset),
                  m_arena.begin() + static_cast<std::ptrdiff_t>(m_index_offset + m_layout.page_index_bytes), std::uint8_t{0});
        for (std::size_t position{0}; position < m_logical_pages; ++position) {
            const std::size_t page = Order(position);
            IndexAdd(position, static_cast<std::ptrdiff_t>(Count(page)));
        }
    }
    std::size_t Rank(std::size_t word)
    {
        const std::size_t chunk = word / PACKED_RANK_CHUNK_WORDS;
        std::size_t total{0};
        for (std::size_t index{chunk}; index > 0; index -= index & (~index + 1)) { total += U16(m_rank_offset + index * 2); ++m_rank_probes; }
        const std::size_t first_byte = chunk * PACKED_RANK_CHUNK_WORDS / 8;
        const std::size_t final_byte = word / 8;
        for (std::size_t byte{first_byte}; byte < final_byte; ++byte) { total += std::popcount(m_arena[m_replay_bitmap_offset + byte]); ++m_rank_probes; }
        const std::uint8_t mask = static_cast<std::uint8_t>((std::uint16_t{1} << (word & 7)) - 1);
        total += std::popcount(static_cast<std::uint8_t>(m_arena[m_replay_bitmap_offset + final_byte] & mask));
        ++m_rank_probes;
        return total;
    }
    void RankAdd(std::size_t word)
    {
        for (std::size_t index{word / PACKED_RANK_CHUNK_WORDS + 1}; index <= m_rank_chunks; index += index & (~index + 1)) {
            SetU16(m_rank_offset + index * 2, static_cast<std::uint16_t>(U16(m_rank_offset + index * 2) + 1));
            ++m_rank_probes;
        }
    }
    Location Locate(std::size_t rank, bool for_insert)
    {
        if (for_insert && m_logical_pages != 0 && rank == m_distinct) {
            const std::size_t position = m_logical_pages - 1, page = Order(position);
            return {position, page, Count(page)};
        }
        std::size_t index{0}, total{0}, step{1};
        while ((step << 1) <= m_layout.max_pages) step <<= 1;
        while (step != 0) {
            const std::size_t candidate = index + step;
            if (candidate <= m_logical_pages) {
                const std::size_t value = U16(m_index_offset + candidate * 2);
                ++m_index_probes;
                if (total + value <= rank) { index = candidate; total += value; }
            }
            step >>= 1;
        }
        if (index >= m_logical_pages) throw std::logic_error("indexed-gap rank is outside occupied values");
        return {index, Order(index), rank - total};
    }
    Location AllocateFirst()
    {
        if (m_allocated_pages == m_layout.max_pages) throw IndexedGapReplayExhausted{};
        const std::size_t page = m_allocated_pages++;
        m_logical_pages = 1;
        SetU16(m_order_offset, static_cast<std::uint16_t>(page));
        SetCount(page, 0);
        m_peak_pages = std::max(m_peak_pages, m_allocated_pages);
        return {0, page, 0};
    }
    Location Split(Location location)
    {
        if (m_allocated_pages == m_layout.max_pages) throw IndexedGapReplayExhausted{};
        const std::size_t new_page = m_allocated_pages++, split = PAGED_SLOTS / 2, moved = PAGED_SLOTS - split;
        std::copy_n(m_arena.begin() + static_cast<std::ptrdiff_t>(PageOffset(location.page, split)), moved * 8,
                    m_arena.begin() + static_cast<std::ptrdiff_t>(PageOffset(new_page)));
        m_shifted_bytes += moved * 8;
        SetCount(location.page, split); SetCount(new_page, moved);
        const std::size_t insert_position = location.position + 1;
        const std::size_t directory_move = (m_logical_pages - insert_position) * 2;
        if (directory_move != 0) {
            auto first = m_arena.begin() + static_cast<std::ptrdiff_t>(m_order_offset + insert_position * 2);
            auto last = first + static_cast<std::ptrdiff_t>(directory_move);
            std::copy_backward(first, last, last + 2);
            m_shifted_bytes += directory_move;
        }
        SetU16(m_order_offset + insert_position * 2, static_cast<std::uint16_t>(new_page));
        ++m_logical_pages;
        m_peak_pages = std::max(m_peak_pages, m_allocated_pages);
        RebuildIndex();
        if (location.local >= split) return {insert_position, new_page, location.local - split};
        return location;
    }
    bool Rebalance(Location location, std::uint64_t value)
    {
        std::size_t right_page{0}, right_count{0}, left_page{0}, left_count{0};
        if (location.position + 1 < m_logical_pages) { right_page = Order(location.position + 1); right_count = Count(right_page); }
        if (location.position > 0) { left_page = Order(location.position - 1); left_count = Count(left_page); }
        const std::size_t right_free = location.position + 1 < m_logical_pages ? PAGED_SLOTS - right_count : 0;
        const std::size_t left_free = location.position > 0 ? PAGED_SLOTS - left_count : 0;
        if (right_free == 0 && left_free == 0) return false;
        ++m_rebalances;
        if (right_free >= left_free) {
            if (right_count != 0) {
                auto first = m_arena.begin() + static_cast<std::ptrdiff_t>(PageOffset(right_page));
                auto last = first + static_cast<std::ptrdiff_t>(right_count * 8);
                std::copy_backward(first, last, last + 8);
                m_shifted_bytes += right_count * 8;
            }
            if (location.local == PAGED_SLOTS) {
                WriteLE64(m_arena.data() + PageOffset(right_page), value);
            } else {
                WriteLE64(m_arena.data() + PageOffset(right_page), ReadLE64(m_arena.data() + PageOffset(location.page, PAGED_SLOTS - 1)));
                m_shifted_bytes += 8;
                const std::size_t move = (PAGED_SLOTS - 1 - location.local) * 8;
                if (move != 0) {
                    auto first = m_arena.begin() + static_cast<std::ptrdiff_t>(PageOffset(location.page, location.local));
                    auto last = first + static_cast<std::ptrdiff_t>(move);
                    std::copy_backward(first, last, last + 8);
                    m_shifted_bytes += move;
                }
                WriteLE64(m_arena.data() + PageOffset(location.page, location.local), value);
            }
            ChangeCount(location.position + 1, right_page, right_count + 1);
            return true;
        }
        if (location.local == 0) {
            WriteLE64(m_arena.data() + PageOffset(left_page, left_count), value);
        } else {
            WriteLE64(m_arena.data() + PageOffset(left_page, left_count), ReadLE64(m_arena.data() + PageOffset(location.page)));
            m_shifted_bytes += 8;
            const std::size_t move = (location.local - 1) * 8;
            if (move != 0) {
                auto first = m_arena.begin() + static_cast<std::ptrdiff_t>(PageOffset(location.page, 1));
                std::copy(first, first + static_cast<std::ptrdiff_t>(move),
                          m_arena.begin() + static_cast<std::ptrdiff_t>(PageOffset(location.page)));
                m_shifted_bytes += move;
            }
            WriteLE64(m_arena.data() + PageOffset(location.page, location.local - 1), value);
        }
        ChangeCount(location.position - 1, left_page, left_count + 1);
        return true;
    }
    void StorePrimary(std::size_t word, std::uint64_t value)
    {
        const std::size_t offset = PrimaryOffset(word % m_layout.primary_cache_capacity);
        const std::uint64_t previous = ReadLE64(m_arena.data() + offset);
        if (previous != EmptyTag() && previous != word) ++m_stats.evictions;
        WriteLE64(m_arena.data() + offset, word); WriteLE64(m_arena.data() + offset + 8, value);
    }
    std::size_t m_word_count, m_rank_chunks{0}, m_primary_offset{0}, m_replay_bitmap_offset{0};
    std::size_t m_rank_offset{0}, m_order_offset{0}, m_count_offset{0}, m_index_offset{0}, m_values_offset{0};
    std::uint64_t m_consumer{0}, m_logical_pages{0}, m_allocated_pages{0}, m_distinct{0};
    std::uint64_t m_peak_values{0}, m_peak_pages{0}, m_rank_probes{0}, m_index_probes{0};
    std::uint64_t m_directory_probes{0}, m_rebalances{0}, m_shifted_bytes{0};
    std::uint8_t m_slot{0};
    Bytes m_arena;
    IndexedGapLayout m_layout;
    BoundedReconstructionStats m_stats;
};

class IndexedGapReplayView {
public:
    explicit IndexedGapReplayView(IndexedGapReconstructionArena& arena) : m_arena(arena) {}
    std::uint64_t Read(std::uint64_t selector) { return m_arena.ReplayRead(selector); }
    void Write(std::uint64_t selector, std::uint64_t value) { m_arena.ReplayWrite(selector, value); }
private:
    IndexedGapReconstructionArena& m_arena;
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

RecursiveRegenerationResult ProbeFirstRecursiveRegeneration(
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
    const std::uint64_t total_iterations =
        context.params.passes * (context.params.scratchpad_bytes / 8);
    RecursiveArena arena(context.params.scratchpad_bytes, context.params.scratchpad_bytes / 2);
    RecursiveRegenerator regenerator(
        arena, context, header_digest, nonce_bytes, params_bytes, RECURSIVE_WORK_LIMIT);
    RecursiveRegenerationResult result{};
    result.layout = arena.Layout();
    Bytes transcript_input = DomainBytes(DOMAIN_RECURSIVE_REGENERATION);

    auto boundary_commitment = [&](bool recursive,
                                   const BoundedReadMiss& miss,
                                   const std::uint64_t* value) {
        Bytes encoded = recursive
            ? DomainBytes(DOMAIN_RECURSIVE_REGENERATION)
            : DomainBytes(DOMAIN_RECONSTRUCTION);
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

    bool stopped{false};
    for (std::uint64_t iteration{0}; iteration < total_iterations; ++iteration) {
        while (true) {
            arena.SetConsumer(iteration);
            try {
                ExecuteMixIteration(context, arena, state, iteration);
                break;
            } catch (const BoundedReadMiss& miss) {
                ++result.reconstruction_attempts;
                if (result.reconstructed_misses != 0) {
                    result.has_refusal = true;
                    result.refusal_consumer = miss.consumer;
                    result.refusal_slot = miss.slot;
                    result.refusal_word = miss.word;
                    result.refusal_state_commitment =
                        boundary_commitment(false, miss, nullptr);
                    stopped = true;
                    break;
                }
                try {
                    const std::uint64_t value =
                        regenerator.ValueAt(miss.word, miss.consumer);
                    const Bytes commitment = boundary_commitment(true, miss, &value);
                    result.has_first = true;
                    result.first_reconstruction = {
                        miss.consumer, miss.word, value, regenerator.calls,
                        regenerator.cache_hits, regenerator.completed_values,
                        regenerator.iterations, regenerator.maximum_depth,
                        regenerator.memo_peak_entries, regenerator.memo_evictions,
                        regenerator.memo_probes, regenerator.memo_shifted_bytes,
                        miss.slot, commitment,
                    };
                    Append(transcript_input, commitment);
                    arena.Retain(miss.word, value);
                    result.reconstructed_misses = 1;
                } catch (const RecursiveRegenerationExhausted& error) {
                    result.has_exhaustion = true;
                    result.exhaustion = {
                        error.reason, error.stop, error.word, error.depth,
                        regenerator.iterations,
                    };
                    stopped = true;
                    break;
                }
            }
        }
        if (stopped) break;
        ++result.completed_iterations;
    }
    if (result.has_exhaustion) {
        result.status = "refused_recursive_regeneration_exhausted";
    } else if (result.has_refusal) {
        result.status = "refused_after_first_recursive_regeneration";
    } else {
        result.status = "refused_unexpected_completion";
    }
    result.canonical_reads = arena.canonical_reads;
    result.cache_hits = arena.cache_hits;
    result.initial_zero_reads = arena.initial_zero_reads;
    result.materialized_misses = arena.materialized_misses;
    result.writes = arena.writes;
    result.evictions = arena.evictions;
    result.regeneration_calls = regenerator.calls;
    result.regeneration_cache_hits = regenerator.cache_hits;
    result.regeneration_completed_values = regenerator.completed_values;
    result.regeneration_iterations = regenerator.iterations;
    result.maximum_depth = regenerator.maximum_depth;
    result.memo_peak_entries = regenerator.memo_peak_entries;
    result.memo_evictions = regenerator.memo_evictions;
    result.memo_probes = regenerator.memo_probes;
    result.memo_shifted_bytes = regenerator.memo_shifted_bytes;
    result.transcript_commitment = Sha3_384(transcript_input);
    return result;
}

RepeatedRecursiveRegenerationResult ProbeRepeatedRecursiveRegeneration(
    const EpochContext& context,
    const Bytes& header,
    std::uint64_t nonce,
    std::uint64_t work_limit = RECURSIVE_WORK_LIMIT,
    std::size_t primary_numerator = RECURSIVE_PRIMARY_NUMERATOR,
    std::size_t primary_denominator = RECURSIVE_PRIMARY_DENOMINATOR,
    std::size_t checkpoint_capacity = 0,
    std::size_t checkpoint_stride = 0,
    bool target_checkpoints = false,
    bool dependency_bundles = false,
    std::uint64_t operation_limit = 0,
    std::size_t external_reserve_bytes = 0,
    bool rolling_transcript = false,
    bool iterative_work_stack = false)
{
    Validate(context.seed, context.params);
    if (header.empty() || header.size() > MAX_HEADER_BYTES) {
        throw std::invalid_argument("header size is outside the v1 research envelope");
    }
    if (iterative_work_stack && !dependency_bundles) {
        throw std::invalid_argument("iterative work stack requires dependency bundles");
    }
    const Bytes params_bytes = EncodeParams(context.params);
    Bytes nonce_bytes;
    AppendLE64(nonce_bytes, nonce);
    const Bytes header_digest = Sha3_384(header);
    MachineState state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
    const std::uint64_t total_iterations =
        context.params.passes * (context.params.scratchpad_bytes / 8);
    RecursiveArena arena(
        context.params.scratchpad_bytes,
        context.params.scratchpad_bytes / 2,
        primary_numerator,
        primary_denominator,
        checkpoint_capacity,
        checkpoint_stride,
        target_checkpoints,
        dependency_bundles,
        external_reserve_bytes);
    RecursiveRegenerator regenerator(
        arena, context, header_digest, nonce_bytes, params_bytes, work_limit,
        operation_limit);
    if (
        rolling_transcript
        && arena.ArenaCapacityBytes() >
            arena.Layout().arena_bytes + ALLOCATOR_ALLOWANCE_BYTES
    ) {
        throw std::runtime_error("arena capacity exceeds allocator allowance");
    }
    RepeatedRecursiveRegenerationResult result{};
    result.primary_numerator = primary_numerator;
    result.primary_denominator = primary_denominator;
    result.work_limit = work_limit;
    result.operation_limit = operation_limit;
    result.physical_accounting = rolling_transcript && !iterative_work_stack;
    result.iterative_accounting = iterative_work_stack;
    result.physical_total_budget_bytes = context.params.scratchpad_bytes / 2;
    result.physical_arena_allocation_bytes = arena.Layout().arena_bytes;
    result.layout = arena.Layout();
    if (dependency_bundles && iterative_work_stack) {
        result.status = "refused_iterative_work_stack_dependency_bundle_exhausted";
    } else if (dependency_bundles && rolling_transcript) {
        result.status = "refused_physically_accounted_dependency_bundle_exhausted";
    } else if (dependency_bundles && operation_limit != 0) {
        result.status = "refused_operation_bounded_dependency_bundle_exhausted";
    } else if (dependency_bundles) {
        result.status = "refused_dependency_bundle_regeneration_exhausted";
    } else if (target_checkpoints) {
        result.status = "refused_target_checkpoint_regeneration_exhausted";
    } else if (checkpoint_capacity != 0) {
        result.status = "refused_checkpoint_regeneration_exhausted";
    }
    Bytes transcript_input = dependency_bundles && iterative_work_stack
        ? DomainBytes(DOMAIN_ITERATIVE_WORK_STACK_DEPENDENCY_BUNDLE_REGENERATION)
        : dependency_bundles && rolling_transcript
        ? DomainBytes(DOMAIN_PHYSICALLY_ACCOUNTED_DEPENDENCY_BUNDLE_REGENERATION)
        : dependency_bundles && operation_limit != 0
        ? DomainBytes(DOMAIN_OPERATION_BOUNDED_DEPENDENCY_BUNDLE_REGENERATION)
        : dependency_bundles
        ? DomainBytes(DOMAIN_DEPENDENCY_BUNDLE_REGENERATION)
        : target_checkpoints ? DomainBytes(DOMAIN_TARGET_CHECKPOINT_REGENERATION)
        : (checkpoint_capacity == 0
            ? DomainBytes(DOMAIN_REPEATED_RECURSIVE_REGENERATION)
            : DomainBytes(DOMAIN_CHECKPOINT_REGENERATION));
    Bytes rolling_transcript_digest = rolling_transcript
        ? Sha3_384(transcript_input) : Bytes{};

    auto boundary_commitment = [&](const BoundedReadMiss& miss,
                                   const std::uint64_t* value) {
        Bytes encoded = dependency_bundles && iterative_work_stack
            ? DomainBytes(DOMAIN_ITERATIVE_WORK_STACK_DEPENDENCY_BUNDLE_REGENERATION)
            : dependency_bundles && rolling_transcript
            ? DomainBytes(DOMAIN_PHYSICALLY_ACCOUNTED_DEPENDENCY_BUNDLE_REGENERATION)
            : dependency_bundles && operation_limit != 0
            ? DomainBytes(DOMAIN_OPERATION_BOUNDED_DEPENDENCY_BUNDLE_REGENERATION)
            : dependency_bundles
            ? DomainBytes(DOMAIN_DEPENDENCY_BUNDLE_REGENERATION)
            : target_checkpoints ? DomainBytes(DOMAIN_TARGET_CHECKPOINT_REGENERATION)
            : (checkpoint_capacity == 0
                ? DomainBytes(DOMAIN_REPEATED_RECURSIVE_REGENERATION)
                : DomainBytes(DOMAIN_CHECKPOINT_REGENERATION));
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

    auto recover = [&](const BoundedReadMiss& miss) {
        ++result.reconstruction_attempts;
        const Bytes state_commitment = boundary_commitment(miss, nullptr);
        try {
            const std::uint64_t value = iterative_work_stack
                ? regenerator.ValueAtIterative(miss.word, miss.consumer)
                : regenerator.ValueAt(miss.word, miss.consumer);
            RecursiveBoundary boundary{
                miss.consumer, miss.word, value, regenerator.calls,
                regenerator.cache_hits, regenerator.completed_values,
                regenerator.iterations, regenerator.maximum_depth,
                regenerator.memo_peak_entries, regenerator.memo_evictions,
                regenerator.memo_probes, regenerator.memo_shifted_bytes,
                miss.slot, boundary_commitment(miss, &value),
            };
            boundary.checkpoint_lookups = regenerator.checkpoint_lookups;
            boundary.checkpoint_hits = regenerator.checkpoint_hits;
            boundary.checkpoint_captures = regenerator.checkpoint_captures;
            boundary.checkpoint_replacements = regenerator.checkpoint_replacements;
            boundary.checkpoint_probes = regenerator.checkpoint_probes;
            if (rolling_transcript) {
                Bytes rolling_input = rolling_transcript_digest;
                Append(rolling_input, boundary.commitment);
                rolling_transcript_digest = Sha3_384(rolling_input);
            } else {
                Append(transcript_input, boundary.commitment);
            }
            if (!result.has_first) {
                result.has_first = true;
                result.first_reconstruction = boundary;
            }
            result.has_last = true;
            result.last_reconstruction = boundary;
            arena.Retain(miss.word, value);
            ++result.reconstructed_misses;
            return true;
        } catch (const RecursiveRegenerationExhausted& error) {
            result.has_exhaustion = true;
            result.exhaustion = {
                error.reason, miss.consumer, miss.word, error.stop, error.depth,
                regenerator.iterations, miss.slot, state_commitment,
            };
            return false;
        }
    };

    bool stopped{false};
    for (std::uint64_t iteration{0}; iteration < total_iterations; ++iteration) {
        while (true) {
            arena.SetConsumer(iteration);
            try {
                ExecuteMixIteration(context, arena, state, iteration);
                break;
            } catch (const BoundedReadMiss& miss) {
                if (!recover(miss)) {
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
                std::rotl(selector ^ state.registers[i & (REGISTER_COUNT - 1)],
                          static_cast<int>((i + 1) & 63)) +
                0x9E3779B97F4A7C15ULL + i;
            while (true) {
                arena.SetConsumer(total_iterations + i);
                try {
                    samples[i] = arena.Read(selector);
                    break;
                } catch (const BoundedReadMiss& miss) {
                    if (!recover(miss)) {
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
        result.has_execution = true;
        result.execution_result = {
            Sha3_384(result_input), state.registers, context.schedule_digest,
            context.dataset_digest, memory_commitment,
        };
    }
    result.canonical_reads = arena.canonical_reads;
    result.cache_hits = arena.cache_hits;
    result.initial_zero_reads = arena.initial_zero_reads;
    result.materialized_misses = arena.materialized_misses;
    result.writes = arena.writes;
    result.evictions = arena.evictions;
    result.regeneration_calls = regenerator.calls;
    result.regeneration_cache_hits = regenerator.cache_hits;
    result.regeneration_completed_values = regenerator.completed_values;
    result.regeneration_iterations = regenerator.iterations;
    result.maximum_depth = regenerator.maximum_depth;
    result.memo_peak_entries = regenerator.memo_peak_entries;
    result.memo_evictions = regenerator.memo_evictions;
    result.memo_probes = regenerator.memo_probes;
    result.memo_shifted_bytes = regenerator.memo_shifted_bytes;
    result.checkpoint_lookups = regenerator.checkpoint_lookups;
    result.checkpoint_hits = regenerator.checkpoint_hits;
    result.checkpoint_captures = regenerator.checkpoint_captures;
    result.checkpoint_replacements = regenerator.checkpoint_replacements;
    result.checkpoint_probes = regenerator.checkpoint_probes;
    result.total_operations = regenerator.total_operations;
    result.transcript_commitment = rolling_transcript
        ? rolling_transcript_digest : Sha3_384(transcript_input);
    return result;
}

PackedReconstructionResult ProbePackedReconstruction(
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
    PackedReconstructionArena arena(context.params.scratchpad_bytes, context.params.scratchpad_bytes / 2);
    PackedReconstructionResult result{};
    Bytes transcript_input = DomainBytes(DOMAIN_PACKED_TRANSCRIPT);

    auto boundary_commitment = [&](const BoundedReadMiss& miss, const std::uint64_t* value) {
        Bytes encoded = DomainBytes(DOMAIN_PACKED_RECONSTRUCTION);
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
        PackedReplayView replay{arena};
        MachineState replay_state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
        const std::uint64_t replay_limit = std::min(miss.consumer, total_iterations);
        std::uint64_t replay_completed{0};
        try {
            for (std::uint64_t iteration{0}; iteration < replay_limit; ++iteration) {
                ExecuteMixIteration(context, replay, replay_state, iteration);
                ++replay_completed;
            }
        } catch (const PackedReplayExhausted&) {
            result.attempted_replay_iterations += replay_completed;
            result.cumulative_rank_probes += arena.ReplayRankProbes();
            result.cumulative_shifted_bytes += arena.ReplayShiftedBytes();
            result.max_replay_peak_entries = std::max(
                result.max_replay_peak_entries, arena.Stats().replay_peak_entries);
            result.has_exhaustion = true;
            result.exhaustion = {
                miss.consumer, miss.slot, miss.word, replay_completed,
                arena.Stats().replay_peak_entries, arena.ReplayRankProbes(),
                arena.ReplayShiftedBytes(), boundary_commitment(miss, nullptr),
            };
            return false;
        }
        result.attempted_replay_iterations += replay_completed;
        result.successful_replayed_iterations += replay_completed;
        result.all_replay_states_matched = result.all_replay_states_matched &&
            replay_state.registers == state.registers && replay_state.accumulator == state.accumulator;
        if (!result.all_replay_states_matched) {
            throw std::logic_error("packed replay machine state does not match the live prefix");
        }
        const std::uint64_t value = arena.ReplayReadExact(miss.word);
        result.cumulative_rank_probes += arena.ReplayRankProbes();
        result.cumulative_shifted_bytes += arena.ReplayShiftedBytes();
        result.max_replay_peak_entries = std::max(
            result.max_replay_peak_entries, arena.Stats().replay_peak_entries);
        PackedBoundary boundary{
            miss.consumer, miss.slot, miss.word, value, replay_completed,
            arena.Stats().replay_peak_entries, arena.ReplayRankProbes(),
            arena.ReplayShiftedBytes(), boundary_commitment(miss, &value),
        };
        Append(transcript_input, boundary.commitment);
        if (!result.has_first) {
            result.has_first = true;
            result.first_reconstruction = boundary;
        }
        result.last_reconstruction = boundary;
        ++result.reconstructed_misses;
        arena.Retain(miss.word, value);
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
                if (!reconstruct(miss)) { stopped = true; break; }
            }
        }
        if (stopped) break;
        ++result.completed_iterations;
    }

    std::array<std::uint64_t, FINAL_SAMPLE_WORDS> samples{};
    if (!stopped) {
        std::uint64_t selector = state.accumulator ^ state.registers[0] ^ state.registers[4];
        for (std::size_t i{0}; i < FINAL_SAMPLE_WORDS; ++i) {
            selector = std::rotl(
                selector ^ state.registers[i & (REGISTER_COUNT - 1)],
                static_cast<int>((i + 1) & 63)) + 0x9E3779B97F4A7C15ULL + i;
            while (true) {
                arena.SetConsumer(total_iterations + i);
                try {
                    samples[i] = arena.Read(selector);
                    break;
                } catch (const BoundedReadMiss& miss) {
                    if (!reconstruct(miss)) { stopped = true; break; }
                }
            }
            if (stopped) break;
            selector ^= samples[i];
        }
    }

    if (!stopped) {
        Bytes encoded_registers;
        for (const std::uint64_t value : state.registers) AppendLE64(encoded_registers, value);
        Bytes encoded_accumulator;
        AppendLE64(encoded_accumulator, state.accumulator);
        Bytes encoded_samples;
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
            Sha3_384(result_input), state.registers, context.schedule_digest,
            context.dataset_digest, memory_commitment,
        };
    }
    result.transcript_commitment = Sha3_384(transcript_input);
    result.layout = arena.Layout();
    result.stats = arena.Stats();
    return result;
}

PagedReconstructionResult ProbePagedReconstruction(const EpochContext& context, const Bytes& header, std::uint64_t nonce)
{
    Validate(context.seed, context.params);
    if (header.empty() || header.size() > MAX_HEADER_BYTES) throw std::invalid_argument("header size is outside the v1 research envelope");
    const Bytes params_bytes = EncodeParams(context.params), header_digest = Sha3_384(header);
    Bytes nonce_bytes; AppendLE64(nonce_bytes, nonce);
    MachineState state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
    const std::uint64_t total_iterations = context.params.passes * (context.params.scratchpad_bytes / 8);
    PagedReconstructionArena arena(context.params.scratchpad_bytes, context.params.scratchpad_bytes / 2);
    PagedReconstructionResult result{};
    Bytes transcript = DomainBytes(DOMAIN_PAGED_TRANSCRIPT);
    auto commitment = [&](const BoundedReadMiss& miss, const std::uint64_t* value) {
        Bytes encoded = DomainBytes(DOMAIN_PAGED_RECONSTRUCTION);
        Append(encoded, context.seed); Append(encoded, header_digest); Append(encoded, nonce_bytes); Append(encoded, params_bytes);
        AppendLE64(encoded, miss.consumer); encoded.push_back(miss.slot); AppendLE64(encoded, miss.word);
        for (const auto item : state.registers) AppendLE64(encoded, item);
        AppendLE64(encoded, state.accumulator); if (value) AppendLE64(encoded, *value);
        return Sha3_384(encoded);
    };
    auto reconstruct = [&](const BoundedReadMiss& miss) {
        ++result.reconstruction_attempts; result.max_reconstruction_depth = 1;
        arena.ResetReplay(); PagedReplayView replay{arena};
        MachineState replay_state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
        std::uint64_t completed{0};
        try {
            for (std::uint64_t i{0}; i < std::min(miss.consumer, total_iterations); ++i) { ExecuteMixIteration(context, replay, replay_state, i); ++completed; }
        } catch (const PagedReplayExhausted&) {
            result.attempted_replay_iterations += completed;
            result.cumulative_rank_probes += arena.RankProbes(); result.cumulative_directory_probes += arena.DirectoryProbes();
            result.cumulative_shifted_bytes += arena.ShiftedBytes();
            result.max_replay_peak_values = std::max(result.max_replay_peak_values, arena.PeakValues());
            result.max_replay_peak_pages = std::max(result.max_replay_peak_pages, arena.PeakPages());
            result.has_exhaustion = true;
            auto& out = result.exhaustion;
            out.consumer = miss.consumer; out.slot = miss.slot; out.word = miss.word; out.replay_completed_iterations = completed;
            out.replay_occupied_values = arena.Distinct(); out.replay_allocated_pages = arena.AllocatedPages();
            out.replay_rank_probes = arena.RankProbes(); out.replay_directory_probes = arena.DirectoryProbes();
            out.replay_shifted_bytes = arena.ShiftedBytes(); out.state_commitment = commitment(miss, nullptr);
            return false;
        }
        result.attempted_replay_iterations += completed; result.successful_replayed_iterations += completed;
        result.all_replay_states_matched = result.all_replay_states_matched && replay_state.registers == state.registers && replay_state.accumulator == state.accumulator;
        if (!result.all_replay_states_matched) throw std::logic_error("paged replay machine state does not match the live prefix");
        const std::uint64_t value = arena.ReplayReadExact(miss.word);
        result.cumulative_rank_probes += arena.RankProbes(); result.cumulative_directory_probes += arena.DirectoryProbes();
        result.cumulative_shifted_bytes += arena.ShiftedBytes();
        result.max_replay_peak_values = std::max(result.max_replay_peak_values, arena.PeakValues());
        result.max_replay_peak_pages = std::max(result.max_replay_peak_pages, arena.PeakPages());
        PagedBoundary boundary{};
        boundary.consumer = miss.consumer; boundary.slot = miss.slot; boundary.word = miss.word; boundary.value = value;
        boundary.replayed_iterations = completed; boundary.replay_peak_values = arena.PeakValues(); boundary.replay_peak_pages = arena.PeakPages();
        boundary.replay_rank_probes = arena.RankProbes(); boundary.replay_directory_probes = arena.DirectoryProbes();
        boundary.replay_shifted_bytes = arena.ShiftedBytes(); boundary.commitment = commitment(miss, &value);
        Append(transcript, boundary.commitment);
        if (!result.has_first) { result.has_first = true; result.first_reconstruction = boundary; }
        result.last_reconstruction = boundary; ++result.reconstructed_misses; arena.Retain(miss.word, value); return true;
    };
    bool stopped{false};
    for (std::uint64_t i{0}; i < total_iterations; ++i) {
        while (true) { arena.SetConsumer(i); try { ExecuteMixIteration(context, arena, state, i); break; } catch (const BoundedReadMiss& miss) { if (!reconstruct(miss)) { stopped = true; break; } } }
        if (stopped) break;
        ++result.completed_iterations;
    }
    std::array<std::uint64_t, FINAL_SAMPLE_WORDS> samples{};
    if (!stopped) {
        std::uint64_t selector = state.accumulator ^ state.registers[0] ^ state.registers[4];
        for (std::size_t i{0}; i < FINAL_SAMPLE_WORDS; ++i) {
            selector = std::rotl(selector ^ state.registers[i & 7], static_cast<int>((i + 1) & 63)) + 0x9E3779B97F4A7C15ULL + i;
            while (true) { arena.SetConsumer(total_iterations + i); try { samples[i] = arena.Read(selector); break; } catch (const BoundedReadMiss& miss) { if (!reconstruct(miss)) { stopped = true; break; } } }
            if (stopped) break;
            selector ^= samples[i];
        }
    }
    if (!stopped) {
        Bytes regs, acc, sample_bytes; for (const auto value : state.registers) AppendLE64(regs, value); AppendLE64(acc, state.accumulator); for (const auto value : samples) AppendLE64(sample_bytes, value);
        Bytes memory_input = DomainBytes(DOMAIN_COMMITMENT); Append(memory_input, params_bytes); Append(memory_input, regs); Append(memory_input, acc); Append(memory_input, sample_bytes);
        const Bytes memory_commitment = Sha3_384(memory_input);
        Bytes result_input = DomainBytes(DOMAIN_RESULT); Append(result_input, context.seed); Append(result_input, header_digest); Append(result_input, nonce_bytes); Append(result_input, params_bytes); Append(result_input, context.schedule_digest); Append(result_input, context.dataset_digest); Append(result_input, regs); Append(result_input, acc); Append(result_input, memory_commitment);
        result.status = "exact_complete"; result.execution_result = {Sha3_384(result_input), state.registers, context.schedule_digest, context.dataset_digest, memory_commitment};
    }
    result.transcript_commitment = Sha3_384(transcript); result.layout = arena.Layout(); result.stats = arena.Stats(); return result;
}

IndexedGapReconstructionResult ProbeIndexedGapReconstruction(const EpochContext& context, const Bytes& header, std::uint64_t nonce)
{
    Validate(context.seed, context.params);
    if (header.empty() || header.size() > MAX_HEADER_BYTES) throw std::invalid_argument("header size is outside the v1 research envelope");
    const Bytes params_bytes = EncodeParams(context.params), header_digest = Sha3_384(header);
    Bytes nonce_bytes; AppendLE64(nonce_bytes, nonce);
    MachineState state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
    const std::uint64_t total_iterations = context.params.passes * (context.params.scratchpad_bytes / 8);
    IndexedGapReconstructionArena arena(context.params.scratchpad_bytes, context.params.scratchpad_bytes / 2);
    IndexedGapReconstructionResult result{};
    Bytes transcript = DomainBytes(DOMAIN_INDEXED_GAP_TRANSCRIPT);
    auto commitment = [&](const BoundedReadMiss& miss, const std::uint64_t* value) {
        Bytes encoded = DomainBytes(DOMAIN_INDEXED_GAP_RECONSTRUCTION);
        Append(encoded, context.seed); Append(encoded, header_digest); Append(encoded, nonce_bytes); Append(encoded, params_bytes);
        AppendLE64(encoded, miss.consumer); encoded.push_back(miss.slot); AppendLE64(encoded, miss.word);
        for (const auto item : state.registers) AppendLE64(encoded, item);
        AppendLE64(encoded, state.accumulator); if (value) AppendLE64(encoded, *value);
        return Sha3_384(encoded);
    };
    auto reconstruct = [&](const BoundedReadMiss& miss) {
        ++result.reconstruction_attempts; result.max_reconstruction_depth = 1;
        arena.ResetReplay(); IndexedGapReplayView replay{arena};
        MachineState replay_state = InitializeMachineState(context, header_digest, nonce_bytes, params_bytes);
        std::uint64_t completed{0};
        try {
            for (std::uint64_t i{0}; i < std::min(miss.consumer, total_iterations); ++i) { ExecuteMixIteration(context, replay, replay_state, i); ++completed; }
        } catch (const IndexedGapReplayExhausted&) {
            result.attempted_replay_iterations += completed;
            result.cumulative_rank_probes += arena.RankProbes(); result.cumulative_index_probes += arena.IndexProbes();
            result.cumulative_directory_probes += arena.DirectoryProbes(); result.cumulative_rebalances += arena.Rebalances();
            result.cumulative_shifted_bytes += arena.ShiftedBytes();
            result.max_replay_peak_values = std::max(result.max_replay_peak_values, arena.PeakValues());
            result.max_replay_peak_pages = std::max(result.max_replay_peak_pages, arena.PeakPages());
            result.has_exhaustion = true;
            auto& out = result.exhaustion;
            out.consumer = miss.consumer; out.slot = miss.slot; out.word = miss.word; out.replay_completed_iterations = completed;
            out.replay_occupied_values = arena.Distinct(); out.replay_allocated_pages = arena.AllocatedPages();
            out.replay_rank_probes = arena.RankProbes(); out.replay_index_probes = arena.IndexProbes();
            out.replay_directory_probes = arena.DirectoryProbes(); out.replay_rebalances = arena.Rebalances();
            out.replay_shifted_bytes = arena.ShiftedBytes(); out.state_commitment = commitment(miss, nullptr);
            return false;
        }
        result.attempted_replay_iterations += completed; result.successful_replayed_iterations += completed;
        result.all_replay_states_matched = result.all_replay_states_matched && replay_state.registers == state.registers && replay_state.accumulator == state.accumulator;
        if (!result.all_replay_states_matched) throw std::logic_error("indexed-gap replay machine state does not match the live prefix");
        const std::uint64_t value = arena.ReplayReadExact(miss.word);
        result.cumulative_rank_probes += arena.RankProbes(); result.cumulative_index_probes += arena.IndexProbes();
        result.cumulative_directory_probes += arena.DirectoryProbes(); result.cumulative_rebalances += arena.Rebalances();
        result.cumulative_shifted_bytes += arena.ShiftedBytes();
        result.max_replay_peak_values = std::max(result.max_replay_peak_values, arena.PeakValues());
        result.max_replay_peak_pages = std::max(result.max_replay_peak_pages, arena.PeakPages());
        IndexedGapBoundary boundary{};
        boundary.consumer = miss.consumer; boundary.slot = miss.slot; boundary.word = miss.word; boundary.value = value;
        boundary.replayed_iterations = completed; boundary.replay_peak_values = arena.PeakValues(); boundary.replay_peak_pages = arena.PeakPages();
        boundary.replay_rank_probes = arena.RankProbes(); boundary.replay_index_probes = arena.IndexProbes();
        boundary.replay_directory_probes = arena.DirectoryProbes(); boundary.replay_rebalances = arena.Rebalances();
        boundary.replay_shifted_bytes = arena.ShiftedBytes(); boundary.commitment = commitment(miss, &value);
        Append(transcript, boundary.commitment);
        if (!result.has_first) { result.has_first = true; result.first_reconstruction = boundary; }
        result.last_reconstruction = boundary; ++result.reconstructed_misses; arena.Retain(miss.word, value); return true;
    };
    bool stopped{false};
    for (std::uint64_t i{0}; i < total_iterations; ++i) {
        while (true) { arena.SetConsumer(i); try { ExecuteMixIteration(context, arena, state, i); break; } catch (const BoundedReadMiss& miss) { if (!reconstruct(miss)) { stopped = true; break; } } }
        if (stopped) break;
        ++result.completed_iterations;
    }
    std::array<std::uint64_t, FINAL_SAMPLE_WORDS> samples{};
    if (!stopped) {
        std::uint64_t selector = state.accumulator ^ state.registers[0] ^ state.registers[4];
        for (std::size_t i{0}; i < FINAL_SAMPLE_WORDS; ++i) {
            selector = std::rotl(selector ^ state.registers[i & 7], static_cast<int>((i + 1) & 63)) + 0x9E3779B97F4A7C15ULL + i;
            while (true) { arena.SetConsumer(total_iterations + i); try { samples[i] = arena.Read(selector); break; } catch (const BoundedReadMiss& miss) { if (!reconstruct(miss)) { stopped = true; break; } } }
            if (stopped) break;
            selector ^= samples[i];
        }
    }
    if (!stopped) {
        Bytes regs, acc, sample_bytes; for (const auto value : state.registers) AppendLE64(regs, value); AppendLE64(acc, state.accumulator); for (const auto value : samples) AppendLE64(sample_bytes, value);
        Bytes memory_input = DomainBytes(DOMAIN_COMMITMENT); Append(memory_input, params_bytes); Append(memory_input, regs); Append(memory_input, acc); Append(memory_input, sample_bytes);
        const Bytes memory_commitment = Sha3_384(memory_input);
        Bytes result_input = DomainBytes(DOMAIN_RESULT); Append(result_input, context.seed); Append(result_input, header_digest); Append(result_input, nonce_bytes); Append(result_input, params_bytes); Append(result_input, context.schedule_digest); Append(result_input, context.dataset_digest); Append(result_input, regs); Append(result_input, acc); Append(result_input, memory_commitment);
        result.status = "exact_complete"; result.execution_result = {Sha3_384(result_input), state.registers, context.schedule_digest, context.dataset_digest, memory_commitment};
    }
    result.transcript_commitment = Sha3_384(transcript); result.layout = arena.Layout(); result.stats = arena.Stats(); return result;
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

void PrintRecursiveRegeneration(
    const Bytes& seed,
    const Bytes& header,
    std::uint64_t nonce,
    const Params& params)
{
    const RecursiveRegenerationResult r =
        ProbeFirstRecursiveRegeneration(PrepareEpoch(seed, params), header, nonce);
    const RecursiveLayout& l = r.layout;
    std::cout << "{\n"
              << "  \"format\": \"soveroot-pow-v1-recursive-regeneration-v0\",\n"
              << "  \"warning\": \"NON-CONSENSUS FIRST RECURSIVE REGENERATION; no completed proof, throughput, or gate result\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes
              << ", \"scratchpad_bytes\": " << params.scratchpad_bytes
              << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"status\": \"" << r.status << "\",\n"
              << "  \"layout\": {\"budget_bytes\": " << l.budget_bytes
              << ", \"fixed_state_reserve_bytes\": " << l.fixed_state_reserve_bytes
              << ", \"arena_bytes\": " << l.arena_bytes
              << ", \"write_bitmap_bytes\": " << l.write_bitmap_bytes
              << ", \"primary_cache_capacity\": " << l.primary_cache_capacity
              << ", \"primary_cache_bytes\": " << l.primary_cache_bytes
              << ", \"frame_bytes\": " << l.frame_bytes
              << ", \"frame_capacity\": " << l.frame_capacity
              << ", \"frame_reserve_bytes\": " << l.frame_reserve_bytes
              << ", \"memo_entry_bytes\": " << l.memo_entry_bytes
              << ", \"memo_capacity\": " << l.memo_capacity
              << ", \"memo_bytes\": " << l.memo_bytes
              << ", \"unused_arena_bytes\": " << l.unused_arena_bytes
              << ", \"admitted_bytes\": " << l.admitted_bytes << "},\n"
              << "  \"work_limit\": " << r.work_limit << ",\n"
              << "  \"completed_iterations\": " << r.completed_iterations << ",\n"
              << "  \"canonical_reads\": " << r.canonical_reads << ",\n"
              << "  \"cache_hits\": " << r.cache_hits << ",\n"
              << "  \"initial_zero_reads\": " << r.initial_zero_reads << ",\n"
              << "  \"materialized_misses\": " << r.materialized_misses << ",\n"
              << "  \"writes\": " << r.writes << ",\n"
              << "  \"evictions\": " << r.evictions << ",\n"
              << "  \"reconstruction_attempts\": " << r.reconstruction_attempts << ",\n"
              << "  \"reconstructed_misses\": " << r.reconstructed_misses << ",\n"
              << "  \"regeneration_calls\": " << r.regeneration_calls << ",\n"
              << "  \"regeneration_cache_hits\": " << r.regeneration_cache_hits << ",\n"
              << "  \"regeneration_completed_values\": " << r.regeneration_completed_values << ",\n"
              << "  \"regeneration_iterations\": " << r.regeneration_iterations << ",\n"
              << "  \"maximum_depth\": " << r.maximum_depth << ",\n"
              << "  \"memo_peak_entries\": " << r.memo_peak_entries << ",\n"
              << "  \"memo_evictions\": " << r.memo_evictions << ",\n"
              << "  \"memo_probes\": " << r.memo_probes << ",\n"
              << "  \"memo_shifted_bytes\": " << r.memo_shifted_bytes << ",\n"
              << "  \"first_reconstruction\": ";
    if (r.has_first) {
        const RecursiveBoundary& b = r.first_reconstruction;
        std::cout << "{\"consumer\": " << b.consumer
                  << ", \"slot\": " << static_cast<unsigned>(b.slot)
                  << ", \"word\": " << b.word
                  << ", \"value\": " << b.value
                  << ", \"regeneration_calls\": " << b.regeneration_calls
                  << ", \"regeneration_cache_hits\": " << b.regeneration_cache_hits
                  << ", \"regeneration_completed_values\": " << b.regeneration_completed_values
                  << ", \"regeneration_iterations\": " << b.regeneration_iterations
                  << ", \"maximum_depth\": " << b.maximum_depth
                  << ", \"memo_peak_entries\": " << b.memo_peak_entries
                  << ", \"memo_evictions\": " << b.memo_evictions
                  << ", \"memo_probes\": " << b.memo_probes
                  << ", \"memo_shifted_bytes\": " << b.memo_shifted_bytes
                  << ", \"commitment\": \"" << Hex(b.commitment) << "\"}";
    } else {
        std::cout << "null";
    }
    std::cout << ",\n  \"refusal_consumer\": ";
    if (r.has_refusal) std::cout << r.refusal_consumer; else std::cout << "null";
    std::cout << ",\n  \"refusal_slot\": ";
    if (r.has_refusal) std::cout << static_cast<unsigned>(r.refusal_slot); else std::cout << "null";
    std::cout << ",\n  \"refusal_word\": ";
    if (r.has_refusal) std::cout << r.refusal_word; else std::cout << "null";
    std::cout << ",\n  \"refusal_state_commitment\": ";
    if (r.has_refusal) std::cout << "\"" << Hex(r.refusal_state_commitment) << "\"";
    else std::cout << "null";
    std::cout << ",\n  \"exhaustion\": ";
    if (r.has_exhaustion) {
        const RecursiveExhaustion& e = r.exhaustion;
        std::cout << "{\"reason\": \"" << e.reason
                  << "\", \"stop_iteration\": " << e.stop_iteration
                  << ", \"word\": " << e.word
                  << ", \"attempted_depth\": " << e.attempted_depth
                  << ", \"regeneration_iterations\": " << e.regeneration_iterations << "}";
    } else {
        std::cout << "null";
    }
    std::cout << ",\n  \"transcript_commitment\": \""
              << Hex(r.transcript_commitment) << "\"\n}\n";
}

void PrintRepeatedRecursiveRegeneration(
    const Bytes& seed,
    const Bytes& header,
    std::uint64_t nonce,
    const Params& params,
    bool checkpoints = false,
    bool target_checkpoints = false,
    bool dependency_bundles = false,
    bool operation_bounded = false,
    std::uint64_t operation_limit = REGENERATION_OPERATION_LIMIT,
    bool physically_accounted = false,
    bool iterative_work_stack = false)
{
    const bool has_checkpoints = checkpoints || target_checkpoints || dependency_bundles;
    const RepeatedRecursiveRegenerationResult r =
        dependency_bundles
        ? ProbeRepeatedRecursiveRegeneration(
              PrepareEpoch(seed, params), header, nonce, RECURSIVE_WORK_LIMIT,
              1, 128, DEPENDENCY_BUNDLE_CAPACITY, CHECKPOINT_STRIDE, false, true,
              operation_bounded ? operation_limit : 0,
              iterative_work_stack ? ITERATIVE_EXTERNAL_RESERVE_BYTES
                  : (physically_accounted ? PHYSICAL_EXTERNAL_RESERVE_BYTES : 0),
              physically_accounted || iterative_work_stack,
              iterative_work_stack)
        : target_checkpoints
        ? ProbeRepeatedRecursiveRegeneration(
              PrepareEpoch(seed, params), header, nonce, RECURSIVE_WORK_LIMIT,
              1, 128, CHECKPOINT_CAPACITY, CHECKPOINT_STRIDE, true)
        : checkpoints
        ? ProbeRepeatedRecursiveRegeneration(
              PrepareEpoch(seed, params), header, nonce, RECURSIVE_WORK_LIMIT,
              1, 32, CHECKPOINT_CAPACITY, CHECKPOINT_STRIDE)
        : ProbeRepeatedRecursiveRegeneration(PrepareEpoch(seed, params), header, nonce);
    const RecursiveLayout& l = r.layout;
    auto print_boundary = [has_checkpoints](const RecursiveBoundary& b) {
        std::cout << "{\"consumer\": " << b.consumer
                  << ", \"slot\": " << static_cast<unsigned>(b.slot)
                  << ", \"word\": " << b.word
                  << ", \"value\": " << b.value
                  << ", \"regeneration_calls\": " << b.regeneration_calls
                  << ", \"regeneration_cache_hits\": " << b.regeneration_cache_hits
                  << ", \"regeneration_completed_values\": " << b.regeneration_completed_values
                  << ", \"regeneration_iterations\": " << b.regeneration_iterations
                  << ", \"maximum_depth\": " << b.maximum_depth
                  << ", \"memo_peak_entries\": " << b.memo_peak_entries
                  << ", \"memo_evictions\": " << b.memo_evictions
                  << ", \"memo_probes\": " << b.memo_probes
                  << ", \"memo_shifted_bytes\": " << b.memo_shifted_bytes;
        if (has_checkpoints) {
            std::cout << ", \"checkpoint_lookups\": " << b.checkpoint_lookups
                      << ", \"checkpoint_hits\": " << b.checkpoint_hits
                      << ", \"checkpoint_captures\": " << b.checkpoint_captures
                      << ", \"checkpoint_replacements\": " << b.checkpoint_replacements
                      << ", \"checkpoint_probes\": " << b.checkpoint_probes;
        }
        std::cout << ", \"commitment\": \"" << Hex(b.commitment) << "\"}";
    };
    std::cout << "{\n"
              << "  \"format\": \""
              << (iterative_work_stack
                  ? "soveroot-pow-v1-iterative-work-stack-regeneration-v0"
                  : physically_accounted
                  ? "soveroot-pow-v1-physically-accounted-dependency-bundle-regeneration-v0"
                  : operation_bounded
                  ? "soveroot-pow-v1-operation-bounded-dependency-bundle-regeneration-v0"
                  : dependency_bundles
                  ? "soveroot-pow-v1-dependency-bundle-regeneration-v0"
                  : target_checkpoints
                  ? "soveroot-pow-v1-target-checkpoint-regeneration-v0"
                  : (checkpoints
                      ? "soveroot-pow-v1-checkpoint-recursive-regeneration-v0"
                      : "soveroot-pow-v1-repeated-recursive-regeneration-v0"))
              << "\",\n"
              << "  \"warning\": \""
              << (iterative_work_stack
                  ? "NON-CONSENSUS ITERATIVE WORK-STACK DEPENDENCY-BUNDLE PILOT; no completed proof or gate result"
                  : physically_accounted
                  ? "NON-CONSENSUS PHYSICALLY ACCOUNTED DEPENDENCY-BUNDLE PILOT; no completed proof or gate result"
                  : operation_bounded
                  ? "NON-CONSENSUS OPERATION-BOUNDED DEPENDENCY-BUNDLE PILOT; no completed proof or gate result"
                  : dependency_bundles
                  ? "NON-CONSENSUS DEPENDENCY-BUNDLE REGENERATION PILOT; no completed proof or gate result"
                  : target_checkpoints
                  ? "NON-CONSENSUS TARGET-AWARE CHECKPOINT PILOT; no completed proof or gate result"
                  : (checkpoints
                      ? "NON-CONSENSUS CHECKPOINT REGENERATION REJECTION PILOT; no completed proof or gate result"
                      : "NON-CONSENSUS REPEATED RECURSIVE REGENERATION; no completed proof, throughput, or gate result"))
              << "\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes
              << ", \"scratchpad_bytes\": " << params.scratchpad_bytes
              << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"status\": \"" << r.status << "\",\n"
              << "  \"layout\": {\"budget_bytes\": " << l.budget_bytes
              << ", \"fixed_state_reserve_bytes\": " << l.fixed_state_reserve_bytes
              << ", \"arena_bytes\": " << l.arena_bytes
              << ", \"write_bitmap_bytes\": " << l.write_bitmap_bytes
              << ", \"primary_cache_capacity\": " << l.primary_cache_capacity
              << ", \"primary_cache_bytes\": " << l.primary_cache_bytes
              << ", \"frame_bytes\": " << l.frame_bytes
              << ", \"frame_capacity\": " << l.frame_capacity
              << ", \"frame_reserve_bytes\": " << l.frame_reserve_bytes;
    if (has_checkpoints) {
        std::cout << ", \"checkpoint_entry_bytes\": " << l.checkpoint_entry_bytes
                  << ", \"checkpoint_capacity\": " << l.checkpoint_capacity
                  << ", \"checkpoint_bytes\": " << l.checkpoint_bytes
                  << ", \"checkpoint_stride\": " << l.checkpoint_stride;
    }
    std::cout << ", \"memo_entry_bytes\": " << l.memo_entry_bytes
              << ", \"memo_capacity\": " << l.memo_capacity
              << ", \"memo_bytes\": " << l.memo_bytes
              << ", \"unused_arena_bytes\": " << l.unused_arena_bytes
              << ", \"admitted_bytes\": " << l.admitted_bytes << "},\n"
              << "  \"primary_numerator\": " << r.primary_numerator << ",\n"
              << "  \"primary_denominator\": " << r.primary_denominator << ",\n"
              << "  \"work_limit\": " << r.work_limit << ",\n"
              << (operation_bounded
                  ? "  \"operation_limit\": " + std::to_string(r.operation_limit) + ",\n"
                  : "")
              << "  \"completed_iterations\": " << r.completed_iterations << ",\n"
              << "  \"canonical_reads\": " << r.canonical_reads << ",\n"
              << "  \"cache_hits\": " << r.cache_hits << ",\n"
              << "  \"initial_zero_reads\": " << r.initial_zero_reads << ",\n"
              << "  \"materialized_misses\": " << r.materialized_misses << ",\n"
              << "  \"writes\": " << r.writes << ",\n"
              << "  \"evictions\": " << r.evictions << ",\n"
              << "  \"reconstruction_attempts\": " << r.reconstruction_attempts << ",\n"
              << "  \"reconstructed_misses\": " << r.reconstructed_misses << ",\n"
              << "  \"regeneration_calls\": " << r.regeneration_calls << ",\n"
              << "  \"regeneration_cache_hits\": " << r.regeneration_cache_hits << ",\n"
              << "  \"regeneration_completed_values\": " << r.regeneration_completed_values << ",\n"
              << "  \"regeneration_iterations\": " << r.regeneration_iterations << ",\n"
              << "  \"maximum_depth\": " << r.maximum_depth << ",\n"
              << "  \"memo_peak_entries\": " << r.memo_peak_entries << ",\n"
              << "  \"memo_evictions\": " << r.memo_evictions << ",\n"
              << "  \"memo_probes\": " << r.memo_probes << ",\n"
              << "  \"memo_shifted_bytes\": " << r.memo_shifted_bytes << ",\n";
    if (has_checkpoints) {
        std::cout << "  \"checkpoint_lookups\": " << r.checkpoint_lookups << ",\n"
                  << "  \"checkpoint_hits\": " << r.checkpoint_hits << ",\n"
                  << "  \"checkpoint_captures\": " << r.checkpoint_captures << ",\n"
                  << "  \"checkpoint_replacements\": " << r.checkpoint_replacements << ",\n"
                  << "  \"checkpoint_probes\": " << r.checkpoint_probes << ",\n";
    }
    if (operation_bounded) {
        std::cout << "  \"operation_counts\": {\"recursive_calls\": "
                  << r.regeneration_calls
                  << ", \"replay_iterations\": " << r.regeneration_iterations
                  << ", \"memo_probes\": " << r.memo_probes
                  << ", \"checkpoint_probes\": " << r.checkpoint_probes
                  << ", \"total\": " << r.total_operations << "},\n";
    }
    if (physically_accounted) {
        std::cout
            << "  \"physical_memory_accounting\": {\"total_budget_bytes\": "
            << r.physical_total_budget_bytes
            << ", \"fixed_state_reserve_bytes\": " << BOUNDED_FIXED_STATE_RESERVE_BYTES
            << ", \"native_stack_frame_allowance_bytes\": "
            << NATIVE_STACK_FRAME_ALLOWANCE_BYTES
            << ", \"native_stack_depth_capacity\": " << NATIVE_STACK_DEPTH_CAPACITY
            << ", \"native_stack_reserve_bytes\": " << NATIVE_STACK_RESERVE_BYTES
            << ", \"allocator_allowance_bytes\": " << ALLOCATOR_ALLOWANCE_BYTES
            << ", \"arena_allocation_bytes\": " << r.physical_arena_allocation_bytes
            << ", \"logical_frame_reserve_bytes\": " << l.frame_reserve_bytes
            << ", \"rolling_transcript_state_bytes\": 48"
            << ", \"transcript_growth_bytes\": 0"
            << ", \"accounted_bytes\": "
            << BOUNDED_FIXED_STATE_RESERVE_BYTES + r.physical_arena_allocation_bytes
                + PHYSICAL_EXTERNAL_RESERVE_BYTES
            << "},\n";
    }
    if (iterative_work_stack) {
        std::cout
            << "  \"iterative_memory_accounting\": {\"total_budget_bytes\": "
            << r.physical_total_budget_bytes
            << ", \"fixed_state_reserve_bytes\": " << BOUNDED_FIXED_STATE_RESERVE_BYTES
            << ", \"allocator_allowance_bytes\": " << ALLOCATOR_ALLOWANCE_BYTES
            << ", \"arena_allocation_bytes\": " << r.physical_arena_allocation_bytes
            << ", \"explicit_frame_bytes\": " << l.frame_bytes
            << ", \"explicit_frame_capacity\": " << l.frame_capacity
            << ", \"explicit_work_stack_bytes_inside_arena\": "
            << l.frame_reserve_bytes
            << ", \"native_recursion_bytes\": 0"
            << ", \"rolling_transcript_state_bytes\": 48"
            << ", \"transcript_growth_bytes\": 0"
            << ", \"accounted_bytes\": "
            << BOUNDED_FIXED_STATE_RESERVE_BYTES + r.physical_arena_allocation_bytes
                + ITERATIVE_EXTERNAL_RESERVE_BYTES
            << "},\n";
    }
    std::cout << "  \"first_reconstruction\": ";
    if (r.has_first) print_boundary(r.first_reconstruction); else std::cout << "null";
    std::cout << ",\n  \"last_reconstruction\": ";
    if (r.has_last) print_boundary(r.last_reconstruction); else std::cout << "null";
    std::cout << ",\n  \"exhaustion\": ";
    if (r.has_exhaustion) {
        const RepeatedRecursiveExhaustion& e = r.exhaustion;
        std::cout << "{\"reason\": \"" << e.reason
                  << "\", \"consumer\": " << e.consumer
                  << ", \"slot\": " << static_cast<unsigned>(e.slot)
                  << ", \"word\": " << e.word
                  << ", \"stop_iteration\": " << e.stop_iteration
                  << ", \"attempted_depth\": " << e.attempted_depth
                  << ", \"regeneration_iterations\": " << e.regeneration_iterations
                  << ", \"state_commitment\": \"" << Hex(e.state_commitment) << "\"}";
    } else {
        std::cout << "null";
    }
    std::cout << ",\n  \"transcript_commitment\": \""
              << Hex(r.transcript_commitment) << "\",\n"
              << "  \"execution_result\": ";
    if (r.has_execution) {
        std::cout << "{\"digest\": \"" << Hex(r.execution_result.digest)
                  << "\", \"registers\": [";
        for (std::size_t i{0}; i < r.execution_result.registers.size(); ++i) {
            if (i != 0) std::cout << ", ";
            std::ostringstream encoded;
            encoded << std::hex << std::setfill('0') << std::setw(16)
                    << r.execution_result.registers[i];
            std::cout << "\"" << encoded.str() << "\"";
        }
        std::cout << "], \"schedule_digest\": \"" << Hex(r.execution_result.schedule_digest)
                  << "\", \"dataset_digest\": \"" << Hex(r.execution_result.dataset_digest)
                  << "\", \"memory_commitment\": \"" << Hex(r.execution_result.memory_commitment)
                  << "\"}";
    } else {
        std::cout << "null";
    }
    std::cout << "\n}\n";
}

void PrintPackedReconstruction(
    const Bytes& seed,
    const Bytes& header,
    std::uint64_t nonce,
    const Params& params)
{
    const PackedReconstructionResult result =
        ProbePackedReconstruction(PrepareEpoch(seed, params), header, nonce);
    const PackedLayout& layout = result.layout;
    const BoundedReconstructionStats& stats = result.stats;
    auto print_boundary = [](const PackedBoundary& boundary) {
        std::cout << "{\"consumer\": " << boundary.consumer
                  << ", \"slot\": " << static_cast<unsigned>(boundary.slot)
                  << ", \"word\": " << boundary.word
                  << ", \"value\": " << boundary.value
                  << ", \"replayed_iterations\": " << boundary.replayed_iterations
                  << ", \"replay_peak_entries\": " << boundary.replay_peak_entries
                  << ", \"replay_rank_probes\": " << boundary.replay_rank_probes
                  << ", \"replay_shifted_bytes\": " << boundary.replay_shifted_bytes
                  << ", \"commitment\": \"" << Hex(boundary.commitment) << "\"}";
    };
    std::cout << "{\n"
              << "  \"format\": \"soveroot-pow-v1-packed-checkpoint-reconstruction-v0\",\n"
              << "  \"warning\": \"NON-CONSENSUS PACKED CHECKPOINT; no completed proof, throughput, or gate result\",\n"
              << "  \"status\": \"" << result.status << "\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes
              << ", \"scratchpad_bytes\": " << params.scratchpad_bytes
              << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"layout\": {\"budget_bytes\": " << layout.budget_bytes
              << ", \"fixed_state_reserve_bytes\": " << layout.fixed_state_reserve_bytes
              << ", \"arena_bytes\": " << layout.arena_bytes
              << ", \"canonical_write_bitmap_bytes\": " << layout.canonical_write_bitmap_bytes
              << ", \"primary_cache_capacity\": " << layout.primary_cache_capacity
              << ", \"primary_cache_bytes\": " << layout.primary_cache_bytes
              << ", \"replay_bitmap_bytes\": " << layout.replay_bitmap_bytes
              << ", \"rank_directory_bytes\": " << layout.rank_directory_bytes
              << ", \"replay_value_capacity\": " << layout.replay_value_capacity
              << ", \"replay_value_bytes\": " << layout.replay_value_bytes
              << ", \"unused_arena_bytes\": " << layout.unused_arena_bytes
              << ", \"admitted_bytes\": " << layout.admitted_bytes << "},\n"
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
              << "  \"cumulative_rank_probes\": " << result.cumulative_rank_probes << ",\n"
              << "  \"cumulative_shifted_bytes\": " << result.cumulative_shifted_bytes << ",\n"
              << "  \"max_replay_peak_entries\": " << result.max_replay_peak_entries << ",\n"
              << "  \"max_reconstruction_depth\": " << result.max_reconstruction_depth << ",\n"
              << "  \"all_replay_states_matched\": "
              << (result.all_replay_states_matched ? "true" : "false") << ",\n"
              << "  \"transcript_commitment\": \"" << Hex(result.transcript_commitment) << "\",\n"
              << "  \"first_reconstruction\": ";
    if (result.has_first) print_boundary(result.first_reconstruction); else std::cout << "null";
    std::cout << ",\n  \"last_reconstruction\": ";
    if (result.has_first) print_boundary(result.last_reconstruction); else std::cout << "null";
    std::cout << ",\n  \"exhaustion\": ";
    if (result.has_exhaustion) {
        const PackedExhaustionBoundary& boundary = result.exhaustion;
        std::cout << "{\"consumer\": " << boundary.consumer
                  << ", \"slot\": " << static_cast<unsigned>(boundary.slot)
                  << ", \"word\": " << boundary.word
                  << ", \"replay_completed_iterations\": " << boundary.replay_completed_iterations
                  << ", \"replay_peak_entries\": " << boundary.replay_peak_entries
                  << ", \"replay_rank_probes\": " << boundary.replay_rank_probes
                  << ", \"replay_shifted_bytes\": " << boundary.replay_shifted_bytes
                  << ", \"state_commitment\": \"" << Hex(boundary.state_commitment) << "\"}";
    } else {
        std::cout << "null";
    }
    if (result.status == "exact_complete") {
        std::cout << ",\n  \"digest\": \"" << Hex(result.execution_result.digest) << "\",\n"
                  << "  \"memory_commitment\": \"" << Hex(result.execution_result.memory_commitment) << "\"\n";
    } else {
        std::cout << ",\n  \"digest\": null,\n  \"memory_commitment\": null\n";
    }
    std::cout << "}\n";
}

void PrintPagedReconstruction(const Bytes& seed, const Bytes& header, std::uint64_t nonce, const Params& params)
{
    const PagedReconstructionResult r = ProbePagedReconstruction(PrepareEpoch(seed, params), header, nonce);
    const auto& l = r.layout; const auto& s = r.stats;
    auto boundary = [](const PagedBoundary& b) { std::cout << "{\"consumer\": " << b.consumer << ", \"slot\": " << static_cast<unsigned>(b.slot) << ", \"word\": " << b.word << ", \"value\": " << b.value << ", \"replayed_iterations\": " << b.replayed_iterations << ", \"replay_peak_values\": " << b.replay_peak_values << ", \"replay_peak_pages\": " << b.replay_peak_pages << ", \"replay_rank_probes\": " << b.replay_rank_probes << ", \"replay_directory_probes\": " << b.replay_directory_probes << ", \"replay_shifted_bytes\": " << b.replay_shifted_bytes << ", \"commitment\": \"" << Hex(b.commitment) << "\"}"; };
    std::cout << "{\n  \"format\": \"soveroot-pow-v1-paged-gap-reconstruction-v0\",\n"
              << "  \"warning\": \"NON-CONSENSUS PAGED GAP; no completed proof, throughput, or gate result\",\n"
              << "  \"status\": \"" << r.status << "\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes << ", \"scratchpad_bytes\": " << params.scratchpad_bytes << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"layout\": {\"budget_bytes\": " << l.budget_bytes << ", \"fixed_state_reserve_bytes\": " << l.fixed_state_reserve_bytes << ", \"arena_bytes\": " << l.arena_bytes << ", \"canonical_write_bitmap_bytes\": " << l.canonical_write_bitmap_bytes << ", \"primary_cache_capacity\": " << l.primary_cache_capacity << ", \"primary_cache_bytes\": " << l.primary_cache_bytes << ", \"replay_bitmap_bytes\": " << l.replay_bitmap_bytes << ", \"rank_directory_bytes\": " << l.rank_directory_bytes << ", \"page_slots\": " << l.page_slots << ", \"max_pages\": " << l.max_pages << ", \"page_directory_bytes\": " << l.page_directory_bytes << ", \"page_count_bytes\": " << l.page_count_bytes << ", \"replay_value_slots\": " << l.replay_value_slots << ", \"replay_value_bytes\": " << l.replay_value_bytes << ", \"unused_arena_bytes\": " << l.unused_arena_bytes << ", \"admitted_bytes\": " << l.admitted_bytes << "},\n"
              << "  \"completed_iterations\": " << r.completed_iterations << ",\n  \"canonical_reads\": " << s.canonical_reads << ",\n  \"cache_hits\": " << s.cache_hits << ",\n  \"initial_zero_reads\": " << s.initial_zero_reads << ",\n  \"materialized_misses\": " << s.materialized_misses << ",\n  \"writes\": " << s.writes << ",\n  \"evictions\": " << s.evictions << ",\n"
              << "  \"reconstruction_attempts\": " << r.reconstruction_attempts << ",\n  \"reconstructed_misses\": " << r.reconstructed_misses << ",\n  \"successful_replayed_iterations\": " << r.successful_replayed_iterations << ",\n  \"attempted_replay_iterations\": " << r.attempted_replay_iterations << ",\n  \"cumulative_rank_probes\": " << r.cumulative_rank_probes << ",\n  \"cumulative_directory_probes\": " << r.cumulative_directory_probes << ",\n  \"cumulative_shifted_bytes\": " << r.cumulative_shifted_bytes << ",\n  \"max_replay_peak_values\": " << r.max_replay_peak_values << ",\n  \"max_replay_peak_pages\": " << r.max_replay_peak_pages << ",\n  \"max_reconstruction_depth\": " << r.max_reconstruction_depth << ",\n  \"all_replay_states_matched\": " << (r.all_replay_states_matched ? "true" : "false") << ",\n  \"transcript_commitment\": \"" << Hex(r.transcript_commitment) << "\",\n  \"first_reconstruction\": ";
    if (r.has_first) boundary(r.first_reconstruction); else std::cout << "null";
    std::cout << ",\n  \"last_reconstruction\": "; if (r.has_first) boundary(r.last_reconstruction); else std::cout << "null";
    std::cout << ",\n  \"exhaustion\": ";
    if (r.has_exhaustion) { const auto& e = r.exhaustion; std::cout << "{\"consumer\": " << e.consumer << ", \"slot\": " << static_cast<unsigned>(e.slot) << ", \"word\": " << e.word << ", \"replay_completed_iterations\": " << e.replay_completed_iterations << ", \"replay_occupied_values\": " << e.replay_occupied_values << ", \"replay_allocated_pages\": " << e.replay_allocated_pages << ", \"replay_rank_probes\": " << e.replay_rank_probes << ", \"replay_directory_probes\": " << e.replay_directory_probes << ", \"replay_shifted_bytes\": " << e.replay_shifted_bytes << ", \"state_commitment\": \"" << Hex(e.state_commitment) << "\"}"; } else std::cout << "null";
    if (r.status == "exact_complete") std::cout << ",\n  \"digest\": \"" << Hex(r.execution_result.digest) << "\",\n  \"memory_commitment\": \"" << Hex(r.execution_result.memory_commitment) << "\"\n";
    else std::cout << ",\n  \"digest\": null,\n  \"memory_commitment\": null\n";
    std::cout << "}\n";
}

void PrintIndexedGapReconstruction(const Bytes& seed, const Bytes& header, std::uint64_t nonce, const Params& params)
{
    const IndexedGapReconstructionResult r = ProbeIndexedGapReconstruction(PrepareEpoch(seed, params), header, nonce);
    const auto& l = r.layout; const auto& s = r.stats;
    auto boundary = [](const IndexedGapBoundary& b) {
        std::cout << "{\"consumer\": " << b.consumer << ", \"slot\": " << static_cast<unsigned>(b.slot)
                  << ", \"word\": " << b.word << ", \"value\": " << b.value
                  << ", \"replayed_iterations\": " << b.replayed_iterations
                  << ", \"replay_peak_values\": " << b.replay_peak_values
                  << ", \"replay_peak_pages\": " << b.replay_peak_pages
                  << ", \"replay_rank_probes\": " << b.replay_rank_probes
                  << ", \"replay_index_probes\": " << b.replay_index_probes
                  << ", \"replay_directory_probes\": " << b.replay_directory_probes
                  << ", \"replay_rebalances\": " << b.replay_rebalances
                  << ", \"replay_shifted_bytes\": " << b.replay_shifted_bytes
                  << ", \"commitment\": \"" << Hex(b.commitment) << "\"}";
    };
    std::cout << "{\n  \"format\": \"soveroot-pow-v1-indexed-gap-reconstruction-v0\",\n"
              << "  \"warning\": \"NON-CONSENSUS INDEXED GAP; no completed proof, throughput, or gate result\",\n"
              << "  \"status\": \"" << r.status << "\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes << ", \"scratchpad_bytes\": " << params.scratchpad_bytes << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"layout\": {\"budget_bytes\": " << l.budget_bytes << ", \"fixed_state_reserve_bytes\": " << l.fixed_state_reserve_bytes << ", \"arena_bytes\": " << l.arena_bytes << ", \"canonical_write_bitmap_bytes\": " << l.canonical_write_bitmap_bytes << ", \"primary_cache_capacity\": " << l.primary_cache_capacity << ", \"primary_cache_bytes\": " << l.primary_cache_bytes << ", \"replay_bitmap_bytes\": " << l.replay_bitmap_bytes << ", \"rank_directory_bytes\": " << l.rank_directory_bytes << ", \"page_slots\": " << l.page_slots << ", \"max_pages\": " << l.max_pages << ", \"page_directory_bytes\": " << l.page_directory_bytes << ", \"page_count_bytes\": " << l.page_count_bytes << ", \"page_index_bytes\": " << l.page_index_bytes << ", \"replay_value_slots\": " << l.replay_value_slots << ", \"replay_value_bytes\": " << l.replay_value_bytes << ", \"unused_arena_bytes\": " << l.unused_arena_bytes << ", \"admitted_bytes\": " << l.admitted_bytes << "},\n"
              << "  \"completed_iterations\": " << r.completed_iterations << ",\n  \"canonical_reads\": " << s.canonical_reads << ",\n  \"cache_hits\": " << s.cache_hits << ",\n  \"initial_zero_reads\": " << s.initial_zero_reads << ",\n  \"materialized_misses\": " << s.materialized_misses << ",\n  \"writes\": " << s.writes << ",\n  \"evictions\": " << s.evictions << ",\n"
              << "  \"reconstruction_attempts\": " << r.reconstruction_attempts << ",\n  \"reconstructed_misses\": " << r.reconstructed_misses << ",\n  \"successful_replayed_iterations\": " << r.successful_replayed_iterations << ",\n  \"attempted_replay_iterations\": " << r.attempted_replay_iterations << ",\n  \"cumulative_rank_probes\": " << r.cumulative_rank_probes << ",\n  \"cumulative_index_probes\": " << r.cumulative_index_probes << ",\n  \"cumulative_directory_probes\": " << r.cumulative_directory_probes << ",\n  \"cumulative_rebalances\": " << r.cumulative_rebalances << ",\n  \"cumulative_shifted_bytes\": " << r.cumulative_shifted_bytes << ",\n  \"max_replay_peak_values\": " << r.max_replay_peak_values << ",\n  \"max_replay_peak_pages\": " << r.max_replay_peak_pages << ",\n  \"max_reconstruction_depth\": " << r.max_reconstruction_depth << ",\n  \"all_replay_states_matched\": " << (r.all_replay_states_matched ? "true" : "false") << ",\n  \"transcript_commitment\": \"" << Hex(r.transcript_commitment) << "\",\n  \"first_reconstruction\": ";
    if (r.has_first) boundary(r.first_reconstruction); else std::cout << "null";
    std::cout << ",\n  \"last_reconstruction\": "; if (r.has_first) boundary(r.last_reconstruction); else std::cout << "null";
    std::cout << ",\n  \"exhaustion\": ";
    if (r.has_exhaustion) {
        const auto& e = r.exhaustion;
        std::cout << "{\"consumer\": " << e.consumer << ", \"slot\": " << static_cast<unsigned>(e.slot)
                  << ", \"word\": " << e.word << ", \"replay_completed_iterations\": " << e.replay_completed_iterations
                  << ", \"replay_occupied_values\": " << e.replay_occupied_values
                  << ", \"replay_allocated_pages\": " << e.replay_allocated_pages
                  << ", \"replay_rank_probes\": " << e.replay_rank_probes
                  << ", \"replay_index_probes\": " << e.replay_index_probes
                  << ", \"replay_directory_probes\": " << e.replay_directory_probes
                  << ", \"replay_rebalances\": " << e.replay_rebalances
                  << ", \"replay_shifted_bytes\": " << e.replay_shifted_bytes
                  << ", \"state_commitment\": \"" << Hex(e.state_commitment) << "\"}";
    } else std::cout << "null";
    if (r.status == "exact_complete") std::cout << ",\n  \"digest\": \"" << Hex(r.execution_result.digest) << "\",\n  \"memory_commitment\": \"" << Hex(r.execution_result.memory_commitment) << "\"\n";
    else std::cout << ",\n  \"digest\": null,\n  \"memory_commitment\": null\n";
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

void PrintTimeCheckpointScreen(
    const Bytes& seed,
    const Bytes& header,
    std::uint64_t nonce,
    const Params& params)
{
    const EpochContext context = PrepareEpoch(seed, params);
    TraceRecorder recorder(params.scratchpad_bytes / 8);
    const ExecutionResult execution = EvaluateWithScratchpad<FullScratchpad>(
        context, header, nonce, nullptr, nullptr, nullptr, &recorder);
    const TimeCheckpointScreenResult r = recorder.ScreenTimeCheckpoints(params.scratchpad_bytes / 2);
    const auto& l = r.layout;
    std::cout << "{\n"
              << "  \"format\": \"soveroot-pow-v1-time-checkpoint-screen-v0\",\n"
              << "  \"warning\": \"NON-CONSENSUS FULL-MEMORY OFFLINE CHECKPOINT SCREEN; not an executable attack or gate result\",\n"
              << "  \"params\": {\"dataset_bytes\": " << params.dataset_bytes
              << ", \"scratchpad_bytes\": " << params.scratchpad_bytes
              << ", \"passes\": " << params.passes << "},\n"
              << "  \"nonce\": " << nonce << ",\n"
              << "  \"layout\": {\"budget_bytes\": " << l.budget_bytes
              << ", \"fixed_state_reserve_bytes\": " << l.fixed_state_reserve_bytes
              << ", \"bitmap_bytes_per_nonempty_store\": " << l.bitmap_bytes_per_nonempty_store
              << ", \"rank_directory_bytes_per_nonempty_store\": " << l.rank_directory_bytes_per_nonempty_store
              << ", \"value_bytes\": " << l.value_bytes
              << ", \"checkpoint_divisions\": " << l.checkpoint_divisions << "},\n"
              << "  \"total_iterations\": " << r.total_iterations
              << ",\n  \"trace_reads\": " << r.trace_reads
              << ",\n  \"trace_writes\": " << r.trace_writes
              << ",\n  \"global_maximum_live_values\": " << r.global_maximum_live_values
              << ",\n  \"cuts\": [\n";
    for (std::size_t index{0}; index < r.cuts.size(); ++index) {
        const auto& c = r.cuts[index];
        std::cout << "    {\"checkpoint_iteration\": " << c.checkpoint_iteration
                  << ", \"snapshot_materialized_values\": " << c.snapshot_materialized_values
                  << ", \"suffix_distinct_write_values\": " << c.suffix_distinct_write_values
                  << ", \"duplicated_snapshot_delta_values\": " << c.duplicated_snapshot_delta_values
                  << ", \"checkpoint_frontier_values\": " << c.checkpoint_frontier_values
                  << ", \"capture_peak_live_values\": " << c.capture_peak_live_values
                  << ", \"resume_peak_live_values\": " << c.resume_peak_live_values
                  << ", \"staged_peak_live_values\": " << c.staged_peak_live_values
                  << ", \"full_checkpoint_bytes\": " << c.full_checkpoint_bytes
                  << ", \"naive_snapshot_delta_bytes\": " << c.naive_snapshot_delta_bytes
                  << ", \"optimistic_staged_bytes\": " << c.optimistic_staged_bytes
                  << ", \"full_checkpoint_fits\": " << (c.full_checkpoint_fits ? "true" : "false")
                  << ", \"naive_snapshot_delta_fits\": " << (c.naive_snapshot_delta_fits ? "true" : "false")
                  << ", \"optimistic_staged_fits\": " << (c.optimistic_staged_fits ? "true" : "false")
                  << "}" << (index + 1 == r.cuts.size() ? "" : ",") << "\n";
    }
    std::cout << "  ],\n  \"any_naive_snapshot_delta_fits\": "
              << (r.any_naive_snapshot_delta_fits ? "true" : "false")
              << ",\n  \"any_optimistic_staged_fits\": "
              << (r.any_optimistic_staged_fits ? "true" : "false")
              << ",\n  \"screen_commitment\": \"" << Hex(r.screen_commitment) << "\",\n"
              << "  \"execution_result\": {\"digest\": \"" << Hex(execution.digest)
              << "\", \"registers\": [";
    for (std::size_t index{0}; index < execution.registers.size(); ++index) {
        std::ostringstream value;
        value << std::hex << std::setfill('0') << std::setw(16) << execution.registers[index];
        std::cout << "\"" << value.str() << "\"" << (index + 1 == execution.registers.size() ? "" : ", ");
    }
    std::cout << "], \"schedule_digest\": \"" << Hex(execution.schedule_digest)
              << "\", \"dataset_digest\": \"" << Hex(execution.dataset_digest)
              << "\", \"memory_commitment\": \"" << Hex(execution.memory_commitment) << "\"}\n}\n";
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
        if ((argc == 8 || argc == 9) &&
            std::string_view{argv[1]} == "recursive-regenerate-iterative-work-stack") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            const std::uint64_t operation_limit = argc == 9
                ? std::stoull(argv[8]) : REGENERATION_OPERATION_LIMIT;
            if (operation_limit == 0) {
                throw std::invalid_argument("operation limit must be positive");
            }
            PrintRepeatedRecursiveRegeneration(
                seed, header, nonce, params, false, false, true, true,
                operation_limit, false, true);
            return 0;
        }
        if ((argc == 8 || argc == 9) &&
            std::string_view{argv[1]} == "recursive-regenerate-physically-accounted-bundle") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            const std::uint64_t operation_limit = argc == 9
                ? std::stoull(argv[8]) : REGENERATION_OPERATION_LIMIT;
            if (operation_limit == 0) {
                throw std::invalid_argument("operation limit must be positive");
            }
            PrintRepeatedRecursiveRegeneration(
                seed, header, nonce, params, false, false, true, true,
                operation_limit, true);
            return 0;
        }
        if ((argc == 8 || argc == 9) &&
            std::string_view{argv[1]} == "recursive-regenerate-operation-bounded-bundle") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            const std::uint64_t operation_limit = argc == 9
                ? std::stoull(argv[8]) : REGENERATION_OPERATION_LIMIT;
            if (operation_limit == 0) {
                throw std::invalid_argument("operation limit must be positive");
            }
            PrintRepeatedRecursiveRegeneration(
                seed, header, nonce, params, false, false, true, true,
                operation_limit);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "recursive-regenerate-dependency-bundle") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintRepeatedRecursiveRegeneration(seed, header, nonce, params, false, false, true);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "recursive-regenerate-target-checkpoint") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintRepeatedRecursiveRegeneration(seed, header, nonce, params, false, true);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "recursive-regenerate-checkpoint") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintRepeatedRecursiveRegeneration(seed, header, nonce, params, true);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "recursive-regenerate-repeated") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintRepeatedRecursiveRegeneration(seed, header, nonce, params);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "recursive-regenerate-first") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintRecursiveRegeneration(seed, header, nonce, params);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "checkpoint-screen") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintTimeCheckpointScreen(seed, header, nonce, params);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "bounded-reconstruct-indexed-gap") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintIndexedGapReconstruction(seed, header, nonce, params);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "bounded-reconstruct-paged") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintPagedReconstruction(seed, header, nonce, params);
            return 0;
        }
        if (argc == 8 && std::string_view{argv[1]} == "bounded-reconstruct-packed") {
            const Bytes seed = ParseHex(argv[2]);
            const Bytes header = ParseHex(argv[3]);
            const std::uint64_t nonce = std::stoull(argv[4]);
            const Params params{ParseSize(argv[5]), ParseSize(argv[6]), ParseSize(argv[7])};
            PrintPackedReconstruction(seed, header, nonce, params);
            return 0;
        }
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
                      << "   or: powvm_v1_cpp bounded-reconstruct-packed SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp bounded-reconstruct-paged SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp bounded-reconstruct-indexed-gap SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp checkpoint-screen SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp recursive-regenerate-first SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp recursive-regenerate-repeated SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp recursive-regenerate-checkpoint SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp recursive-regenerate-target-checkpoint SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp recursive-regenerate-dependency-bundle SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES\n"
                      << "   or: powvm_v1_cpp recursive-regenerate-operation-bounded-bundle SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES [OPERATION_LIMIT]\n"
                      << "   or: powvm_v1_cpp recursive-regenerate-physically-accounted-bundle SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES [OPERATION_LIMIT]\n"
                      << "   or: powvm_v1_cpp recursive-regenerate-iterative-work-stack SEED_HEX HEADER_HEX NONCE DATASET_BYTES SCRATCHPAD_BYTES PASSES [OPERATION_LIMIT]\n"
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
