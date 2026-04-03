#!/usr/bin/env bash
set -euo pipefail

SSH_CONFIG_PATH="${SSH_CONFIG_PATH:-$HOME/.ssh/config}"
TA_SSH_ALIAS="${TA_SSH_ALIAS:-trade-arena-prod}"

if [[ $# -eq 0 ]]; then
  echo "usage: bash scripts/trade_arena_ssh.sh '<remote command>'" >&2
  exit 1
fi

ssh -F "$SSH_CONFIG_PATH" -o BatchMode=yes "$TA_SSH_ALIAS" "$*"
