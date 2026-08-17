# Labnet mining-autonomy prototype

`autonomous_labnet_miner.py` is a deliberately small external miner for the
isolated Soveroot labnet. It obtains a template from the miner's own node,
constructs the coinbase and block outside the daemon, performs inherited
labnet SHA256d proof of work locally, and submits the result directly.

It is packaged by the Labnet Kit and is normally run through:

```bash
./soveroot-labnet autonomy-demo
```

This prototype is evidence for one narrow property: a miner can construct and
publish a labnet block without a pool coordinator. It is not Stratum V2, a
share-accounting service, a payout protocol, the experimental Soveroot PoW, or
production software.
