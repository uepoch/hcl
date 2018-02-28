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
    url="http://nexus.query.consul/service/local/repo_groups/criteo/content/com/github/hashicorp/vault"
    archive="vault-${vault_version}.tar.gz"
    if ! [ -f archive ]; then
        wget "${url}/${vault_version}/${archive}"
    fi
    tar xvf "${archive}"
fi
