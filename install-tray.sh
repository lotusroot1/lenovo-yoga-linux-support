#!/usr/bin/env bash
# User install: deploys the Yoga tray app and sets up autostart.
# Run as your normal user (not root).
#
# PREREQUISITE: run the root install first:
#   sudo ./install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/tray-app/install.sh"
