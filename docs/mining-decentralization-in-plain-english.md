# Mining Decentralization in Plain English

Status: **PUBLIC EXPLAINER FOR AN UNFINISHED RESEARCH PROTOCOL**

Soveroot is trying to make mining power harder to concentrate, while being honest that no blockchain can guarantee that mining will remain decentralized forever.

The project is not ready for public mining or monetary use. The Bitcoin-derived node and private two-node `labnet` work, but the proposed proof of work is still isolated research code and is not part of block consensus.

## The problem we are trying to reduce

Mining can become concentrated in several different ways:

- a small number of companies may own the fastest hardware;
- miners may depend on a few pools to choose transactions and create block templates;
- large facilities may obtain cheaper electricity, financing, cooling, chips, or regulation; and
- miners may appear independent while actually being controlled by the same organization.

One consensus rule cannot solve all of these problems. Soveroot therefore separates the work into three layers: mining hardware, pool coordination, and rule governance.

## 1. Making mining hardware less easy to monopolize

Bitcoin mining repeatedly performs one well-known calculation. That made it worthwhile to build extremely specialized machines that perform that calculation much better than ordinary computers.

Soveroot is researching a different kind of proof of work. Its rules would remain fixed, but the exact workload would change automatically from public chain data. The workload is also designed to require substantial memory and memory bandwidth.

The goal is to keep commodity CPUs and GPUs relevant and make a narrow-purpose secret advantage more expensive and shorter-lived. This is a research goal, not a promise. A company could still build specialized hardware, and a large facility could still benefit from cheap power and capital.

## 2. Preventing a pool from controlling every miner's block

A mining pool can perform two separate jobs:

1. combine many miners' work so payouts are less unpredictable; and
2. choose which transactions go into the block.

Soveroot wants to separate those jobs. Under the proposed official mining profile, each miner chooses transactions using its own node, constructs its own block candidate, and uses an authenticated Stratum V2 connection only for share accounting and payouts. A P2Pool-like decentralized share system is also a required testnet workstream.

This means miners could cooperate on predictable payouts without automatically giving one pool operator control over block contents.

The base protocol cannot reliably enforce a rule such as "no pool may exceed 10 percent." A large operator could create many names, keys, and servers. Enforcing real-world identity would require a permissioned authority, which would itself be centralized.

## 3. Keeping miners from controlling the rules

Miners propose blocks; independently operated nodes decide whether those blocks follow the rules. A miner with substantial hash power cannot make an invalid block valid unless users voluntarily install software accepting the changed rules.

Soveroot therefore treats miner signaling as readiness information, not a binding vote. Consensus changes require explicit software adoption, independent validation, public review, and the activation process documented by the project.

Hash power still matters. Concentrated miners can censor transactions temporarily, reorganize recent blocks, or delay an upgrade. The design reduces miner governance authority; it does not make concentrated hash power harmless.

## What the current memory experiment means

Imagine a mining job as an open-book exam with 98,304 steps. A normal miner keeps the whole notebook available. We are deliberately building a cheating miner that keeps only half the allowed memory and tries to recreate missing pages whenever it needs them.

The first version recreated one missing value correctly. The next version reused its notes and recreated 51 missing values correctly. It performed 1,000,000 replayed calculations but advanced the real job only to step 983. Another tested memory split reached step 999. None of the tested versions finished the job or produced a valid proof.

We then tried giving the half-memory miner small bookmarks containing the calculation's internal state. The best bookmark version reached only step 892 under the same work limit—107 steps fewer than the best version without bookmarks. A bookmark helps restore the calculator's state, but it does not contain the discarded notebook page the miner actually needs. Recreating that page adds another layer of work, and the bookmarks also consume space that could have held useful notes. We therefore rejected this particular checkpoint design.

The next version made each bookmark remember one exact notebook value as well as the calculator's state. That removed the extra layer of work. On a sparse memory split that previously reached only step 719, the improved bookmarks reached step 999—a gain of 280 steps. However, step 999 was already the best result from the ordinary recursive attacker. The smarter bookmarks improved a weak setup but did not move the overall record, and they still did not finish the 98,304-step job.

We then let each bookmark carry four values already being used by that calculation step. The best seed-zero setup reached step 1,006, seven steps beyond the previous record. It did this even though the larger bookmarks displaced 32 general-purpose memo entries. That is a real improvement to the attack, but still only about 1.02% of the job and still no proof.

The result did not generalize cleanly. The same setup helped a second seed, hurt a third, and a later seed spent several minutes in recursive calls and lookups without returning. The one-million limit counts replayed calculation steps, but it does not yet cap all bookkeeping operations. We therefore preserve the new record while refusing to claim that bundles are generally better.

That is encouraging because reducing memory was very expensive in this experiment. It is not yet proof of memory hardness. A smarter recovery method may exist, and the prototypes have not measured every byte used by the program's real call stack and allocator.

## Where we are now

| Part | Plain-language status |
| --- | --- |
| Bitcoin-derived node and command-line client | Working development foundation |
| Private two-node lab network | Working in automated tests |
| Proposed mining workload | Research prototype only |
| Half-memory attack | Correctly recovers some data but cannot finish |
| Independent Python and C++ comparison | Passing for the current experiment |
| Commodity CPU/GPU fairness | Not demonstrated |
| ASIC, FPGA, and quantum analysis | Not complete |
| Decentralized pool system | Designed on paper; not implemented end to end |
| Public testnet | Not launched |
| Production or mainnet readiness | Not ready |

## What happens next

The next experiment will put one deterministic ceiling around all attacker work: replay iterations, recursive calls, memo probes, and checkpoint probes. Then we can finish the multi-seed comparison without allowing one type of bookkeeping to run indefinitely. We should try hard to defeat our own design before asking anyone to trust it.

If an exact half-memory miner eventually finishes, we will measure its actual memory and speed on controlled physical computers. The candidate is useful only if independent implementations and hardware testing show that saving memory causes a large enough performance penalty without making verification expensive for ordinary nodes.

Even a successful proof-of-work result would address only one source of mining concentration. Stratum V2 job declaration, decentralized share accounting, independent block publication, accessible node operation, conservative governance, and a fair launch must work together.

## Short glossary

- **Proof of work:** the difficult calculation miners perform to propose a block.
- **Hash power:** the total rate at which mining work is attempted.
- **Mining pool:** a service or protocol that combines miners' work and distributes payouts.
- **Block template:** the transactions and other data a miner proposes to include in a block.
- **Memory-hard:** designed so that using substantially less memory causes a major loss of speed.
- **Node:** software that independently checks blocks and rejects any block that violates consensus rules.
- **Consensus:** the objective rules that every validating node applies.
- **Labnet:** Soveroot's private development network; it has no monetary value.

Readers who want the technical evidence can continue with the [proof-of-work research specification](pow-vm-research.md), [latest dependency-bundle result](pow-v1-dependency-bundle-regeneration.md), and [research ledger](research-ledger.md).
