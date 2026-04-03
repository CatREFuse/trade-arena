#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.ssh.trade-arena.local}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
SSH_SKILL_DIR="${SSH_SKILL_DIR:-$CODEX_HOME_DIR/skills/ssh-skill}"
DEPLOY_PUBKEY="${DEPLOY_PUBKEY:-$SSH_SKILL_DIR/scripts/deploy_pubkey.py}"
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
: "${TA_SSH_HOST:=121.41.193.199}"
: "${TA_SSH_USER:=root}"
: "${TA_SSH_KEY_NAME:=trade_arena_ops}"

KEY_DIR="${TA_SSH_KEY_DIR:-$HOME/.ssh}"
KEY_FILE="${TA_SSH_KEY_FILE:-$KEY_DIR/$TA_SSH_KEY_NAME}"
PUBKEY_FILE="${KEY_FILE}.pub"

mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"

if [[ ! -f "$DEPLOY_PUBKEY" ]]; then
  echo "ssh-skill deploy_pubkey.py not found: $DEPLOY_PUBKEY" >&2
  exit 1
fi

if ! command -v ssh-keygen >/dev/null 2>&1; then
  echo "ssh-keygen is required" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

if [[ ! -f "$KEY_FILE" ]]; then
  ssh-keygen -t ed25519 -f "$KEY_FILE" -N "" -C "${TA_SSH_ALIAS}@trade-arena"
fi

chmod 600 "$KEY_FILE"
chmod 644 "$PUBKEY_FILE"

python3 "$DEPLOY_PUBKEY" "$TA_SSH_ALIAS" --pubkey-file "$PUBKEY_FILE" --key-name "$TA_SSH_KEY_NAME"

python3 - "$SSH_CONFIG_PATH" "$TA_SSH_ALIAS" "$TA_SSH_KEY_NAME" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

config_path = Path(sys.argv[1]).expanduser()
alias = sys.argv[2]
key_name = sys.argv[3]
identity_line = f"    IdentityFile ~/.ssh/{key_name}\n"
extra_lines = [
    "    IdentitiesOnly yes\n",
    "    PreferredAuthentications publickey\n",
    "    ControlMaster auto\n",
    "    ControlPath ~/.ssh/cm-%C\n",
    "    ControlPersist 600\n",
    "    ServerAliveInterval 30\n",
    "    ServerAliveCountMax 3\n",
]

lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
host_line = f"Host {alias}"

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
    cleaned_comments = []
    for item in comment_block:
        stripped = item.strip()
        if stripped.startswith("# password:"):
            continue
        if stripped.startswith("# tags:"):
            tags = [tag.strip() for tag in stripped[7:].split(",") if tag.strip()]
            if "key-auth" not in tags:
                tags.append("key-auth")
            cleaned_comments.append(f"# tags: {','.join(tags)}\n")
            continue
        cleaned_comments.append(item)
    lines[start:idx] = cleaned_comments
    idx = start + len(cleaned_comments)

    end = idx + 1
    while end < len(lines):
        stripped = lines[end].strip()
        if stripped.startswith("Host ") and not stripped.startswith("Host *"):
            break
        if stripped.startswith("# ====="):
            break
        end += 1

    block = lines[idx:end]
    kept = []
    seen = {
        "identityfile": False,
        "identitiesonly": False,
        "preferredauthentications": False,
        "controlmaster": False,
        "controlpath": False,
        "controlpersist": False,
        "serveraliveinterval": False,
        "serveralivecountmax": False,
    }

    for item in block:
        stripped = item.strip()
        lower = stripped.lower()
        if lower.startswith("identityfile "):
            kept.append(identity_line)
            seen["identityfile"] = True
        elif lower.startswith("identitiesonly "):
            kept.append("    IdentitiesOnly yes\n")
            seen["identitiesonly"] = True
        elif lower.startswith("preferredauthentications "):
            kept.append("    PreferredAuthentications publickey\n")
            seen["preferredauthentications"] = True
        elif lower.startswith("controlmaster "):
            kept.append("    ControlMaster auto\n")
            seen["controlmaster"] = True
        elif lower.startswith("controlpath "):
            kept.append("    ControlPath ~/.ssh/cm-%C\n")
            seen["controlpath"] = True
        elif lower.startswith("controlpersist "):
            kept.append("    ControlPersist 600\n")
            seen["controlpersist"] = True
        elif lower.startswith("serveraliveinterval "):
            kept.append("    ServerAliveInterval 30\n")
            seen["serveraliveinterval"] = True
        elif lower.startswith("serveralivecountmax "):
            kept.append("    ServerAliveCountMax 3\n")
            seen["serveralivecountmax"] = True
        else:
            kept.append(item)

    if not seen["identityfile"]:
        kept.append(identity_line)
    mapping = [
        ("identitiesonly", extra_lines[0]),
        ("preferredauthentications", extra_lines[1]),
        ("controlmaster", extra_lines[2]),
        ("controlpath", extra_lines[3]),
        ("controlpersist", extra_lines[4]),
        ("serveraliveinterval", extra_lines[5]),
        ("serveralivecountmax", extra_lines[6]),
    ]
    for key, value in mapping:
        if not seen[key]:
            kept.append(value)

    lines[idx:end] = kept
    config_path.write_text("".join(lines), encoding="utf-8")
    break
else:
    raise SystemExit(f"Host alias not found in SSH config: {alias}")
PY

ssh -F "$SSH_CONFIG_PATH" -o BatchMode=yes "$TA_SSH_ALIAS" "hostname && whoami"

echo "Key auth bootstrap complete for ${TA_SSH_ALIAS}"
echo "Fast path: ssh -F \"$SSH_CONFIG_PATH\" \"$TA_SSH_ALIAS\" \"cd /etc/nginx/website/trade-arena && bash scripts/opsctl.sh status\""
