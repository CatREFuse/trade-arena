#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRANCH="${1:-}"

if [[ -z "$BRANCH" ]]; then
  echo "[webhook/deploy] Error: missing branch argument" >&2
  exit 1
fi

exec /bin/bash "$ROOT_DIR/scripts/opsctl.sh" deploy --branch "$BRANCH"
