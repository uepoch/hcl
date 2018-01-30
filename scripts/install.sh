#!/usr/bin/env bash

cd $(git rev-parse --show-toplevel)
mkdir -p ./tmp
cd ./tmp

vault_version="$(cat ../VAULT_VERSION | tr -d '\n')"
url="http://nexus.query.consul/service/local/repo_groups/criteo/content/com/github/hashicorp/vault"
archive="vault-${vault_version}.tar.gz"
wget "${url}/${vault_version}/${archive}"
tar xvf "${archive}"