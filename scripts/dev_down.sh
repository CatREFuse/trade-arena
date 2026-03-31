#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

STOP_DOCKER="${STOP_DOCKER:-0}" \
bash "$ROOT_DIR/scripts/service_ctl.sh" stop
