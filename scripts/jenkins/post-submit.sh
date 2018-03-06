#!/usr/bin/env bash
set -e
set -x

cd $(git rev-parse --show-toplevel)
source ./scripts/venv.sh

./scripts/pre-commit

# TODO: deploy policies on vault server according to environment