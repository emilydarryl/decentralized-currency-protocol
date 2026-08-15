# PoW v1 External Attack Challenge

Status: **OPEN NON-CONSENSUS RESEARCH CHALLENGE; NO GATE ASSESSED**

Soveroot is inviting independent researchers to break its experimental proof-of-work design. The target is not Bitcoin, a live Soveroot network, or real funds. It is the isolated v1 research workload described in [the candidate specification](pow-v1-candidate-spec.md).

The challenge asks a narrow question: can an exact miner use no more than 131,072 bytes of mutable per-attempt attack memory—half the standard scratchpad—and still produce the same canonical proof as the ordinary evaluator at a practical cost?

No prize or bounty is currently offered. A missing submission, failed submission, or elapsed period without a published attack is not evidence that the design is secure.

## Plain-language explanation

Imagine a 98,304-page workbook. A normal miner keeps the whole working notebook. A challenge attacker gets half as much notebook space and may recreate discarded pages, compress information, or invent a better filing system.

The attacker wins the exact-completion track only by reaching the last page and producing the same final answer as the ordinary miner. Reaching farther than our current attackers is valuable evidence, but it is not a completed proof.

The project supplies a ruler for checking file formats, arithmetic outputs, memory ledgers, and work-counter totals. That ruler cannot see through a dishonest memory claim. Reviewers must inspect the code and then measure it in a controlled, network-disabled environment.

## Challenge tracks

### Qualification preflight

Three public 1,024-iteration cases verify that a submitted runner accepts the request format and emits exact v1 outputs. Ordinary full-memory code may be used for this preflight. Passing qualification makes no reduced-memory claim.

The committed case set is [`external_attack_qualification_v0.json`](../contrib/pow_research_v1/vectors/external_attack_qualification_v0.json).

### Screening track

The screening track uses the standard 98,304-iteration workload and the same five-million-operation ceiling used by the two internal bounded attack families. Exact completion is not required. Every partial, exhausted, refused, invalid, and unfavorable case is retained.

This track answers whether a new strategy advances the exact prefix under comparable bounded work. It cannot pass the time-memory gate.

### Exact-completion track

The completion track keeps the 131,072-byte memory ceiling but removes the artificial five-million-operation stop. All work counters remain mandatory. A successful case must complete all 98,304 iterations and reproduce the ordinary evaluator's complete result object.

An exact result does not automatically pass or reject the candidate. It triggers independent source review followed by controlled physical-memory and accepted-work throughput measurement under the frozen evaluation gates.

## What counts toward 131,072 bytes

The budget includes all mutable per-attempt attack state:

- retained or recreated scratch values;
- registers, accumulators, checkpoints, tags, indexes, maps, bitmaps, queues, and schedules;
- native and explicit stacks for every worker thread;
- allocator bookkeeping and reserved capacity;
- counters, transcripts, buffers, and inter-thread communication; and
- any other recovery-dependent state.

Read-only candidate code, the ordinary read-only epoch dataset and 64-entry schedule, fixed input bytes, and the measured process baseline before epoch preparation are excluded.

External spill files, databases, memory-mapped backing, network helpers, hidden workers, and future-aware traces or schedules retained during a run are forbidden. Logical allocation totals are only the first screen. Physical eligibility requires reproducible compiler evidence and controlled process-memory measurements.

## Work accounting

Every screening result reports these five nonnegative counters:

1. `logical_value_requests`
2. `replay_iterations`
3. `metadata_probes`
4. `checkpoint_probes`
5. `other_charged_operations`

`total_operations` must equal their exact sum. A strategy must map every attack-specific action to a counter. Work that does not honestly fit the first four categories belongs in `other_charged_operations` and must be explained in the manifest.

The operation total is a reproducible screening score, not a substitute for elapsed time, memory bandwidth, energy, or hardware measurements.

## Submission and fresh-case process

1. Pass the candidate's existing Python/C++ canonical vectors and the public qualification cases.
2. Open a draft GitHub issue using the PoW attack-submission template and request an evaluator-salt commitment. Do not freeze the source yet.
3. The evaluator publishes a SHA3-384 commitment to a private 32-byte evaluator salt.
4. Copy [`external_attack_submission_template_v0.json`](../contrib/pow_research_v1/external_attack_submission_template_v0.json), fill every field, and then freeze a public 40-hex-character source revision, reproducible build commands, manifest, and independent 32-byte submitter salt. Emit each evaluation using [`external_attack_results_template_v0.json`](../contrib/pow_research_v1/external_attack_results_template_v0.json).
5. The evaluator reveals its salt. The tool combines both salts and the frozen source revision with SHAKE-256 to derive eight unique, previously unused 32-bit seed indices. It publishes the selection record and committed case set.
6. Reviewers build and run the submission in a disposable, network-disabled environment. The project tool validates structure and independently recomputes every claimed canonical proof.
7. Publish the case set, environment, commands, raw output, accounting review, favorable and unfavorable rows, and an eligibility decision.

Fresh cases are hidden only until the source revision is frozen. They are revealed afterward so anyone can reproduce the result. Hidden testing never replaces public evidence or independent review.

## Tooling

Validate the template shape:

```console
python3 -m contrib.pow_research_v1.external_attack_challenge \
  validate-submission \
  --submission contrib/pow_research_v1/external_attack_submission_template_v0.json \
  --allow-template
```

Generate and validate the public qualification cases:

```console
python3 -m contrib.pow_research_v1.external_attack_challenge \
  make-cases --track qualification \
  --seed-index 0 --seed-index 1 --seed-index 2 \
  --output build/pow-v1-qualification-cases.json

python3 -m contrib.pow_research_v1.external_attack_challenge \
  validate-cases --cases build/pow-v1-qualification-cases.json
```

Validate a real manifest and result set:

```console
python3 -m contrib.pow_research_v1.external_attack_challenge \
  validate-submission --submission submission.json

python3 -m contrib.pow_research_v1.external_attack_challenge \
  make-fresh-cases --track screening --submission submission.json \
  --evaluator-salt-hex REVEALED_64_HEX_CHARACTERS \
  --output assigned-cases.json

python3 -m contrib.pow_research_v1.external_attack_challenge \
  verify-results --submission submission.json \
  --cases assigned-cases.json --results results.json
```

The verifier never runs the submitted entrypoint. The manifest stores command arguments as arrays so an evaluator can inspect them without interpreting a shell string. Untrusted compilation and execution belong in a separately secured environment, never project CI. The evaluator must publish its salt commitment before the source freeze and reveal the matching salt afterward; otherwise the fresh case set is invalid.

## Independence and prior work

A second attack model must disclose copied code, shared authorship, prior collaboration, and conceptual dependence on repository attacks. A language port of the checkpoint ladder or frontier policy is useful differential evidence but is not an independently developed strategy.

Pseudonymous submissions are welcome if their source, build, accounting, and results are reproducible. Authors should not include private keys, tokens, personal data, or secrets in a submission.

## Decision policy

- **Exact eligible proof:** begin independent code review and controlled physical-host measurements immediately; apply the frozen pass, redesign, and rejection thresholds only after the required evidence exists.
- **Partial improvement:** preserve and study the strategy, but leave the gate open and not assessed.
- **Invalid accounting:** preserve the artifact with the exact ineligibility reason; do not silently repair or discard it.
- **No successful submission:** leave the gate open and not assessed. Failure to find an attack is not proof that none exists.

The challenge itself changes no consensus rules, node behavior, mining protocol, issuance, or mainnet status.
