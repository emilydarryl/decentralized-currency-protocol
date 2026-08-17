# Non-Normative References

These sources informed the v0.1 working draft. Their inclusion does not import their rules into this protocol and does not imply endorsement of a particular implementation.

## Consensus and Bitcoin foundations

- Satoshi Nakamoto, [Bitcoin: A Peer-to-Peer Electronic Cash System](https://bitcoin.org/bitcoin.pdf).
- Bitcoin Core, [reference implementation repository](https://github.com/bitcoin/bitcoin).
- Bitcoin Knots, [implementation repository](https://github.com/bitcoinknots/bitcoin).
- Bitcoin Knots, [draft BLAKE2b proof-of-work hard fork and XOR-key withholding construction](https://github.com/bitcoinknots/bitcoin/pull/359), reviewed at commit [`4e683f13f45093fcdac52e4f4762999e44ab12e1`](https://github.com/bitcoinknots/bitcoin/commit/4e683f13f45093fcdac52e4f4762999e44ab12e1).
- Bitcoin Improvement Proposals repository, [BIP process and specifications](https://github.com/bitcoin/bips).
- Bitcoin BIP 9, [Version bits with timeout and delay](https://github.com/bitcoin/bips/blob/master/bip-0009.mediawiki).
- Bitcoin BIP 8, [Version bits with lock-in by height](https://github.com/bitcoin/bips/blob/master/bip-0008.mediawiki).

## Post-quantum cryptography

- NIST FIPS 202, [SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions](https://csrc.nist.gov/pubs/fips/202/final).
- NIST FIPS 203, [Module-Lattice-Based Key-Encapsulation Mechanism Standard (ML-KEM)](https://csrc.nist.gov/pubs/fips/203/final).
- NIST FIPS 204, [Module-Lattice-Based Digital Signature Standard (ML-DSA)](https://csrc.nist.gov/pubs/fips/204/final).
- NIST FIPS 205, [Stateless Hash-Based Digital Signature Standard (SLH-DSA)](https://csrc.nist.gov/pubs/fips/205/final).
- Bitcoin BIP 360, [Pay-to-Merkle-Root](https://github.com/bitcoin/bips/blob/master/bip-0360.mediawiki).
- Bitcoin BIP 361, [Post Quantum Migration and Legacy Signature Sunset](https://github.com/bitcoin/bips/blob/master/bip-0361.mediawiki).

## Peer and wallet privacy

- Bitcoin BIP 324, [Version 2 P2P Encrypted Transport Protocol](https://bips.dev/324/).
- Bitcoin BIP 330, [Transaction Announcements Reconciliation](https://bips.dev/330/).
- Bitcoin BIP 352, [Silent Payments](https://bips.dev/352/).
- Bitcoin BIP 77, [Async Payjoin](https://bips.dev/77/).
- Tor Project, [Onion Services overview](https://community.torproject.org/onion-services/overview/).
- Tor Project, [Arti embeddable Tor implementation](https://arti.torproject.org/about/).
- Fanti et al., [Dandelion++: Lightweight Cryptocurrency Networking with Formal Anonymity Guarantees](https://arxiv.org/abs/1805.11060).

## Mining decentralization

- Stratum V2, [Protocol overview](https://stratumprotocol.org/specification/03-protocol-overview/).
- Stratum V2, [Mining Protocol](https://stratumprotocol.org/specification/05-mining-protocol/).
- Stratum V2, [Job Declaration Protocol](https://stratumprotocol.org/specification/06-job-declaration-protocol/).
- Miller, Kosba, Katz, and Shi, [Nonoutsourceable Scratch-Off Puzzles to Discourage Bitcoin Mining Coalitions](https://www.cs.umd.edu/~jkatz/papers/nonoutsourceable.pdf).
- Luu et al., [SmartPool: Practical Decentralized Pooled Mining](https://eprint.iacr.org/2017/019.pdf).

## State and private validation research

- Bitcoin Optech, [Utreexo topic index](https://bitcoinops.org/en/topics/utreexo/).
- Ben-Sasson et al., [Scalable, Transparent, and Post-Quantum Secure Computational Integrity](https://starkware.co/wp-content/uploads/2022/05/STARK-paper.pdf).

## Optional delegated-agent payment patterns

- Agent Payments Protocol, [AP2 specification](https://ap2-protocol.org/ap2/specification/).
- x402 Foundation, [x402 protocol specification repository](https://github.com/x402-foundation/x402).

## Reference policy

Before a protocol freeze, each cryptographic reference MUST be rechecked for revisions, errata, parameter changes, and newly published attacks. Drift-prone external specifications must be pinned by version and content hash in the eventual implementation repository.

