#!/usr/bin/env bash
set -x
set -e

cd $(git rev-parse --show-toplevel)
source ./scripts/venv.sh

./scripts/pre-commit
