# Independent Researchers Wanted: Try to Break Soveroot PoW v1

Status: **OPEN PUBLIC CALL FOR NON-CONSENSUS RESEARCH**

Soveroot needs independent researchers to challenge its proposed proof of work before anyone considers putting it into consensus. The candidate is isolated research code. It does not secure a public network, has not passed its evaluation gates, and is not ready for monetary use.

In plain language, we designed a lock and built tools for testing it. We now need people who did not design the lock to try different ways of opening it with less memory than an ordinary miner.

## What we are asking researchers to test

An ordinary standard-profile evaluation uses a 262,144-byte scratchpad. The challenge asks whether an attacker can reproduce the exact canonical result while using no more than 131,072 bytes of total mutable attack state.

That limit includes retained values, recreated values, indexes, stacks, allocator reserves, counters, buffers, transcripts, and worker communication. Spill files, memory-mapped backing, network helpers, hidden workers, and precomputed future-aware traces are forbidden.

The full rules are frozen in the [external attack challenge](pow-v1-external-attack-challenge.md). The machine-readable contract is [`external_attack_challenge_v0.json`](../contrib/pow_research_v1/external_attack_challenge_v0.json).

## Two useful ways to participate

### Build an attack

Develop a reduced-memory evaluation strategy that is meaningfully independent of the repository's checkpoint-ladder and cost-aware frontier attacks. A language port or parameter adjustment is still useful differential evidence, but it does not count as a separately developed attack model.

You may enter either or both tracks:

- **Screening:** run eight fresh standard cases under a five-million-operation ceiling. Partial progress is preserved and compared honestly.
- **Completion:** run eight fresh standard cases without an artificial operation ceiling. Success requires the complete exact canonical proof.

Start with the three small public qualification cases. Ordinary full-memory code is allowed for qualification because that stage checks only interoperability.

### Review an attack

Evaluators can help without designing an attack. Useful work includes source review, memory-ledger review, operation-counter mapping, reproducible builds, compiler stack evidence, sandboxed execution, physical-memory measurement, and independent proof verification.

Evaluators should read the [external evaluator runbook](pow-v1-external-evaluator-runbook.md) and open an evaluator-interest issue through the repository's issue chooser.

## Submission path

1. Read the [challenge guide](pow-v1-external-attack-challenge.md) and run the public qualification cases.
2. Open a draft issue using the **PoW v1 external attack submission** template. Request an evaluator-salt commitment before freezing your source.
3. Wait for an evaluator to publish that commitment.
4. Freeze a public source revision, manifest, reproducible build commands, and submitter salt.
5. The evaluator reveals its salt and derives eight fresh cases bound to the frozen source revision.
6. Reviewers inspect the code and accounting, then run it in a disposable, network-disabled environment.
7. Publish the cases, raw results, commands, environment, review findings, and every favorable or unfavorable row.

Use the [GitHub issue chooser](https://github.com/emilydarryl/decentralized-currency-protocol/issues/new/choose) to begin. Pseudonymous participation is welcome when the code, build, accounting, and evidence are public and reproducible.

## What makes a submission valuable

A result does not need to break the candidate to help:

- an exact eligible proof is urgent evidence and triggers controlled-host measurement;
- a longer exact prefix may expose a better attack direction;
- a clean refusal or exhaustion result helps compare strategies;
- an accounting failure can reveal ambiguity in the challenge; and
- an independent review can find hidden allocations or uncharged work.

All results are preserved. The project will not quietly discard an unfavorable result or silently repair an ineligible submission.

## What this call does not promise

- There is currently **no bounty, prize, employment offer, token allocation, or guaranteed compensation**.
- Passing qualification does not establish reduced-memory eligibility.
- A successful proof does not automatically reject the candidate; its implementation and physical memory use still require independent review.
- No successful submission does not establish security and does not pass a gate.
- Project CI never compiles or executes submitted attack code.
- The challenge changes no consensus rule, node behavior, mining reward, or network status.

The machine-readable status of this call is [`independent_research_call_v0.json`](../contrib/pow_research_v1/independent_research_call_v0.json). Its counts remain zero until public, reviewable artifacts exist.
