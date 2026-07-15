#!/usr/bin/env bash
# Root install: sets up all system-level components for Lenovo Yoga 9i Gen 7.
# Run as root: sudo ./install.sh [backlight-startup-state]
#
#   [backlight-startup-state]  one of: off, dim, on, auto (default: auto)
#
# After this, run (as your normal user):
#   ./install-tray.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo $0 $*"

echo "╔══════════════════════════════════════════════╗"
echo "║   Lenovo Yoga 9i Gen 7 — Linux Support       ║"
echo "║   Root install                                ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── keyboard backlight ────────────────────────────────────────────────────────
echo "━━━  Keyboard Backlight  ━━━━━━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/kbd-backlight/install.sh" "${1:-auto}"
echo ""

# ── performance profile ───────────────────────────────────────────────────────
echo "━━━  Performance Profile  ━━━━━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/perf-profile/install.sh"
echo ""

# ── battery conservation ──────────────────────────────────────────────────────
echo "━━━  Battery Conservation  ━━━━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/battery-conservation/install.sh"
echo ""

# ── done ──────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════╗"
echo "║   System install complete.                   ║"
echo "║                                              ║"
echo "║   Now run (as your normal user):             ║"
echo "║     ./install-tray.sh                        ║"
echo "╚══════════════════════════════════════════════╝"
