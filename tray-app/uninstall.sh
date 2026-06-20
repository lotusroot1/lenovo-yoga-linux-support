#!/usr/bin/env bash
# User uninstall: removes the Yoga tray app and autostart entry.
set -euo pipefail

TRAY_BIN="$HOME/.local/bin/yoga-tray"
TRAY_DESKTOP="$HOME/.config/autostart/yoga-tray.desktop"
TRAY_APPENTRY="$HOME/.local/share/applications/yoga-tray.desktop"

echo "==> Killing any running instance"
pkill -f yoga-tray 2>/dev/null || true

echo "==> Removing tray app"
rm -f "$TRAY_BIN"

echo "==> Removing autostart entry"
rm -f "$TRAY_DESKTOP"

echo "==> Removing application menu entry"
rm -f "$TRAY_APPENTRY"

echo ""
echo "Done. (Run 'sudo ./uninstall.sh' to remove system-level components too.)"
