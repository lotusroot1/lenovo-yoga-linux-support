#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

echo "==> Killing any running instance"
pkill -f kbd-backlight-tray 2>/dev/null || true

echo "==> Removing tray app"
rm -f "$TRAY_BIN"

echo "==> Removing autostart entry"
rm -f "$TRAY_DESKTOP"

echo "==> Removing application menu entry"
rm -f "$TRAY_APPENTRY"

echo "Done."
