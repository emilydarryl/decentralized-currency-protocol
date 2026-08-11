# Inherited-Assumptions Register

Status: Release-blocking checklist
Baseline: Bitcoin Core v31.0 at `6574cb40869b96b9ffc79c19dc8f4e467d60f321`

Every item begins **Unresolved**. A code change is not complete merely because a constant was renamed. Closure requires implementation evidence and negative cross-network tests.

| Area | Inherited Bitcoin behavior | Required project disposition | Status |
| --- | --- | --- | --- |
| Genesis | Bitcoin network genesis blocks and hashes | Generate a new genesis using the committed fair-launch procedure | Labnet resolved with a zero-value laboratory genesis; public genesis unresolved |
| Chain identity | Bitcoin chain parameter selection | Add unique project mainnet, testnet, signet-equivalent, and laboratory identities | Labnet v1 implemented; public identities unresolved |
| Message magic | Bitcoin P2P start bytes | Replace for every project network and test cross-rejection | Labnet v1 implemented and cross-checked; public networks unresolved |
| Ports | Bitcoin P2P and RPC defaults | Allocate unique defaults and test that no Bitcoin endpoint is contacted | Provisional labnet P2P/RPC defaults implemented; public allocation unresolved |
| Seeds | Bitcoin DNS and fixed seeds | Remove all inherited seeds; add only independently operated project seeds after testnet | Labnet has no DNS or fixed seeds; public discovery unresolved |
| Addresses | Base58, Bech32, Bech32m, and extended-key namespaces | Define unique human-readable prefixes and version bytes | Transitional labnet namespace implemented; post-quantum public format unresolved |
| Signatures | secp256k1 transaction authorization and Bitcoin sighash domains | Introduce versioned post-quantum programs and chain-specific domains; sunset classical-only authorization | Unresolved |
| Hashes | SHA-256-based identifiers and commitments | Inventory every hash call and assign retain, replace, or compatibility-only disposition | Unresolved |
| Proof of work | Bitcoin double-SHA-256 PoW | Replace with the reviewed chain-specific PoW construction | Unresolved |
| Difficulty | Bitcoin network adjustment rules | Specify and simulate the selected continuous adjustment | Unresolved |
| Issuance | Bitcoin subsidy, halvings, cap, and maturity | Implement the approved decline schedule and deterministic tail emission | Unresolved |
| Checkpoints | Checkpoints, assumed-valid block, minimum chain work | Remove inherited values; prohibit permanent post-genesis trust anchors | Labnet inherited snapshots removed and trust values zeroed; public policy unresolved |
| Data paths | Bitcoin directories, files, cookies, sockets, and process names | Allocate project-specific names and migration-safe paths | Labnet network directory isolated as `dcp-labnet`; base application paths unresolved |
| URI and MIME | `bitcoin:` and Bitcoin handler registrations | Define project-specific schemes without claiming Bitcoin compatibility | Unresolved |
| Signed messages | Bitcoin message-signing prefix and BIP322 contexts | Define chain-specific post-quantum message domains | Unresolved |
| Wallet broadcast | Direct Bitcoin P2P submission paths | Route official-wallet origin traffic only through the fail-closed privacy broadcaster | Unresolved |
| Mining RPC | Bitcoin template and legacy pool assumptions | Add miner-created jobs, direct publication, and the required Stratum V2 profile | Unresolved |
| Branding | Bitcoin names, icons, translations, help text, and package identifiers | Replace user-facing identity while preserving copyright attribution | Unresolved |
| Builds | Bitcoin package names, signing, update, and reproducibility processes | Establish independent reproducible artifacts with no privileged updater | Unresolved |
| Tests | Bitcoin-valid fixtures and network assumptions | Preserve upstream regression coverage and add project plus cross-network rejection vectors | Unresolved |

## Closure evidence

Each resolved row must link to:

- the specification section controlling the change;
- implementation commit or pull request;
- unit and functional test names;
- negative Bitcoin/project interoperability tests;
- benchmark or simulation evidence where applicable; and
- reviewer sign-off identifying consensus impact.
