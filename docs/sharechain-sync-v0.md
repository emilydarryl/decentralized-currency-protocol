# Authenticated three-process share synchronization v0

Status: **working loopback private-lab experiment; not a public pool or production network**

## Plain-English summary

The earlier milestone gave two separate calculators the same linked notebook of
mining shares. They agreed on which pages were valid and which history won, but
the notebook was still only a file.

This milestone runs three separate notebook processes. Each knows the two
specific neighbors it is allowed to contact and has a different secret for
each connection. A process rejects a message if its authentication code is
wrong, its sequence number was already used, it is too large, or it tries to
fill more storage than the experiment permits.

The test deliberately separates the three processes, delivers pages late and
out of order, lets one neighbor relay only part of the history, restarts a
process, and reconnects them. All three eventually select the same history and
payout-accounting state. The test also preserves proof when one authenticated
neighbor announces two different states for the same slot.

This is progress from a file format to a real process boundary. It is not yet a
public decentralized pool. All processes run on one machine over loopback,
their peers and secrets are supplied in advance, and there is no defense
against an attacker creating many identities or surrounding a miner with
malicious peers.

## Protocol boundary

Every message is canonical ASCII JSON with these envelope fields:

| Field | Meaning |
| --- | --- |
| `format` | `soveroot-share-sync-labnet-v0` |
| `sender_id`, `recipient_id` | Exact pinned route |
| `sequence` | Strictly increasing per sender; repeated or older values fail |
| `payload` | Inventory, share push, response, announcement, or local control object |
| `mac_sha256` | HMAC-SHA256 over a domain-separated canonical envelope body |

The authentication domain is `soveroot/share-sync/auth/v0`. Each pair of lab
peers has a distinct 32-byte shared key. Local control uses a separate key and
is also restricted to loopback.

Pairwise HMAC proves that a holder of that pair's key created a message. It is
not public identity or non-repudiation: either endpoint knows the same secret,
so evidence cannot prove authorship to an unrelated third party. A future
public profile needs reviewed identity and session authentication, including a
post-quantum migration design, before equivocation evidence can be portable.

## Frozen resource limits

| Resource | Limit |
| --- | ---: |
| Complete framed message | 131,072 bytes |
| Shares in one message | 64 |
| Known accepted and orphan shares | 4,096 |
| Inventory identifiers in one page | 512 |
| Inventory pages | 8 |
| Pending unknown-parent shares | 16 |
| Orphan age | 64 deterministic processing ticks |
| Configured peers | 8 |
| Concurrent connections | 8 |
| Most recent remembered announcement slots per peer | 128 |
| Preserved equivocation records | 128 |
| Complete synchronization operations | 144 |

The daemon refuses configurations that change these values. Private-lab
listeners and peers must use `127.0.0.1` or `::1`.

## Synchronization behavior

1. A process reads the pinned peer's inventory in at most eight pages of 512
   identifiers, keeping every frame below the byte limit.
2. It pulls missing shares in batches of at most 64 and validates them.
3. It pushes shares the peer lacks in batches of at most 64.
4. It rereads the bounded inventory and fails unless both identifier sets agree
   within the 144-operation ceiling.
5. Unknown-parent shares enter the bounded orphan set. When a parent arrives,
   the process attempts deterministic promotion in sequence and share-id order.
6. Every accepted graph is evaluated by both `sharechain_v0.py` and the
   separately written `independent_sharechain_v0.py`. Disagreement fails closed.
7. Accepted shares, pending orphans, replay state, announcements, equivocation
   evidence, and rejection counters are atomically persisted for restart.

An announcement binds a processing slot to the selected-tip and state
commitments. Two different authenticated announcements from the same peer for
one slot are retained together with a canonical evidence commitment. The lab
does not treat that evidence as a consensus punishment or identity verdict.

## Adversarial experiment

`run_share_sync_lab.py` launches three independent Python processes named
`alpha`, `bravo`, and `charlie` and requires 13 checks to pass:

- delayed shares enter bounded orphan sets;
- partitioned state is observable rather than hidden;
- restart preserves pending state;
- selective relay creates observable temporary disagreement;
- all three processes converge after reconnection;
- reference and independent state calculations agree;
- conflicting authenticated announcements are preserved;
- replayed and unauthenticated messages are rejected;
- orphan flooding stops exactly at the frozen limit;
- deterministic orphan aging releases the bounded storage;
- an oversized frame is rejected; and
- hostile inputs do not change the canonical selected tip.

Run it with:

```bash
python3 contrib/mining_autonomy/run_share_sync_lab.py \
  --output build/share-sync-v0-evidence.json
```

Run all focused tests with:

```bash
python3 -m unittest discover -s test/mining_autonomy \
  -p 'test_sharechain_sync_v0.py' -v
```

CI executes the experiment inside the existing mining-autonomy step and
retains the committed evidence with the existing mining interoperability
artifact. No additional job or matrix is created.

## What this does not prove

The experiment does not provide:

- Internet peer discovery or permissionless membership;
- independent machines, operators, networks, or jurisdictions;
- Sybil, eclipse, routing, traffic-analysis, or denial-of-service resistance;
- publicly verifiable peer identity or portable equivocation proof;
- payout maturity, reorganization economics, or production settlement;
- anonymity for miners or payout identifiers;
- base-consensus enforcement;
- the final Soveroot proof of work; or
- a coin with monetary value.

## Next bounded step

The [multi-host safety profile v1](sharechain-multihost-v1.md) now freezes the
first preflight for that research step: classical signed ephemeral sessions,
explicit admission and rate policy, deterministic peer-diversity rules,
bounded long-partition catch-up, eclipse simulations, and portable signed
equivocation evidence. It derives v0 frame keys and reruns this experiment on
three distinct loopback prefixes.

It does not yet expose a listener beyond loopback or place the signed layer on
the live frame boundary. Routed namespaces, independent hosts and operators,
reviewed post-quantum hybrid authentication, safe identity-key distribution,
peer discovery/rotation, hostile Internet evidence, and production payout and
privacy rules remain later milestones under issue #73.
