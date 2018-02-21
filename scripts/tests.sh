#!/usr/bin/env bash
#
# usage: ./tests.sh [--interactive]
#  if --interactive is precised doesn't stop vault server.

# helper

exit_status() {
    exit_status=$?
    if [[ $exit_status -gt 0 ]]; then
        if ./scripts/vault.sh status &> /dev/null ; then
            ./scripts/vault.sh stop
        fi
        echo "ERROR: tests failed!"
        exit $exit_status
    fi
}

# main

cd $(git rev-parse --show-toplevel)

is_interactive=$1

. ./bootstrap.sh

trap exit_status EXIT

set -e
set -x

echo "*** INFO: Test vault configurations ***"

if ./scripts/vault.sh status ; then
        ./scripts/vault.sh stop
fi
./scripts/vault.sh start

export VAULT_ADDR="http://$(cat ./tmp/vault.addr)"
export VAULT_TOKEN="$(cat ./scripts/vault-dev-token.txt)"


echo "*** INFO: first execution, to provision vault server ***"
python ./app/main.py

echo "*** INFO: second execution, to verify that configuration overload works ***"

python ./app/main.py

if [[ "${is_interactive}" != "--interactive" ]]; then
  ./scripts/vault.sh stop
else
  echo "Interactive tests with local vault in dev mode (storage in memory), execute that:"
  echo "  export VAULT_ADDR=http://$(cat ./tmp/vault.addr)"
  echo "Log in as root user by executing that:"
  echo "  export VAULT_TOKEN=$(cat ./scripts/vault-dev-token.txt)"
  echo "or test connection with (unset VAULT_TOKEN before):"
  echo "  vault auth -method=ldap username=<criteo_login>"
fi
