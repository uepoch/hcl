#!/usr/bin/env bash

# helper

start_vault() {
  local addr="$1"
  if [[ ! -e ./vault ]] || [[ ! -x ./vault ]]; then
    >&2 echo "ERROR: ./vault doesn't exist or isn't executable!"
    exit 1
  fi
  if [[ -e ./vault.pid ]]; then
    >&2 echo -n "ERROR: ./vault.pid exists, "
    >&2 echo "it seems that vault instance is already running!"
    exit 1
  fi
  nohup \
  ./vault server -dev -dev-listen-address="${addr}" -log-level=trace \
  > vault.log 2>&1 &
  echo $! > vault.pid
  chmod 400 vault.pid
  if [[ -e "${HOME}/.vault-token" ]]; then
    >&2 echo "ERROR: please ~/.vault-token already exists,"
    >&2 echo "clean that before starting vault in dev mode!"
    exit 1
  fi
  until mv "${HOME}/.vault-token" ./vault.token &> /dev/null; do
    echo "waiting for vault token..."
    sleep 1
  done
  chmod 400 vault.token
  local vault_token="$(cat ./vault.token)"
  echo "${addr}" > vault.addr
  local pid="$(cat ./vault.pid)"
  until VAULT_ADDR="http://${addr}" ./vault status; do
    >&2 echo "vault server is inaccessible!"
  done
  echo "vault pid: ${pid} started at ${addr}, see vault.log."
  echo "vault token: ${vault_token}"
}

stop_vault() {
  if [[ ! -e ./vault.pid ]] || [[ ! -r ./vault.pid ]]; then
    >&2 echo -n "ERROR: ./vault.pid doesn't exist or isn't readable, "
    >&2 echo "it seems that vault instance is not running!"
    exit 1
  fi
  local pid="$(cat ./vault.pid)"
  local addr="$(cat ./vault.addr)"
  kill "$pid" && \
  rm -f vault.*
  echo "vault pid:$pid from ${addr} is stopped!"
}

status_vault() {
  if [[ ! -e ./vault.pid ]]; then
    echo "vault stopped."
    return 1
  fi
  local pid="$(cat ./vault.pid)"
  local addr="$(cat ./vault.addr)"
  echo "vault running pid:$pid at $addr, see vault.log..."
}

# main

cd $(git rev-parse --show-toplevel)
cd ./tmp

case $1 in
start)
  ip=127.0.0.1
  port=32768
  addr=${ip}:${port}
  # find free port
  until start_vault ${addr}; do
    >&2 echo "Impossible to start vault in dev mode, ${addr} occupied!"
    ((port++))
    addr=${ip}:${port}
  done
  ;;
stop)
  stop_vault
  ;;
status)
  status_vault
  ;;
*)
  >&2 echo "ERROR: bad argument $1, possible values start, stop or status!"
  exit 1
esac


