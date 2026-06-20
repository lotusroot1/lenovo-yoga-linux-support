#!/usr/bin/env bash
# User uninstall: removes all tray apps and autostart entries.
# Run as your normal user (not root).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━  Keyboard Backlight Tray  ━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/kbd-backlight/tray-app/uninstall.sh"
echo ""

echo "━━━  Performance Profile Tray  ━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/perf-profile/tray-app/uninstall.sh"
echo ""

echo "Done. (Run 'sudo ./uninstall.sh' to remove system-level components too.)"
