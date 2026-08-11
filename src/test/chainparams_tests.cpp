// Copyright (c) 2026 The Decentralized Currency Protocol developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or https://opensource.org/license/mit/.

#include <chainparamsbase.h>
#include <kernel/chainparams.h>
#include <uint256.h>
#include <util/chaintype.h>

#include <boost/test/unit_test.hpp>

#include <array>
#include <memory>
#include <vector>

BOOST_AUTO_TEST_SUITE(chainparams_tests)

BOOST_AUTO_TEST_CASE(labnet_identity_isolated_from_bitcoin)
{
    const auto labnet{CChainParams::LabNet({})};
    const auto mainnet{CChainParams::Main()};
    const auto testnet{CChainParams::TestNet()};
    const auto testnet4{CChainParams::TestNet4()};
    const auto signet{CChainParams::SigNet({})};
    const auto bitcoin_regtest{CChainParams::RegTest({})};
    const std::array<const CChainParams*, 5> inherited{
        mainnet.get(), testnet.get(), testnet4.get(), signet.get(), bitcoin_regtest.get()};

    BOOST_CHECK(labnet->GetChainType() == ChainType::LABNET);
    BOOST_CHECK_EQUAL(labnet->GetChainTypeString(), "labnet");
    BOOST_CHECK(ChainTypeFromString("labnet") == ChainType::LABNET);
    BOOST_CHECK_EQUAL(labnet->GetDefaultPort(), 29444);
    BOOST_CHECK_EQUAL(labnet->Bech32HRP(), "dcprt");
    const MessageStartChars expected_magic{0xd1, 0xf5, 0xf7, 0x1d};
    BOOST_CHECK(labnet->MessageStart() == expected_magic);
    BOOST_CHECK(labnet->GenesisBlock().GetHash() == uint256{"5e0a0388d08796f24641a42cdcf87c7dc786b15a2b33e50b52dfb16d080bc28f"});
    BOOST_CHECK(labnet->GenesisBlock().hashMerkleRoot == uint256{"6744cd92d9f1c63c0f74e4c38f907cf3a6c3a79874647a44240ff76e1b40a445"});
    BOOST_REQUIRE_EQUAL(labnet->GenesisBlock().vtx.size(), 1U);
    BOOST_REQUIRE_EQUAL(labnet->GenesisBlock().vtx[0]->vout.size(), 1U);
    BOOST_CHECK_EQUAL(labnet->GenesisBlock().vtx[0]->vout[0].nValue, 0);

    BOOST_CHECK(labnet->DNSSeeds().empty());
    BOOST_CHECK(labnet->FixedSeeds().empty());
    BOOST_CHECK(labnet->GetAvailableSnapshotHeights().empty());
    BOOST_CHECK(labnet->GetConsensus().nMinimumChainWork.IsNull());
    BOOST_CHECK(labnet->GetConsensus().defaultAssumeValid.IsNull());

    BOOST_CHECK(labnet->Base58Prefix(CChainParams::PUBKEY_ADDRESS) == std::vector<unsigned char>{9});
    BOOST_CHECK(labnet->Base58Prefix(CChainParams::SCRIPT_ADDRESS) == std::vector<unsigned char>{72});
    BOOST_CHECK(labnet->Base58Prefix(CChainParams::SECRET_KEY) == std::vector<unsigned char>{176});
    const std::vector<unsigned char> expected_ext_public{0xa4, 0x8a, 0xaf, 0x01};
    const std::vector<unsigned char> expected_ext_secret{0xd9, 0x2c, 0x57, 0x68};
    BOOST_CHECK(labnet->Base58Prefix(CChainParams::EXT_PUBLIC_KEY) == expected_ext_public);
    BOOST_CHECK(labnet->Base58Prefix(CChainParams::EXT_SECRET_KEY) == expected_ext_secret);

    for (const CChainParams* bitcoin : inherited) {
        BOOST_CHECK(labnet->MessageStart() != bitcoin->MessageStart());
        BOOST_CHECK(labnet->GetDefaultPort() != bitcoin->GetDefaultPort());
        BOOST_CHECK(labnet->GenesisBlock().GetHash() != bitcoin->GenesisBlock().GetHash());
        BOOST_CHECK(labnet->Bech32HRP() != bitcoin->Bech32HRP());
        for (int type = CChainParams::PUBKEY_ADDRESS; type < CChainParams::MAX_BASE58_TYPES; ++type) {
            const auto prefix_type{static_cast<CChainParams::Base58Type>(type)};
            BOOST_CHECK(labnet->Base58Prefix(prefix_type) != bitcoin->Base58Prefix(prefix_type));
        }
    }

    BOOST_CHECK(GetNetworkForMagic(labnet->MessageStart()) == ChainType::LABNET);
    BOOST_CHECK(GetNetworkForMagic(bitcoin_regtest->MessageStart()) == ChainType::REGTEST);

    const auto labnet_base{CreateBaseChainParams(ChainType::LABNET)};
    BOOST_CHECK_EQUAL(labnet_base->DataDir(), "dcp-labnet");
    BOOST_CHECK_EQUAL(labnet_base->RPCPort(), 29443);
}

BOOST_AUTO_TEST_SUITE_END()
