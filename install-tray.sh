#!/usr/bin/env bash
# User install: deploys all tray apps and sets up autostart.
# Run as your normal user (not root).
#
# PREREQUISITE: run the root install first:
#   sudo ./install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔══════════════════════════════════════════════╗"
echo "║   Lenovo Yoga 9i Gen 7 — Linux Support       ║"
echo "║   Tray app install                            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

echo "━━━  Keyboard Backlight Tray  ━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/kbd-backlight/tray-app/install.sh"
echo ""

echo "━━━  Performance Profile Tray  ━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/perf-profile/tray-app/install.sh"
echo ""

echo "╔══════════════════════════════════════════════╗"
echo "║   Tray install complete.                     ║"
echo "║                                              ║"
echo "║   Launch now:                                ║"
echo "║     ~/.local/bin/kbd-backlight-tray &        ║"
echo "║     ~/.local/bin/platform-profile-tray &     ║"
echo "║                                              ║"
echo "║   Both will start automatically at login.    ║"
echo "╚══════════════════════════════════════════════╝"
