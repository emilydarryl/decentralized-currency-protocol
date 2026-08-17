# Pool-Protocol Research Tools

Everything in this directory is non-consensus research code. It is not used by `sovrd`, wallet software, block validation, or the official mining profile.

## XOR-key worker-withholding model

`xor_withholding_model.py` exhaustively enumerates a small leading-zero target model for the XOR-key idea reviewed in [`docs/xor-key-block-withholding-study.md`](../../docs/xor-key-block-withholding-study.md).

Run the model:

```shell
python contrib/pool_research/xor_withholding_model.py --width 12 --clear-bits 4 --block-bits 8
```

Run its focused tests:

```shell
python -m unittest discover -s test/pool_research -p "test_*.py"
```

The output is an idealized combinatorial check, not a cryptographic result or a production pool simulation. The model intentionally rejects widths above 20 because it enumerates every share and every hidden mask.
