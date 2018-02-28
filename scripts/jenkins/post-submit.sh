#!/usr/bin/env bash

cd $(git rev-parse --show-toplevel)

./scripts/pre-commit

# TODO: deploy policies on vault server according to environment