#!/usr/bin/env bash
# User uninstall: removes the tray app and autostart entry.
# Leaves the root-level backend in place (run sudo ../uninstall.sh to remove that).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

echo "==> Killing any running instance"
pkill -f platform-profile-tray 2>/dev/null || true

echo "==> Removing tray app"
rm -f "$TRAY_BIN"

echo "==> Removing autostart entry"
rm -f "$TRAY_DESKTOP"

echo "==> Removing application menu entry"
rm -f "$TRAY_APPENTRY"

echo ""
echo "Done. (Backend still installed — run 'sudo ../uninstall.sh' to remove it too.)"
