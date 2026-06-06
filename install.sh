#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "${BIN_DIR:-}" ]; then
  if [ -d /opt/homebrew/bin ]; then
    BIN_DIR="/opt/homebrew/bin"
  else
    BIN_DIR="/usr/local/bin"
  fi
fi

mkdir -p "$BIN_DIR"
ln -sf "$ROOT_DIR/4saves" "$BIN_DIR/4saves"

echo "4Saves installed."
echo "Run it with: 4saves"
