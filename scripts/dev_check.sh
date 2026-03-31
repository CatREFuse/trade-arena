#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_PYTEST="${RUN_PYTEST:-0}"
RUN_REGRESSION="${RUN_REGRESSION:-0}"
BASE_URL="${BASE_URL:-http://127.0.0.1:3000}"

echo "[dev_check] service status"
bash "$ROOT_DIR/scripts/service_ctl.sh" status

echo "[dev_check] dev self-check"
bash "$ROOT_DIR/scripts/dev_self_check.sh"

if [[ "$RUN_PYTEST" == "1" ]]; then
  echo "[dev_check] backend pytest"
  (
    cd "$ROOT_DIR/backend"
    pytest -q
  )
fi

if [[ "$RUN_REGRESSION" == "1" ]]; then
  echo "[dev_check] online regression"
  RUN_REGISTER=0 BASE_URL="$BASE_URL" bash "$ROOT_DIR/scripts/online_regression.sh"
fi
