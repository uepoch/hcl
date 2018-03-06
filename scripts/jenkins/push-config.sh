#!/usr/bin/env bash
set -e
set -x

cd $(git rev-parse --show-toplevel)
source ./scripts/venv.sh

if [ -n "$VAULT_ADDR" ]; then
    echo "Can't find VAULT_ADDR"
    exit 2
fi

if [ -n "$VAULT_TOKEN" ];then
    echo "Can't find VAULT_TOKEN in env"
# No secret ID needed for now.
    result=$(curl -XPOST -d '{"role_id": "criteo-jenkins", "secret_id": "'$JENKINS_VAULT_SECRET_ID'"}' "$VAULT_ADDR/v1/auth/approle/login" | jq -r '.auth.client_token')
    if [ -z "$result" ]; then
        echo "Didn't manage to get a vault token from Vault. Aborting"
        exit 2
    fi

    export VAULT_TOKEN="$result"
fi


if ! [ -d "./build" ];then
    echo "Testing and building configuration"
    ./scripts/pre-commit
fi

echo "Deploying configuration"
python app/main.py -v --no-build
echo "Deployed configuration"
