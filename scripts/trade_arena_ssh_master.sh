#!/usr/bin/env bash
set -euo pipefail

SSH_CONFIG_PATH="${SSH_CONFIG_PATH:-$HOME/.ssh/config}"
TA_SSH_ALIAS="${TA_SSH_ALIAS:-trade-arena-prod}"

action="${1:-status}"

case "$action" in
  start)
    if ssh -F "$SSH_CONFIG_PATH" -O check "$TA_SSH_ALIAS" >/dev/null 2>&1; then
      echo "master connection already running for $TA_SSH_ALIAS"
      exit 0
    fi
    ssh -F "$SSH_CONFIG_PATH" -o BatchMode=yes -MNf "$TA_SSH_ALIAS"
    echo "master connection started for $TA_SSH_ALIAS"
    ;;
  stop)
    ssh -F "$SSH_CONFIG_PATH" -O exit "$TA_SSH_ALIAS"
    ;;
  status)
    ssh -F "$SSH_CONFIG_PATH" -O check "$TA_SSH_ALIAS"
    ;;
  *)
    echo "usage: bash scripts/trade_arena_ssh_master.sh {start|stop|status}" >&2
    exit 1
    ;;
esac
