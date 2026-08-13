# Soveroot PoW v1 Recursive Value Regeneration

Status: **NON-CONSENSUS FIRST REGENERATION PILOT; TIME-MEMORY GATE NOT ASSESSED**

This Stage C pilot demonstrates one exact recursive scratch-value recovery inside the same logical half-scratch arena as primary execution. It uses no offline trace, future schedule, spill file, mapped backing store, helper process, or second scratch arena. It then deliberately refuses at the next materialized primary-cache miss and emits no proof digest.

The machine-readable method is [`recursive_regeneration_v0.json`](../contrib/pow_research_v1/recursive_regeneration_v0.json). Fixed independent Python/C++ boundaries are in [`vectors/recursive_regeneration_v0.json`](../contrib/pow_research_v1/vectors/recursive_regeneration_v0.json).

## Construction

The evaluator divides the half-scratch budget into a written-word bitmap, a deliberately small direct-mapped primary cache, a fixed logical frame reserve, and a four-way set-associative regeneration memo. Each memo entry is exactly 12 logical bytes: a packed 32-bit `(stop iteration, word)` identity and one 64-bit value.

When primary execution encounters its first missing materialized word, `value_at(word, stop)` replays the VM state from genesis to `stop`. Every missing replay read recursively requests the required word at the earlier consuming iteration. Child stop iterations are therefore strictly smaller than their parents, making the dependency computation acyclic. The engine tracks the requested word through deterministic writes, memoizes exact completed values, retries the interrupted primary operation, and refuses at the next miss.

The packed key uses 15 word bits and is restricted to the current v1 research profiles. Key overflow, recursion-depth exhaustion, or the one-million-iteration replay-work limit causes fail-closed refusal.

## Byte accounting

For the 131,072-byte standard half-scratch ceiling:

| Structure | Bytes |
| --- | ---: |
| Fixed state and control reserve | 512 |
| Written-word bitmap | 4,096 |
| Primary cache, 123 entries | 1,968 |
| Logical frames, 20 at 104 bytes | 2,080 |
| Regeneration memo, 10,200 entries at 12 bytes | 122,400 |
| Unused alignment remainder | 16 |
| **Admitted total** | **131,072** |

The frame reserve charges eight registers, the accumulator, target value, packed stop/word/iteration/phase state, and one saved read value per active logical frame. The current Python and C++ prototypes still use their language/runtime call stacks to execute recursion. Compiler/interpreter stack bytes, allocator overhead, and process resident memory are not measured, so this logical admission is not yet physical half-memory evidence.

## Standard seed-zero boundary

The first primary miss occurs at consumer iteration 159, read slot 1, word 59. Recursive replay returns the exact full-memory value `12843086673575782630` after 25,281 completed replay iterations at maximum depth 3. Retrying the operation advances exact primary execution to iteration 270, where the pilot refuses on its intentionally unsupported second miss at word 62.

| Metric | Result |
| --- | ---: |
| Half-scratch budget | 131,072 bytes |
| First value recovered | 1 |
| Recursive replay work | 25,281 iterations |
| Maximum logical depth | 3 of 20 frames |
| Exact primary prefix | 270 iterations |
| Proof digests produced | 0 |

First-boundary commitment: `9839a09897167f1bb97377abb0c7d5617aac5d3d835024fa85278c9bed556fdc4570a6a3df1b98014cd3ec1d860ddacb`

Transcript commitment: `7b126e274dffd731c88767cfbe6daa4951a088e2084fc8e18c4cdf319351d0ace47d5e87ddb5561a972fd2b8c9de3cf1`

The three minimum-profile fixed vectors independently agree between Python and C++ on layout, exact recovered value, recursion counters, refusal boundary, and commitments. Their maximum depths range from 8 to 16 and the most demanding fixed case completes 923,778 replay iterations, exercising both the frame and work ceilings closely without crossing them.

## Interpretation and next step

This is a qualitative advance over flat replay tables: the recovered historical value is computed from recursively recovered dependencies instead of retaining every prior write. It is not a throughput-optimized allocation. Giving only 1/64 of the available 16-byte primary slots to normal execution intentionally creates early misses and leaves nearly the entire arena for the recursive core.

The earlier indexed-gap pilot reached primary iteration 5,759 before exhausting a replay-value representation. This pilot reaches only iteration 270 because it deliberately stops after proving one recursive recovery. Those prefixes do not compare attack quality; they test different questions.

The next milestone is repeated recursive recovery with deterministic memo reuse and an allocation sweep across primary cache, frame reserve, and memo capacity. It must eventually reproduce exact final digests, charge actual stack and allocator memory, measure peak resident memory on controlled hosts, and report throughput. Until then the time-memory gate remains `OPEN` and `NOT_ASSESSED`.
