# Mining Decentralization in Plain English

Status: **PUBLIC EXPLAINER FOR AN UNFINISHED RESEARCH PROTOCOL**

Soveroot is trying to make mining power harder to concentrate, while being honest that no blockchain can guarantee that mining will remain decentralized forever.

The project is not ready for public mining or monetary use. The Bitcoin-derived node, private two-node `labnet`, and first outside-the-daemon labnet miner work, but the proposed proof of work is still isolated research code and is not part of block consensus.

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

The labnet prototype now demonstrates the independent half of this idea.
A small program outside the node asks the miner's own node for transactions,
builds the block, performs easy development proof of work, and publishes the
block directly. A second test lets it report work to a simple accounting
process, switches that process off, and proves the miner still publishes the
next block without restarting. The authenticated connection's rules are frozen
in a private-labnet Stratum V2 and Job Declaration profile with nine test stories:
acceptance, rejection, timeout, disconnect, downgrade, malformed data,
equivocation, replay, and failed server authentication. A reference connection
now uses those real encrypted messages: the first miner-created job is accepted,
the coordinator is stopped, and the same miner directly publishes its next
block anyway. A second mining program was then written separately. The two
programs must create the same protocol messages and complete block byte for
byte, and each must publish its own block. This lowers the risk that one
program's private interpretation or bug defines the rules.

The newest test keeps one miner alive while its preferred coordinator rejects
its job, disconnects, stalls, sends malformed information, and tries an older
protocol. Each time, the miner takes the same self-created block to a backup
coordinator. When both coordinators disappear, it mines and publishes directly.
The accounting service records how much verified test work each wallet payout
script contributed, but it never holds a wallet key or any coins. In everyday
terms, it first produced an auditable bill, not a bank account or a payment.

The newest test adds a second bookkeeper. Each stores its own work receipts.
They compare records, one is switched off while mining continues, and the
stale copy imports what it missed after restart. Both must calculate exactly
the same payment list. The miner then puts both payments directly in the new
block instead of sending the reward through a pool wallet. If either
bookkeeper is missing or the lists differ, pooled settlement stops.

This is meaningful progress, but both bookkeepers still run on one laboratory
machine and know each other's address in advance. A real decentralized system
still needs a public P2Pool-like share history, independent operators, and
defenses against fake identities, selective message delivery, and collusion.
The exact proof and limits are in [Replicated share accounting and direct
coinbase settlement](replicated-share-settlement-labnet.md).

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

The result did not generalize cleanly. The same setup helped a second seed, hurt a third, and a later seed spent several minutes in recursive calls and lookups without returning. The one-million limit counted replayed calculation steps but did not cap all bookkeeping operations.

We have now closed that loophole. The attacker receives five million total tokens, and every recursive request, replayed step, memo check, and bookmark check spends one. All eight planned seeds stop exactly at the limit. They reach between step 480 and step 999, and none produces a proof. Under the fairer accounting, the old 1,006 seed-zero record falls back to 999, so the larger bookmarks have not demonstrated a general advantage. One seed also performs more than 1.5 million short-lived recoveries while advancing only 480 steps, exposing severe cache thrashing.

We then audited memory that the model had treated as free. The recursive C++ function used the computer's real call stack, and its audit log grew with every recovery. That version reserved stack and allocator space before sizing its notebook and replaced the growing log with one fixed 48-byte rolling fingerprint. With those costs included, the eight attackers reached only steps 641 through 853 and produced no proof.

The newest version removes that hidden recursive call chain. Think of it as replacing reminders scattered on the computer's desk with twenty numbered index cards stored in a drawer inside the attacker's notebook. Every unfinished recovery is written on one fixed-size card, and the attacker refuses if the drawer would overflow. Reclaiming the earlier conservative stack reserve gives the attacker more usable notebook space, so the eight cases now reach steps 712 through 952. The best case still completes less than 1% of the 98,304-step job, every case uses all five million work tokens, and none produces a proof.

We then made the bookmarks smarter. Instead of searching one tray of twelve bookmarks, the attacker uses four labeled drawers for short-, medium-, and long-distance history. A page number points to one place in each drawer, so a lookup always costs four checks. This raises the middle result from step 886 to 945.5 and the best from 952 to 982. One seed falls backward from 952 to 840, and we keep that unfavorable result. Every case again uses all five million tokens, the best still reaches less than 1% of the job, and no case produces a proof.

We have also completed a second kind of half-memory attacker. Instead of saving calculator-state bookmarks, it saves expensive recreated notebook pages. Each page gets two possible lockers. The attacker always checks both and prefers later pages because they usually take more work to recreate. This produced about 1.42 million useful locker hits per case, but the two checks on every access and replay from the beginning still consumed all five million tokens. The eight fresh cases reached steps 714 through 828, with a middle result of 794. The best completed only 0.8423% of the job, and none produced a proof. These cases used different seeds from the bookmark experiment, so the numbers are not a fair speed contest between the two designs.

