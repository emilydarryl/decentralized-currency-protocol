# Routed share synchronization namespace experiment v1

Status: **working live-session laboratory profile; one machine and one administrator, not independent Internet operation**

## Plain-English summary

The previous safety experiment proved that the proposed identity, connection,
rate, replay, diversity, and recovery rules behaved deterministically. It still
created the signed sessions before starting the three notebook processes and
then handed those processes ordinary shared secrets. The signed safety layer
was therefore not protecting the real socket boundary.

This experiment removes that shortcut. Four notebook validators run as four
separate Linux processes in four network namespaces. Each namespace has a
private address in a different `/24`. A fifth, disposable router namespace
forwards packets between them, so the experiment does not depend on or alter
the GitHub host's forwarding policy.
Before one validator can exchange a share page with another, it must:

1. connect from its pinned namespace address;
2. sign a fresh hello with its pinned Ed25519 laboratory identity;
3. verify the other side's signed hello and configured operator information;
4. derive a fresh X25519/HKDF session key bound to both hellos; and
5. carry the share request and response inside authenticated v1 session frames.

There is no configured pairwise peer password on the wire. The already-tested
v0 validator remains unchanged behind this boundary. A deterministic internal
adapter feeds an authenticated payload into that validator in memory; its key
is never stored in a peer configuration or transmitted.

The run partitions the initial share history, performs several fresh sessions,
restarts one process, proves that a captured hello nonce is still rejected after
the restart, and requires all four validators to finish with the same accepted
share graph and selected tip.

This is stronger evidence than four loopback addresses, but it is still one
computer, one kernel, one GitHub runner, and one administrator. The two
"transport" values are configured labels carried over from the diversity
preflight; both use the same TCP stack. They are not evidence of independent
networks, organizations, jurisdictions, or anonymity routes.

## Frozen routed configuration

Each node configuration contains:

- one listener IP, port, and matching signed endpoint;
- one separately routed controller source used only by the laboratory harness;
- one private Ed25519 fixture seed and one local controller key;
- one operator-group and transport label;
- exactly three pinned peers, each with a route, public identity key, operator
  label, and transport label; and
- the unchanged v0 validator limits, v1 safety limits, a 30-second socket
  timeout, and a 128-entry transcript-commitment history.

The peer table contains no `shared_key_hex`. Every node sees peers in three
different IPv4 `/24` prefixes, three configured operator groups, and at least
two configured transport labels. The listener rejects a signed identity that
arrives from a source IP other than that peer's pinned route.

The 30-second timeout is deliberately longer than the five-second v0 fixture
timeout because the readable pure-Python Ed25519 implementation is slow on
some CI and Windows hosts. It is a frozen laboratory limit, not a recommendation
for production cryptography.

## Live session and restart boundary

The listener accounts for the source prefix and hello nonce before doing the
expensive signature check. It then verifies the pinned identity, network,
role, algorithms, operator label, transport label, endpoint, signature, and
hello lifetime. Accepted frames use the frozen v1 frame limit and message token
bucket. The process retains bounded admission buckets, replay nonces,
quarantines, rejection counters, observed prefixes, transcript commitments,
and accepted session/frame counts in an atomic sidecar file.

Live TCP connections cannot survive a process restart, so their active counters
reset to zero. Replay, rate, quarantine, and transcript evidence remains. The
test admits one fixed bravo-to-charlie hello, restarts charlie, repeats the same
hello from bravo's namespace, and requires the listener to reject it.

Application announcements are now Ed25519-signed before entering a live
session frame. A third party with the pinned public key can validate a captured
announcement. As before, conflicting signatures are portable evidence only;
they cause no consensus punishment, automatic slashing, payout change, or
claim about a real-world person.

## Deterministic retained evidence

On Linux with `iproute2` and root namespace permission, run:

```bash
sudo --preserve-env=PATH python3 \
  contrib/mining_autonomy/run_share_routed_namespace_lab.py \
  --output build/share-sync-routed-namespace-v1-evidence.json
```

The runner creates four temporary validator namespaces, one temporary router
namespace, four routed veth pairs, and one controller veth pair. IPv4
forwarding is enabled only inside that disposable router namespace. Four
narrow controller routes are installed for the run. Cleanup removes those
routes, interfaces, and all five namespaces without changing the host's global
forwarding setting. Evidence records stable checks and counts, not random
ephemeral keys, nonces, or wall-clock values, so its commitment is
reproducible. If the run fails, its error identifies the active phase (for
example topology setup, fixture seeding, synchronization, or replay testing)
instead of reporting only a generic socket timeout.

The retained checks require:

- four distinct non-loopback routed prefixes and four processes;
- no pairwise peer secret in any routed configuration;
- three operator labels and at least two transport labels in every peer set;
- delayed share delivery over the live boundary;
- a valid hello before restart and rejection of its replay after restart;
- persisted replay state;
- more than one transcript for repeated alpha-to-bravo sessions;
- authenticated frames observed across the routed namespaces;
- pinned source prefixes observed at the listeners;
- only portably signed application announcements in persisted peer state; and
- identical reference/independent validator state, selected tip, and complete
  five-share graph at all four processes.

CI runs this in the existing Ubuntu job and retains the JSON in the existing
mining-interoperability artifact. It adds no job or matrix.

## What this does not prove

This experiment does not prove independent operation, Sybil resistance,
permissionless discovery, honest operator labels, transport independence,
resistance to a hostile ISP or Internet route, anonymity, safe production key
distribution, constant-time cryptography, post-quantum authentication,
production payout settlement, a consensus rule, or a final proof of work.

Issue #73 and Template Autonomy remain **OPEN**. The
[four-operator kit v1](sharechain-operator-kit-v1.md) packages this boundary
without centralized field keys, but only a run by separately administered
machines and networks can supply the next evidence. Reviewed hybrid
post-quantum identity and key lifecycle, discovery/rotation evidence, and
adversarial route testing without a privileged seed or operator authority also
remain required.
