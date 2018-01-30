#!/usr/bin/env bash

cd $(git rev-parse --show-toplevel)

mkdir -p .git/hooks
ln -sf ../../scripts/pre-commit .git/hooks/pre-commit
source scripts/venv.sh
