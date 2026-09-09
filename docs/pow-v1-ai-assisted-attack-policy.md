# PoW v1 AI-Assisted Attack Policy

Status: **ALLOWED RESEARCH METHOD; NOT INDEPENDENT REVIEW BY ITSELF**

AI tools may be used to challenge the isolated PoW v1 candidate. They can help propose replay and pebbling strategies, inspect allocation ledgers, generate fuzz cases, translate an independently conceived algorithm, optimize code, search parameter spaces, and criticize specifications. Their output is untrusted research material and receives no evidentiary credit until a human freezes, understands, reviews, and reproduces it under the ordinary challenge rules.

## Required disclosure

An AI-assisted submission SHALL disclose:

- provider and model identifier, including the dated version when available;
- whether the model ran locally or through a hosted service;
- the human operators and dates of use;
- repository files, prior attacks, private notes, and other context supplied;
- system instructions and prompts sufficient to reproduce the research direction, except secrets;
- tools, code execution, retrieval, and external services available to the model;
- which design, source, tests, prose, and accounting entries were model-generated or model-modified;
- material outputs that were rejected or corrected; and
- the human review used to establish understanding and correctness.

Do not publish credentials, private keys, unrevealed evaluator salts, personal data, or provider-private chain-of-thought. A concise prompt-and-action transcript is sufficient; hidden reasoning is neither required nor accepted as evidence.

## Independence classification

Each submission receives one classification:

- **human-origin, AI-assisted implementation:** a human independently designed the attack and used AI for bounded implementation or review;
- **AI-origin, human-verified strategy:** AI proposed a material attack idea that humans subsequently specified and verified;
- **AI reproduction or derivative:** the work ports, tunes, or recombines disclosed prior attacks; or
- **provenance insufficient:** material model, prompt, context, or authorship information is missing.

AI-origin work can produce valid attack evidence. It does not count as a genuinely independent human attack model, an independent code review, or an independent evaluator. Separate conversations, agents, or vendors count as separate exploratory searches only when their context and operators are disclosed; they do not automatically establish independence.

## Safety and validation

AI-generated source and dependencies are treated as untrusted. They SHALL NOT run in project CI or on a wallet, mining, production, credential-bearing, or personal host. The ordinary evaluator runbook applies without exception.

Before fresh cases are assigned, a human submitter SHALL:

1. pass all qualification cases;
2. explain the algorithm without relying on model output;
3. inspect every mutable allocation, stack, subprocess, file, accelerator, and operation counter;
4. remove undeclared network and dynamic-code behavior;
5. freeze a public source revision and complete manifest; and
6. attest responsibility for every submitted claim.

The canonical verifier, controlled physical measurements, and human source review—not model confidence—decide whether an output is exact and eligible.

## Useful AI experiments

High-value experiments include searching new cache policies, finding shared state across nonces, synthesizing bounded pebbling schedules, detecting mismatches between Python and C++, fuzzing canonical serialization, and adversarially auditing the memory ledger. Low-value experiments include asking a model whether the construction is secure, generating many cosmetic variants of an existing attack, or treating agreement between agents as review consensus.
