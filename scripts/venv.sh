#!/usr/bin/env bash

VENV="${PWD}/venv"
VENV_BIN="${VENV}/bin"

if [[ ! -n ${VIRTUAL_ENV} ]]; then
    if [[ ! -e ${VENV_BIN}/activate ]]; then
        virtualenv -q -p python3 --prompt="(vault-configuration) " ${VENV}
    fi

    source ${VENV_BIN}/activate

    pip install -q --upgrade pip
    pip install -q --upgrade setuptools
    pip install -e .
fi
