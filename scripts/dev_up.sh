#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE=dev \
START_DOCKER="${START_DOCKER:-1}" \
BUILD_FRONTEND=0 \
PREPARE_BACKEND="${PREPARE_BACKEND:-0}" \
PREPARE_FRONTEND="${PREPARE_FRONTEND:-0}" \
bash "$ROOT_DIR/scripts/service_ctl.sh" start
