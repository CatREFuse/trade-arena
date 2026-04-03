#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.ssh.trade-arena.local}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
SSH_SKILL_DIR="${SSH_SKILL_DIR:-$CODEX_HOME_DIR/skills/ssh-skill}"
SSH_MANAGER="${SSH_MANAGER:-$SSH_SKILL_DIR/scripts/ssh_config_manager_v3.py}"
SSH_CONFIG_PATH="${SSH_CONFIG_PATH:-$HOME/.ssh/config}"

if [[ -f "$ENV_FILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    [[ -z "$key" ]] && continue
    export "$key=$value"
  done <"$ENV_FILE"
fi

: "${TA_SSH_ALIAS:=trade-arena-prod}"
: "${TA_SSH_HOST:?TA_SSH_HOST is required}"
: "${TA_SSH_USER:?TA_SSH_USER is required}"
: "${TA_SSH_PASSWORD:?TA_SSH_PASSWORD is required}"
: "${TA_SSH_PORT:=22}"
: "${TA_SSH_ENVIRONMENT:=production}"
: "${TA_SSH_DESCRIPTION:=Trade Arena online ops server}"
: "${TA_SSH_TAGS:=trade-arena,ops,prod}"
: "${TA_SSH_LOCATION:=online-server}"

if [[ ! -f "$SSH_MANAGER" ]]; then
  echo "ssh-skill is not installed: $SSH_MANAGER" >&2
  echo "Expected path: ${CODEX_HOME_DIR}/skills/ssh-skill" >&2
  exit 1
fi

mkdir -p "$(dirname "$SSH_CONFIG_PATH")"
touch "$SSH_CONFIG_PATH"

IFS=',' read -r -a tag_array <<<"$TA_SSH_TAGS"

manager_cmd=(python3 "$SSH_MANAGER")
common_args=(--host "$TA_SSH_HOST" --user "$TA_SSH_USER" --port "$TA_SSH_PORT" --environment "$TA_SSH_ENVIRONMENT" --description "$TA_SSH_DESCRIPTION")

if [[ -n "$TA_SSH_LOCATION" ]]; then
  common_args+=(--location "$TA_SSH_LOCATION")
fi

if (( ${#tag_array[@]} > 0 )); then
  common_args+=(--tags)
  for tag in "${tag_array[@]}"; do
    trimmed="${tag#"${tag%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    if [[ -n "$trimmed" ]]; then
      common_args+=("$trimmed")
    fi
  done
fi

if rg -q "^Host[[:space:]]+${TA_SSH_ALIAS}$" "$SSH_CONFIG_PATH"; then
  "${manager_cmd[@]}" update "$TA_SSH_ALIAS" "${common_args[@]}"
else
  "${manager_cmd[@]}" create --alias "$TA_SSH_ALIAS" "${common_args[@]}"
fi

python3 - "$SSH_CONFIG_PATH" "$TA_SSH_ALIAS" "$TA_SSH_PASSWORD" <<'PY'
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

config_path = Path(sys.argv[1]).expanduser()
alias = sys.argv[2]
password = sys.argv[3]

lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
host_line = f"Host {alias}"
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for idx, line in enumerate(lines):
    if line.strip() != host_line:
        continue

    start = idx
    while start > 0:
        prev = lines[start - 1]
        if prev.strip() == "" or prev.lstrip().startswith("#"):
            start -= 1
            continue
        break

    comment_block = lines[start:idx]
    if not comment_block:
        comment_block = [f"\n# ===== {alias} =====\n"]

    updated = []
    has_password = False
    has_updated_at = False

    for item in comment_block:
        stripped = item.strip()
        if stripped.startswith("# password:"):
            updated.append(f"# password: {password}\n")
            has_password = True
            continue
        if stripped.startswith("# updated_at:"):
            updated.append(f"# updated_at: {now}\n")
            has_updated_at = True
            continue
        updated.append(item)

    if not has_password:
        insert_at = len(updated)
        for pos, item in enumerate(updated):
            if item.strip().startswith("# created_at:") or item.strip().startswith("# updated_at:"):
                insert_at = pos
                break
        updated.insert(insert_at, f"# password: {password}\n")

    if not has_updated_at:
        updated.append(f"# updated_at: {now}\n")

    lines[start:idx] = updated
    config_path.write_text("".join(lines), encoding="utf-8")
    break
else:
    raise SystemExit(f"Host alias not found in SSH config: {alias}")
PY

echo "SSH skill server alias is ready: ${TA_SSH_ALIAS}"
echo "Check config: python3 \"$SSH_MANAGER\" find \"$TA_SSH_ALIAS\""
echo "Example execute: python3 \"$SSH_SKILL_DIR/scripts/ssh_execute.py\" \"$TA_SSH_ALIAS\" \"hostname && whoami\""
