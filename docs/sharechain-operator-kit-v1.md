# Four-operator share synchronization kit v1

Status: **portable laboratory tooling; not a public pool, production service, or independent-host result by itself**

## What this adds

The routed namespace experiment proved that four validator processes could use
the signed v1 session boundary and converge across four routed address ranges.
All four still belonged to one administrator on one computer.

This kit packages that same frozen protocol so four separate operators can
prepare their own nodes without exchanging private identity seeds or controller
keys. Each operator creates:

- one owner-only private identity file;
- one self-signed public manifest containing the route, public key, operator
  label, and transport label; and
- one owner-only node configuration assembled from the other three public
  manifests.

The number four is deliberate. The frozen safety profile requires every node
to select three peers from three distinct source prefixes and configured
operator groups, with at least two transport labels. A three-node kit would
give each node only two peers and silently weaken that rule.

The kit also creates a deterministic delayed-delivery campaign and lets each
operator sign a final public snapshot. A collector accepts the result only if
all four signatures and manifests verify, every node reports a non-empty state,
all four reports bind the same campaign and source revision, and all four state
commitments, selected tips, accepted-share counts, and empty orphan sets match.

## Important security boundary

This is a research tool. The readable Ed25519/X25519 code is classical,
non-constant-time reference code. It is not reviewed production cryptography
and is not post-quantum. Do not use this kit for funds or expose it as a public
service.

A manifest signature proves that the holder of its private seed approved that
manifest. It does not prove the operator's legal identity, independence,
location, network ownership, or honesty. Operator and transport labels are
claims. Participants must compare manifest commitments through an independent
channel and separately document who controlled each host and route.

## Requirements

Each operator needs:

- a separate Linux host or separately administered virtual machine;
- Python 3.11 or newer;
- this exact repository revision;
- one stable unicast IP literal assigned to that host or its private overlay;
- TCP port `19444` reachable only by the other three experiment hosts; and
- a local loopback controller source, normally `127.0.0.1`.

Use four different IPv4 `/24` or IPv6 `/48` source prefixes. Use at least two
genuinely different transports if available. Giving one transport two names
does not create route diversity.

The commands below use `KIT` as shorthand:

```bash
KIT=contrib/mining_autonomy/operator_kit_v1.py
```

## Step 1: each operator creates only their own identity

Run one command on each host with that operator's values. Example for alpha:

```bash
python3 "$KIT" init \
  --directory operator-alpha \
  --node-id alpha \
  --host 10.221.1.2 \
  --port 19444 \
  --operator-group operator-alpha \
  --transport overlay-red
```

Repeat independently for bravo, charlie, and delta with distinct node IDs,
addresses, operator groups, and an honest transport label. The command refuses
to overwrite an existing identity.

Keep this directory private and backed up offline:

```text
operator-alpha/private/
```

Share only this file:

```text
operator-alpha/public/operator-manifest.json
```

Never send `operator-private.json`, `node-config.json`, `share-state.json`, or
`transport-state.json` to another operator.

## Step 2: compare and validate the four public manifests

After exchanging manifests through an authenticated channel, every operator
should run the same check:

```bash
python3 "$KIT" validate-manifests \
  --manifest alpha-manifest.json \
  --manifest bravo-manifest.json \
  --manifest charlie-manifest.json \
  --manifest delta-manifest.json
```

Compare the printed manifest-set commitment over a second communication
channel. Stop if any operator sees a different value. The check rejects altered
signatures, repeated identities or endpoints, fewer than four operators,
source-prefix concentration, operator-label concentration, and a transport
monoculture.

## Step 3: each operator assembles their private node configuration

Alpha supplies the other three manifests, never its own, as peer inputs:

```bash
python3 "$KIT" assemble \
  --directory operator-alpha \
  --peer-manifest bravo-manifest.json \
  --peer-manifest charlie-manifest.json \
  --peer-manifest delta-manifest.json
```

Bravo, charlie, and delta do the equivalent with their three peers. Assembly
revalidates the full four-manifest set and then passes the result through the
unchanged routed v1 configuration validator. It refuses to overwrite an
existing configuration.

