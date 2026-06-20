#!/usr/bin/env bash
# User install: deploys the tray app and sets up autostart.
# Run as your normal user (not root).
#
# PREREQUISITE: the root install.sh must be run first:
#   sudo ../install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

die() { echo "ERROR: $*" >&2; exit 1; }

# ── preflight ─────────────────────────────────────────────────────────────────
echo "==> Checking prerequisites"

[ -f "$PROFILE_BIN" ] \
    || die "Backend not installed ($PROFILE_BIN). Run first: cd '$(dirname "$SCRIPT_DIR")' && sudo ./install.sh"

python3 -c "import gi" 2>/dev/null \
    || die "python3-gi not found. Install: sudo apt install python3-gi"

if ! python3 -c "
import gi; gi.require_version('AppIndicator3','0.1')
from gi.repository import AppIndicator3
" 2>/dev/null; then
    echo "    AppIndicator3 not found — tray will use Gtk.StatusIcon fallback"
    echo "    For better Cinnamon integration: sudo apt install gir1.2-appindicator3-0.1"
    echo "    (continuing without it)"
else
    echo "    AppIndicator3 present"
fi

if ! python3 -c "
import gi; gi.require_version('Notify','0.7')
from gi.repository import Notify
" 2>/dev/null; then
    echo "    libnotify not found — hardware key notifications disabled"
    echo "    To enable: sudo apt install gir1.2-notify-0.7"
    echo "    (continuing without it)"
else
    echo "    libnotify present"
fi

echo "    All checks passed"

# ── install ───────────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$TRAY_BIN")"
echo "==> Installing tray app to $TRAY_BIN"
install -m 755 "$SCRIPT_DIR/platform-profile-tray" "$TRAY_BIN"

mkdir -p "$(dirname "$TRAY_DESKTOP")"
echo "==> Adding autostart entry ($TRAY_DESKTOP)"
cat > "$TRAY_DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Performance Profile Tray
Comment=System tray control for Yoga 9i Gen 7 performance mode
Exec=$TRAY_BIN
Icon=preferences-system-symbolic
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

mkdir -p "$(dirname "$TRAY_APPENTRY")"
echo "==> Adding application menu entry ($TRAY_APPENTRY)"
cat > "$TRAY_APPENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Performance Profile Tray
Comment=System tray control for Yoga 9i Gen 7 performance mode
Exec=$TRAY_BIN
Icon=preferences-system-symbolic
Categories=Utility;HardwareSettings;
StartupNotify=false
EOF

echo ""
echo "Done."
echo "  Launch now:   $TRAY_BIN &"
echo "  Autostart:    active at next login"
echo "  Uninstall:    ./uninstall.sh  (tray only)  or  sudo ../uninstall.sh  (everything)"
