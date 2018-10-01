#!/usr/bin/env bash
#
# usage: ./tests.sh [-iv]

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

INTERACTIVE=0
PYTHON_OPTS="${PYTHON_OPTS}"


cd $(git rev-parse --show-toplevel)

usage()
{
    echo >&2 "Usage: $0 -[iv]"
    echo >&2 "  -i      Interactive mode: Keep the vault server up"
    echo >&2 "  -v      Verbose mode: Activate debug output"
    echo >&2 "Usage: tests.sh -i -v"
    exit 1
}

while getopts ":iv" option; do
    case "${option}" in
        i)
            INTERACTIVE=1
            ;;
        v)
            PYTHON_OPTS="$PYTHON_OPTS -d"
            ;;
        *)
            usage
            ;;
    esac
done

. ./bootstrap.sh

trap exit_status EXIT

set -e

echo "*** INFO: Test vault configurations ***"

if ./scripts/vault.sh status ; then
        ./scripts/vault.sh stop
fi
./scripts/vault.sh start

export VAULT_ADDR="http://$(cat ./tmp/vault.addr)"
export VAULT_TOKEN="$(cat ./scripts/vault-dev-token.txt)"


echo "*** INFO: first execution, to provision vault server ***"
python ./app/main.py $PYTHON_OPTS

echo "*** INFO: Another execution. ***"
python ./app/main.py $PYTHON_OPTS


if [[ "${INTERACTIVE}" -eq 0 ]]; then
  ./scripts/vault.sh stop
else
  echo "Interactive tests with local vault in dev mode (storage in memory), execute that:"
  echo "  export VAULT_ADDR=http://$(cat ./tmp/vault.addr)"
  echo "Log in as root user by executing that:"
  echo "  export VAULT_TOKEN=$(cat ./scripts/vault-dev-token.txt)"
  echo "or test connection with (unset VAULT_TOKEN before):"
  echo "  vault auth -method=ldap username=<criteo_login>"
fi

tox -e lint
