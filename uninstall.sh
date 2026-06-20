#!/usr/bin/env bash
# Root uninstall: removes all system-level components.
# Run as root: sudo ./uninstall.sh
#
# Tray apps are user-level — run ./uninstall-tray.sh as your normal user first.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo $0"

echo "╔══════════════════════════════════════════════╗"
echo "║   Lenovo Yoga 9i Gen 7 — Linux Support       ║"
echo "║   Root uninstall                              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

echo "━━━  Keyboard Backlight  ━━━━━━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/kbd-backlight/uninstall.sh"
echo ""

echo "━━━  Performance Profile  ━━━━━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/perf-profile/uninstall.sh"
echo ""

echo "Done. (Run ./uninstall-tray.sh as your normal user to remove tray apps.)"
