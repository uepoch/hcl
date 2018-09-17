#!/usr/bin/env bash
set -x
set -e

cd $(git rev-parse --show-toplevel)
source ./scripts/venv.sh

export PYTHON_OPTS="-d"

./scripts/pre-commit