That is encouraging because reducing memory was very expensive in this experiment. It is not yet proof of memory hardness. A smarter recovery method may exist, and controlled computers have not yet measured the complete process and allocator behavior.

## Where we are now

| Part | Plain-language status |
| --- | --- |
| Bitcoin-derived node and command-line client | Working development foundation |
| Private two-node lab network | Working in automated tests |
| External miner-created labnet block | Working in the packaged automated test |
| Proposed mining workload | Research prototype only |
| Half-memory attack | Two frozen strategies cannot finish; the newest reaches at most 0.8423% |
| Independent Python and C++ comparison | Fixed-vector parity is enforced in CI |
| Commodity CPU/GPU fairness | Not demonstrated |
| ASIC, FPGA, and quantum analysis | Not complete |
| Decentralized pool system | Three separate loopback processes exchange the frozen share notebook and recover from partition, selective relay, and restart; independent public operators remain unfinished |
| Public testnet | Not launched |
| Production or mainnet readiness | Not ready |

## What happens next

The external attack challenge and [public research call](pow-v1-independent-research-call.md) are now specified. Think of them as publishing the exam, the half-size notebook rule, the scoring ruler, the form for showing every hidden pocket, and the instructions for independent graders. An outside researcher first proves that their program produces correct small answers, freezes its source code, and then receives eight fresh cases. Reviewers inspect every claimed memory pocket and unit of work before running the code on an isolated computer. The project keeps successful, partial, failed, invalid, and ineligible results. The next step is to obtain and independently review a genuinely different attack submission. If an exact half-memory miner eventually finishes, we will measure its speed and resident memory on controlled physical computers. No submission—or many failed submissions—would still not prove the design secure. There is currently no bounty or token reward for participation.

Even a successful proof-of-work result would address only one source of mining concentration. Stratum V2 job declaration, decentralized share accounting, independent block publication, accessible node operation, conservative governance, and a fair launch must work together.

The pool work has also advanced by one deliberately small step. Imagine a
notebook in which each page points to the previous page and contains a small
mining proof plus the wallet script that earned it. Two calculators written
separately now read that notebook and agree on which history has the most work,
which pages are old enough to count, and how the last four settled pages are
grouped for payout. They also agree on 15 examples involving honest histories,
forks, delayed pages, fake difficulty, copied proofs, bad parents, malformed
headers, and stale work.

That result prevents one software implementation from quietly inventing its
own interpretation of the notebook. By itself it did not stop a real network
attacker: the pages were local files and the test round information came from
a trusted fixture. See [Sharechain private-lab profile v0](sharechain-v0.md).

That three-process experiment is now working. Each notebook process has a
different prearranged secret for each neighbor. Repeated, altered, oversized,
or storage-flooding messages fail closed. We separate the processes, deliver
pages late, let one process relay only part of the notebook, restart another,
and reconnect them. They end with the same winning history and payout
calculation, and they preserve two conflicting authenticated claims instead of
hiding the conflict.

The next safety layer is also working. Each test peer signs fresh connection
information with a pinned public key, both sides derive a one-session secret,
and altered identities, networks, algorithms, transcripts, old connections,
and repeated messages fail. Exact limits now apply per identity and address
prefix. A deterministic selector refuses peer sets concentrated in one address
prefix or configured operator group, and long-disconnected peers may catch up
only within a fixed 1,024-share budget. Conflicting signed claims can be checked
by someone who knows the public key instead of by only the two holders of a
shared password.

This remains one computer talking to itself, now through three distinct
loopback address prefixes. Configured operator and transport labels are not
proof of real independence; an attacker can invent them. The readable Ed25519
and X25519 test implementation is classical, not post-quantum or production
reviewed, and the signed preflight does not yet sit directly on every live
share frame. Separate routed namespaces, independent operators, hostile
Internet evidence, key distribution, and reviewed hybrid authentication are
still required. See [Multi-host share synchronization safety profile v1](sharechain-multihost-v1.md).

## Short glossary

- **Proof of work:** the difficult calculation miners perform to propose a block.
- **Hash power:** the total rate at which mining work is attempted.
- **Mining pool:** a service or protocol that combines miners' work and distributes payouts.
- **Block template:** the transactions and other data a miner proposes to include in a block.
- **Memory-hard:** designed so that using substantially less memory causes a major loss of speed.
- **Node:** software that independently checks blocks and rejects any block that violates consensus rules.
- **Consensus:** the objective rules that every validating node applies.
- **Labnet:** Soveroot's private development network; it has no monetary value.
- **Sharechain:** An off-chain linked history of lower-difficulty mining proofs used to choose a payout history without giving one pool operator control of block validity.

Readers who want to participate can continue with the [public research call](pow-v1-independent-research-call.md). Technical readers can continue with the [external attack challenge](pow-v1-external-attack-challenge.md), [evaluator runbook](pow-v1-external-evaluator-runbook.md), [latest cost-aware frontier result](pow-v1-frontier-pebbling-attacker.md), and [research ledger](research-ledger.md).
