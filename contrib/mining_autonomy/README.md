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
```

This prototype is evidence for one narrow property: a miner can construct and
publish a labnet block without a pool coordinator. The second command uses
`share_accounting_coordinator.py` to record verified work, kills it, and proves
the miner continues. The third command uses the pinned Stratum V2 reference
helper for authenticated Job Declaration and then proves coordinator loss
cannot stop the miner. It is not independent interoperability, decentralized
accounting, a payout protocol, the experimental Soveroot PoW, or production
software.

The authenticated protocol boundary is frozen in
[`docs/stratum-v2-job-declaration-labnet-profile-v0.md`](../../docs/stratum-v2-job-declaration-labnet-profile-v0.md).
`sv2_job_declaration_vectors.py` generates and validates nine semantic
transcripts. The Rust helper in `sv2-reference/` now implements the pinned
Noise and binary Job Declaration/custom-job path, while the same Python miner
keeps template construction, solving, and direct publication. The packaged
demo kills the authenticated coordinator between two blocks and requires the
same miner process to continue in direct fallback. This is one reference path,
not independent interoperability or a payout protocol.

```bash
python3 contrib/mining_autonomy/sv2_job_declaration_vectors.py --check
```