## Step 4: start each node

Each operator runs:

```bash
python3 "$KIT" serve --directory operator-alpha
```

Use a service manager for a real multi-hour experiment, capture standard
output and error, and pin the source revision. The listener must not be exposed
beyond the four declared experiment routes.

From a second terminal on the same host:

```bash
python3 "$KIT" status --directory operator-alpha
```

The controller key stays local, and the listener accepts controller messages
only from the configured loopback source.

## Step 5: run the public convergence campaign

Generate the same public campaign once and publish the complete directory plus
its printed commitment:

```bash
python3 "$KIT" write-campaign --directory campaign-v1
```

Each operator imports only their initial file:

```bash
python3 "$KIT" import-shares --directory operator-alpha \
  --shares campaign-v1/alpha-initial.json
```

Bravo, charlie, and delta use their matching initial files. Then perform these
seven steps in order, with each command run by the named operator:

```bash
# alpha
python3 "$KIT" sync --directory operator-alpha --peer bravo
python3 "$KIT" import-shares --directory operator-alpha \
  --shares campaign-v1/alpha-step.json
python3 "$KIT" sync --directory operator-alpha --peer bravo

# bravo
python3 "$KIT" sync --directory operator-bravo --peer charlie

# charlie
python3 "$KIT" sync --directory operator-charlie --peer alpha

# delta
python3 "$KIT" sync --directory operator-delta --peer alpha

# alpha, so delta also records an inbound session
python3 "$KIT" sync --directory operator-alpha --peer delta
```

This sequence is an observable laboratory campaign, not a privileged network
coordinator. Any operator can independently inspect every public fixture and
repeat the run from clean state.

## Step 6: sign and compare final evidence

Agree on one ASCII run ID before starting. Each operator then exports a public
signed snapshot locally:

```bash
REVISION=$(git rev-parse HEAD)
python3 "$KIT" snapshot \
  --directory operator-alpha \
  --run-id four-host-2026-001 \
  --campaign campaign-v1/campaign.json \
  --source-revision "$REVISION" \
  --output alpha-evidence.json
```

Collect the four public evidence files and verify them:

```bash
python3 "$KIT" verify-evidence \
  --evidence alpha-evidence.json \
  --evidence bravo-evidence.json \
  --evidence charlie-evidence.json \
  --evidence delta-evidence.json \
  --output four-host-summary.json
```

The summary is accepted only when all reports name the same frozen campaign
commitment and 40-hex-character Git source revision, the four nodes report the
same non-empty validator state with no remaining orphans, and each recorded at
least one inbound authenticated session and frame.
Retain the manifests, campaign, four signed reports, summary, source revision,
host descriptions, route descriptions, command logs, and independent operator
attestations together.

## Fail-closed behavior

The kit deliberately refuses to continue when:

- an identity, manifest, configuration, campaign file, evidence file, or
  summary would be overwritten;
- a private file is group- or world-readable on POSIX;
- a public manifest was altered after signing;
- fewer or more than four manifests or evidence reports are supplied;
- identities, endpoints, operator groups, or source prefixes repeat;
- any three-peer view lacks the frozen transport diversity;
- local private and public identities disagree;
- the existing routed v1 validator rejects the assembled configuration;
- an evidence signature, manifest commitment, or run ID is inconsistent; or
- the four final validator states do not converge.

## What CI proves and what remains open

CI creates four deterministic packages, checks that no public manifest contains
a private seed or controller key, validates every assembled routed v1 config,
rejects a three-operator downgrade and altered manifest, and verifies four
signed converged reports while rejecting a signed divergent report.

CI still runs on one machine and generates all fixture identities in one
process. It sends no packet between independent hosts. Therefore it proves the
packaging and verification logic, not real operator independence, hostile
Internet safety, Sybil resistance, route diversity, anonymity, post-quantum
authentication, or production settlement. Issue #73 and the Template Autonomy
gate remain **OPEN** until genuinely separate operators run and review the
experiment and the remaining cryptographic and discovery work is completed.
