#!/usr/bin/env bash
# Copyright (c) 2026 The Soveroot developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.

set -euo pipefail

script_path="${BASH_SOURCE[0]}"
[[ "${script_path}" == */* ]] || script_path="./${script_path}"
SCRIPT_DIR="$(cd -- "${script_path%/*}" && pwd)"
SOURCE_DIR="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="${1:-${SOURCE_DIR}/build}"
OUTPUT_DIR="${2:-${BUILD_DIR}/labnet-kit-artifacts}"
SOVRD="${BUILD_DIR}/bin/sovrd"
SOVR_CLI="${BUILD_DIR}/bin/sovr-cli"
SV2_REFERENCE="${SOVEROOT_SV2_REFERENCE_BINARY:-${SOURCE_DIR}/contrib/mining_autonomy/sv2-reference/target/release/soveroot-sv2-reference}"
SV2_INDEPENDENT="${SOVEROOT_SV2_INDEPENDENT_BINARY:-${SOURCE_DIR}/contrib/mining_autonomy/sv2-independent-miner/target/release/soveroot-sv2-independent-miner}"

[[ -x "${SOVRD}" ]] || { printf 'Missing executable: %s\n' "${SOVRD}" >&2; exit 1; }
[[ -x "${SOVR_CLI}" ]] || { printf 'Missing executable: %s\n' "${SOVR_CLI}" >&2; exit 1; }
[[ -x "${SV2_REFERENCE}" ]] || { printf 'Missing executable: %s\n' "${SV2_REFERENCE}" >&2; exit 1; }
[[ -x "${SV2_INDEPENDENT}" ]] || { printf 'Missing executable: %s\n' "${SV2_INDEPENDENT}" >&2; exit 1; }

architecture="$(uname -m)"
[[ "${architecture}" == "x86_64" ]] || {
    printf 'Unsupported package architecture: %s (expected x86_64)\n' "${architecture}" >&2
    exit 1
}

commit="${GITHUB_SHA:-$(git -C "${SOURCE_DIR}" rev-parse HEAD)}"
short_commit="${commit:0:12}"
kit_name="soveroot-labnet-kit-linux-x86_64-${short_commit}"
archive="${OUTPUT_DIR}/${kit_name}.tar.gz"
checksum="${archive}.sha256"
temporary_root="$(mktemp -d)"
trap 'rm -rf -- "${temporary_root}"' EXIT
kit_root="${temporary_root}/${kit_name}"

mkdir -p -- "${kit_root}/bin" "${kit_root}/libexec" "${kit_root}/share/man/man1" "${OUTPUT_DIR}"
install -m 0755 "${SOVRD}" "${kit_root}/bin/sovrd"
install -m 0755 "${SOVR_CLI}" "${kit_root}/bin/sovr-cli"
install -m 0755 "${SCRIPT_DIR}/soveroot-labnet" "${kit_root}/soveroot-labnet"
install -m 0755 "${SOURCE_DIR}/contrib/mining_autonomy/autonomous_labnet_miner.py" "${kit_root}/libexec/autonomous_labnet_miner.py"
install -m 0755 "${SOURCE_DIR}/contrib/mining_autonomy/share_accounting_coordinator.py" "${kit_root}/libexec/share_accounting_coordinator.py"
install -m 0755 "${SV2_REFERENCE}" "${kit_root}/libexec/soveroot-sv2-reference"
install -m 0755 "${SV2_INDEPENDENT}" "${kit_root}/libexec/soveroot-sv2-independent-miner"
install -m 0755 "${SOURCE_DIR}/contrib/mining_autonomy/run_interoperability.py" "${kit_root}/libexec/run_interoperability.py"
install -m 0644 "${SOURCE_DIR}/contrib/mining_autonomy/vectors/sv2_interoperability_v0.json" "${kit_root}/libexec/sv2_interoperability_v0.json"
install -m 0644 "${SOURCE_DIR}/docs/labnet-kit.md" "${kit_root}/README.md"
install -m 0644 "${SOURCE_DIR}/docs/mining-autonomy-labnet.md" "${kit_root}/mining-autonomy-labnet.md"
install -m 0644 "${SOURCE_DIR}/doc/man/sovrd.1" "${kit_root}/share/man/man1/sovrd.1"
install -m 0644 "${SOURCE_DIR}/doc/man/sovr-cli.1" "${kit_root}/share/man/man1/sovr-cli.1"
install -m 0644 "${SOURCE_DIR}/COPYING" "${kit_root}/COPYING"

{
    printf 'Soveroot Labnet Kit\n'
    printf 'Commit: %s\n' "${commit}"
    printf 'Platform: Linux x86_64\n'
    printf 'Built by: %s\n' "${GITHUB_SERVER_URL:-local build}"
    printf 'Safety: development labnet only; coins have no monetary value\n'
} >"${kit_root}/BUILD-INFO.txt"

tar -C "${temporary_root}" -czf "${archive}" "${kit_name}"
(
    cd -- "${OUTPUT_DIR}"
    sha256sum "$(basename -- "${archive}")" >"$(basename -- "${checksum}")"
)

printf 'Created %s\n' "${archive}"
printf 'Created %s\n' "${checksum}"
