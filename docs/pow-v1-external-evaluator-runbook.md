# PoW v1 External Evaluator Runbook

Status: **REVIEW PROCEDURE FOR UNTRUSTED NON-CONSENSUS RESEARCH CODE**

This runbook turns the [external attack challenge](pow-v1-external-attack-challenge.md) into a repeatable review process. It does not authorize running untrusted code on a personal workstation, production service, wallet host, mining host, or GitHub Actions runner.

## Roles and separation

One person may coordinate the public record, but the evidence should identify who performed each role:

- **submitter:** freezes the attack source, manifest, build commands, and submitter salt;
- **case evaluator:** commits to and later reveals the evaluator salt;
- **code reviewer:** maps allocations and operations to the source;
- **execution reviewer:** builds and runs the source in the disposable environment; and
- **evidence reviewer:** independently validates artifacts and canonical proofs.

Conflicts, shared authorship, copied code, private coordination, and earlier access to the strategy must be disclosed. A project contributor may administer the process, but that does not make the attack independently developed.

## Phase 1: open the record

1. Require a draft submission issue with a stable submission ID, author or pseudonym, public contact or `none`, intended tracks, strategy summary, and prior-work disclosure.
2. Confirm that no source revision or submitter salt has been frozen yet.
3. Assign one case evaluator and record any conflict of interest.
4. Create a new unpredictable 32-byte evaluator salt for this submission. Never reuse a salt.
5. Publish only the SHA3-384 evaluator-salt commitment defined by the challenge. Keep the salt private and offline until the source freeze is complete.

Do not place the unrevealed salt in an issue, pull request, chat, CI variable, shell transcript, or repository file. If it is exposed early, mark the round invalid and begin again with a new evaluator and salt.

## Phase 2: freeze the submission

Require all of the following before revealing the evaluator salt:

- a public source URL and full 40-character revision;
- a validated submission manifest;
- reproducible build commands expressed as argument arrays;
- a public source license sufficient for reproduction and review;
- the submitter's independent 32-byte salt;
- a complete mutable-memory allocation ledger;
- a mapping for every charged operation; and
- limitations and relationships to earlier work.

Review the pinned revision directly. Mutable branches, release names, file-sharing links, and container tags such as `latest` do not freeze source.

Validate the manifest without executing its entrypoint:

```console
python3 -m contrib.pow_research_v1.external_attack_challenge \
  validate-submission --submission submission.json
```

Record the manifest hash and source revision in the issue. After this point, any source or manifest change creates a new round with a new evaluator salt.

## Phase 3: reveal and assign cases

1. Reveal the exact 32-byte evaluator salt.
2. Recompute its commitment and compare it with the value published in Phase 1.
3. Generate screening or completion cases using the frozen manifest and revealed salt.
4. Validate the case set before any execution.
5. Publish the salt, selection record, exclusions, all eight cases, and case-set commitment.

```console
python3 -m contrib.pow_research_v1.external_attack_challenge \
  make-fresh-cases --track screening --submission submission.json \
  --evaluator-salt-hex REVEALED_64_HEX_CHARACTERS \
  --output assigned-cases.json

python3 -m contrib.pow_research_v1.external_attack_challenge \
  validate-cases --cases assigned-cases.json
```

The cases become public after source freeze. Continued secrecy is neither required nor desirable.

## Phase 4: review before execution

Two reviewers should independently inspect the source when possible. At minimum, account for:

- every mutable allocation and reserved capacity;
- native and explicit stacks for every thread;
- allocator metadata and runtime-owned buffers;
- transcripts, logs, counters, queues, and inter-thread messages;
- files, memory mappings, subprocesses, network access, accelerators, and IPC;
- precomputation or future-aware data retained during an attempt; and
- every attack-specific operation that must enter one of the five counters.

Reject shell-string entrypoints, undeclared dynamic allocation after start, external storage, hidden helpers, missing counter mappings, or an allocation total above 131,072 bytes. Preserve the submission and state the exact ineligibility reason.

## Phase 5: isolated build and execution

Build and run the reviewed submission only in a disposable, network-disabled environment.

Use a disposable machine or virtual machine with:

- no credentials, wallets, private keys, SSH agents, browser sessions, or personal files;
- outbound and inbound networking disabled;
- no mounted host directories other than read-only reviewed inputs;
- resource limits and process monitoring enabled;
- a fresh toolchain record and dependency inventory; and
- complete stdout, stderr, exit-status, process-tree, file-access, and memory evidence retained.

Do not use project CI for this phase. Treat the submission, its build system, dependencies, and output parsers as hostile until reviewed.

## Phase 6: verify and publish

Validate the result envelope and independently recompute every claimed canonical proof:

```console
python3 -m contrib.pow_research_v1.external_attack_challenge \
  verify-results --submission submission.json \
  --cases assigned-cases.json --results results.json
```

Publish:

- frozen source and manifest identifiers;
- evaluator commitment and revealed salt;
- assigned case set and commitment;
- exact build and run commands;
- host, compiler, dependency, and isolation records;
- raw results and logs;
- logical allocation and operation reviews;
- physical-memory evidence when applicable;
- conflicts, limitations, and deviations; and
- a per-case decision: complete, exhausted, refused, invalid, or ineligible.

Artifact validation does not prove a memory claim. An exact canonical proof triggers controlled physical-host measurement; it does not pass the time-memory gate by itself. Partial or unsuccessful evidence is still published, and the gate remains **OPEN / NOT ASSESSED** until every frozen requirement is satisfied.

## Stop conditions

Stop execution and preserve evidence if the submission attempts network access, reads undeclared files, launches an undeclared process, changes its own frozen artifacts, exceeds a resource boundary, or produces output outside the declared result path. Do not continue merely to obtain a more favorable row.
