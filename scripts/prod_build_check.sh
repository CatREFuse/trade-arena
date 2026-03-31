#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[prod_build_check] ops doctor"
bash "$ROOT_DIR/scripts/opsctl.sh" doctor

echo "[prod_build_check] frontend build"
(
  cd "$ROOT_DIR/frontend"
  rm -rf .nuxt .output
  npm run build
)

echo "[prod_build_check] done"
