#!/usr/bin/env bash

TMPDIR="./tmp"

cd $(git rev-parse --show-toplevel)

vault_version="$(cat ./VAULT_VERSION | tr -d '\n')"

if ! [ -d "$TMPDIR" ]; then
    mkdir -p "$TMPDIR"
fi
cd "$TMPDIR"


if command -v vault > /dev/null && [ "$(vault version | awk '{print $2}')" == "v${vault_version}" ]; then
    if ! [ -e "./vault" ]; then
        ln -s $(command -v vault) ./vault
    fi

elif ! [ -x "./vault" ] || ! [ "$(./vault version | awk '{print $2}')" == "v${vault_version}" ]; then
    ARCH="386"
    if [ "$(getconf LONG_BIT)" -eq 64 ]; then
        ARCH="amd64"
    fi
    OS="linux"
    if [ "$(uname -s)" == "Darwin" ]; then
        OS="darwin"
    fi
    ARCHIVE_NAME="vault_${vault_version}_${OS}_${ARCH}.zip"
    url="https://releases.hashicorp.com/vault/${vault_version}/${ARCHIVE_NAME}"
    if ! [ -f archive ]; then
        wget "${url}"
    fi
    unzip -o "./${ARCHIVE_NAME}"
    chmod +x ./vault
fi
