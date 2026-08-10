# Upstream Source Register

Status: Normative development-process record
Last reviewed: 2026-08-10

This project is a code fork, not a fork of Bitcoin's live chain. Upstream repositories are read-only sources. Their push URLs are deliberately disabled in the maintained local configuration.

## Primary baseline: Bitcoin Core

- Repository: `https://github.com/bitcoin/bitcoin.git`
- Local remote: `upstream-core`
- Release: `v31.0`
- Annotated tag object: `84b62e1e8dbc9bbb393d0cb50c863b161b378f35`
- Dereferenced commit: `6574cb40869b96b9ffc79c19dc8f4e467d60f321`
- Imported as an unmodified source baseline before project-specific consensus work

The commit hash was resolved independently from the official Git repository. Local GPG verification remains release-blocking until the Bitcoin Core signer keyring is installed and verified through a documented trust path.

## Patch source: Bitcoin Knots

- Repository: `https://github.com/bitcoinknots/bitcoin.git`
- Local remote: `upstream-knots`
- Observed default branch: `29.x-knots`
- Observed commit: `2d531eaf4b0801278b3e928cf9df3b3852001d0a`
- Role: candidate patch source only

No Knots branch is merged wholesale. Each candidate patch requires an entry in [patch-provenance.md](patch-provenance.md), a consensus-versus-policy classification, compatibility review against the Core baseline, and focused tests.

## Update rules

1. Never follow an upstream moving branch in production builds.
2. Record immutable tag and commit identifiers before review begins.
3. Verify upstream release signatures and reproducible-build attestations before release use.
4. Review consensus diffs separately from wallet, node-policy, GUI, build, and test changes.
5. Import upstream changes only on a dedicated branch with the full inherited test suite.
6. Never push to either upstream remote from project automation.
