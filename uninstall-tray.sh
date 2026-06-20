#!/usr/bin/env bash
# User uninstall: removes the Yoga tray app and autostart entry.
# Run as your normal user (not root).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/tray-app/uninstall.sh"
