# Labnet mining-autonomy prototype

`autonomous_labnet_miner.py` is a deliberately small external miner for the
isolated Soveroot labnet. It obtains a template from the miner's own node,
constructs the coinbase and block outside the daemon, performs inherited
labnet SHA256d proof of work locally, and submits the result directly.

It is packaged by the Labnet Kit and is normally run through:

```bash
./soveroot-labnet autonomy-demo
./soveroot-labnet coordinator-failure-demo
```

This prototype is evidence for one narrow property: a miner can construct and
publish a labnet block without a pool coordinator. The second command uses
`share_accounting_coordinator.py` to record verified work, kills it, and proves
the miner continues. It is not Stratum V2, decentralized accounting, a payout
protocol, the experimental Soveroot PoW, or production software.

The next protocol boundary is frozen in
[`docs/stratum-v2-job-declaration-labnet-profile-v0.md`](../../docs/stratum-v2-job-declaration-labnet-profile-v0.md).
`sv2_job_declaration_vectors.py` generates and validates nine semantic
transcripts for an accepted custom job and every required fail-closed direct
fallback. These are state-machine fixtures, not Noise ciphertext vectors or a
network implementation.

```bash
python3 contrib/mining_autonomy/sv2_job_declaration_vectors.py --check
```
