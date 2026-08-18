# Labnet mining-autonomy prototype

`autonomous_labnet_miner.py` is a deliberately small external miner for the
isolated Soveroot labnet. It obtains a template from the miner's own node,
constructs the coinbase and block outside the daemon, performs inherited
labnet SHA256d proof of work locally, and submits the result directly.

It is packaged by the Labnet Kit and is normally run through:

```bash
./soveroot-labnet autonomy-demo
./soveroot-labnet coordinator-failure-demo
./soveroot-labnet job-declaration-demo
./soveroot-labnet interoperability-demo
./soveroot-labnet resilience-demo
./soveroot-labnet share-settlement-demo
```

This prototype is evidence for one narrow property: a miner can construct and
publish a labnet block without a pool coordinator. The second command uses
`share_accounting_coordinator.py` to record verified work, kills it, and proves
the miner continues. The third command uses the pinned Stratum V2 reference
helper for authenticated Job Declaration and then proves coordinator loss
cannot stop the miner. The fourth command compares that reference path with a
separately written Rust miner, then requires each implementation to declare,
solve, and directly publish its own block. The sixth command reconciles two
locally stored receipt sets through one outage, requires identical payout
plans, and places the agreed outputs directly in coinbase. It is not a global
sharechain, the experimental Soveroot PoW, or production software.

`sharechain_v0.py` now freezes an offline P2Pool-like share format, fixed share
target, accumulated-work fork choice, two-share finality depth, four-share
payout window, and 15 accepted or rejected histories. The separately written
`independent_sharechain_v0.py` imports no reference code and must reach the
same result for every case. This is a file-based private-lab conformance gate,
not peer synchronization or a public pool. See
[`docs/sharechain-v0.md`](../../docs/sharechain-v0.md).

The authenticated protocol boundary is frozen in
[`docs/stratum-v2-job-declaration-labnet-profile-v0.md`](../../docs/stratum-v2-job-declaration-labnet-profile-v0.md).
`sv2_job_declaration_vectors.py` generates and validates nine semantic
transcripts. The Rust helper in `sv2-reference/` now implements the pinned
Noise and binary Job Declaration/custom-job path, while the same Python miner
keeps template construction, solving, and direct publication. The packaged
demo kills the authenticated coordinator between two blocks and requires the
same miner process to continue in direct fallback.

The standalone `sv2-independent-miner/` crate manually encodes and parses the
supported message payloads and independently builds the coinbase, merkle tree,
header, proof, and block. `run_interoperability.py` hard-fails if it disagrees
with the reference path on authentication inputs, wire bytes, negative cases,
the template commitment, or the complete solved block. See
[`docs/mining-interoperability-labnet.md`](../../docs/mining-interoperability-labnet.md)
for the exact independence boundary and limitations.

The fifth command keeps one miner process alive through an accepted primary
job, rejection, disconnect, stall, malformed state, downgrade, alternate
coordinator failover, and final total coordinator loss. The accounting service
binds verified receipts to miner-wallet payout scripts and emits deterministic
claims without holding a key or publishing a block. See
[`docs/noncustodial-payout-failover-labnet.md`](../../docs/noncustodial-payout-failover-labnet.md).

The sixth command uses `share_replica_client.py` to reconcile two independently
stored v2 receipt ledgers. `build_share_settlement_evidence.py` then checks the
recovery result, both canonical plans, the miner's commitment events, and the
decoded settlement coinbase. See
[`docs/replicated-share-settlement-labnet.md`](../../docs/replicated-share-settlement-labnet.md).

```bash
python3 contrib/mining_autonomy/sv2_job_declaration_vectors.py --check
python3 contrib/mining_autonomy/sharechain_v0.py --check
python3 contrib/mining_autonomy/independent_sharechain_v0.py --check
```
