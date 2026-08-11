#!/usr/bin/env python3
# Copyright (c) 2026 The Decentralized Currency Protocol developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Exercise a two-node labnet through the built daemon and command-line client."""

from decimal import Decimal

from test_framework.test_framework import BitcoinTestFramework, SkipTest
from test_framework.util import (
    assert_equal,
    get_datadir_path,
)


class LabnetSmokeTest(BitcoinTestFramework):
    def set_test_params(self):
        self.chain = "labnet"
        self.num_nodes = 2
        self.setup_clean_chain = True
        # Keep wallet support available without importing inherited regtest WIFs.
        self.uses_wallet = None

    def skip_test_if_missing_module(self):
        if not self.is_wallet_compiled():
            raise SkipTest("wallet has not been compiled")
        self.skip_if_no_cli()

    def setup_chain(self):
        super().setup_chain()
        config_path = get_datadir_path(self.options.tmpdir, 0) / "bitcoin.conf"
        config_lines = config_path.read_text(encoding="utf-8").splitlines()
        assert_equal(config_lines[0], "chain=labnet")
        assert "labnet=1" not in config_lines
        assert "[labnet]" in config_lines

    def run_test(self):
        self.log.info("Confirm both command-line clients selected isolated labnet")
        for node in self.nodes:
            info = node.getblockchaininfo()
            assert_equal(info["chain"], "labnet")
            assert_equal(info["blocks"], 0)
            assert node.chain_path.name == "dcp-labnet"
            assert node.chain_path.is_dir()

        self.log.info("Confirm the nodes are connected only through the test's explicit link")
        self.wait_until(lambda: all(len(node.getpeerinfo()) == 1 for node in self.nodes))

        self.log.info("Create independent wallets and mine spendable labnet-only coins")
        self.nodes[0].createwallet("miner")
        self.nodes[1].createwallet("receiver")
        miner = self.nodes[0].get_wallet_rpc("miner")
        receiver = self.nodes[1].get_wallet_rpc("receiver")

        mining_address = miner.getnewaddress()
        receiving_address = receiver.getnewaddress()
        assert mining_address.startswith("dcprt1")
        assert receiving_address.startswith("dcprt1")

        self.generatetoaddress(self.nodes[0], 101, mining_address)
        assert_equal(self.nodes[0].getblockcount(), 101)
        assert_equal(self.nodes[1].getblockcount(), 101)

        self.log.info("Transfer one coin, relay it, mine it, and verify the receiver")
        txid = miner.sendtoaddress(receiving_address, Decimal("1"))
        self.sync_mempools()
        assert txid in self.nodes[1].getrawmempool()

        self.generatetoaddress(self.nodes[0], 1, mining_address)
        assert_equal(receiver.getbalance(), Decimal("1"))
        assert_equal(receiver.gettransaction(txid)["confirmations"], 1)


if __name__ == "__main__":
    LabnetSmokeTest(__file__).main()
