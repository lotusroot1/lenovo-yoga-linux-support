#!/usr/bin/env bash
# User install: deploys the combined Yoga tray app and sets up autostart.
# Run as your normal user (not root).
#
# PREREQUISITE: run the root install first:
#   sudo ../install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TRAY_BIN="$HOME/.local/bin/yoga-tray"
TRAY_DESKTOP="$HOME/.config/autostart/yoga-tray.desktop"
TRAY_APPENTRY="$HOME/.local/share/applications/yoga-tray.desktop"

die() { echo "ERROR: $*" >&2; exit 1; }

# ── preflight ─────────────────────────────────────────────────────────────────
echo "==> Checking prerequisites"

if [ ! -f /usr/local/bin/kbd-backlight ] && [ ! -f /usr/local/bin/platform-profile ]; then
    die "Neither backend is installed. Run first: cd '$(dirname "$SCRIPT_DIR")' && sudo ./install.sh"
fi

[ ! -f /usr/local/bin/kbd-backlight ]   && echo "    ⚠  kbd-backlight not installed — backlight control will show as unavailable"
[ ! -f /usr/local/bin/platform-profile ] && echo "    ⚠  platform-profile not installed — profile control will show as unavailable"

python3 -c "import gi" 2>/dev/null \
    || die "python3-gi not found. Install: sudo apt install python3-gi"

if python3 -c "
import gi; gi.require_version('XApp', '1.0')
from gi.repository import XApp
" 2>/dev/null; then
    echo "    XApp present — left-click opens Yoga Options, right-click opens menu"
elif python3 -c "
import gi; gi.require_version('AppIndicator3','0.1')
from gi.repository import AppIndicator3
" 2>/dev/null; then
    echo "    AppIndicator3 present (menu-only; no left-click support)"
    echo "    For left-click support: sudo apt install gir1.2-xapp-1.0"
else
    echo "    Neither XApp nor AppIndicator3 found — using Gtk.StatusIcon fallback"
    echo "    Recommended: sudo apt install gir1.2-xapp-1.0"
fi

if ! python3 -c "
import gi; gi.require_version('Notify','0.7')
from gi.repository import Notify
" 2>/dev/null; then
    echo "    libnotify not found — hardware key notifications disabled"
    echo "    To enable: sudo apt install gir1.2-notify-0.7"
else
    echo "    libnotify present"
fi

echo "    All checks passed"

# ── input group (required for star key and refresh key via evdev) ─────────────
# KEY_FAVORITES and KEY_REFRESH_RATE_TOGGLE have evdev keycodes > 247, which
# puts them beyond X11's 8-255 keycode range. The tray reads them directly from
# /dev/input, which requires membership in the 'input' group.
echo "==> Checking 'input' group membership"
if groups "$USER" | grep -qw input; then
    echo "    Already in 'input' group — OK"
else
    echo "    Adding $USER to 'input' group (requires sudo)"
    sudo usermod -aG input "$USER"
    echo "    ⚠  Log out and log back in for the group change to take effect"
fi

# ── install ───────────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$TRAY_BIN")"
echo "==> Installing tray app to $TRAY_BIN"
install -m 755 "$SCRIPT_DIR/yoga-tray" "$TRAY_BIN"

echo "==> Installing refresh-rate-toggle to $(dirname "$TRAY_BIN")/refresh-rate-toggle"
install -m 755 "$SCRIPT_DIR/../special-keys/refresh-rate-toggle" "$(dirname "$TRAY_BIN")/refresh-rate-toggle"

# ── pre-populate evdev key commands ──────────────────────────────────────────
# These are stored in ~/.config/yoga-tray/ and picked up by the tray's evdev
# listener. The user can change them at any time via the tray menu.
YOGA_CFG="$HOME/.config/yoga-tray"
mkdir -p "$YOGA_CFG"

if [ ! -s "$YOGA_CFG/fav-cmd" ]; then
    echo "x-terminal-emulator" > "$YOGA_CFG/fav-cmd"
    echo "==> Star key default: x-terminal-emulator (change via tray menu)"
fi

if [ ! -s "$YOGA_CFG/refresh-cmd" ]; then
    echo "$(dirname "$TRAY_BIN")/refresh-rate-toggle" > "$YOGA_CFG/refresh-cmd"
    echo "==> Refresh key default: refresh-rate-toggle (change via tray menu)"
fi

# ── clean up stale xmodmap entries ───────────────────────────────────────────
if [ -f "$HOME/.Xmodmap" ]; then
    sed -i '/keycode 570/d; /keycode 372/d' "$HOME/.Xmodmap"
    # Remove the file if it's now empty
    [ -s "$HOME/.Xmodmap" ] || rm -f "$HOME/.Xmodmap"
    echo "==> Removed stale xmodmap entries from ~/.Xmodmap"
fi

mkdir -p "$(dirname "$TRAY_DESKTOP")"
echo "==> Adding autostart entry ($TRAY_DESKTOP)"
cat > "$TRAY_DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Yoga Tray
Comment=Keyboard backlight and performance profile for Yoga 9i Gen 7
Exec=$TRAY_BIN
Icon=input-keyboard
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

mkdir -p "$(dirname "$TRAY_APPENTRY")"
echo "==> Adding application menu entry ($TRAY_APPENTRY)"
cat > "$TRAY_APPENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Yoga Tray
Comment=Keyboard backlight and performance profile for Yoga 9i Gen 7
Exec=$TRAY_BIN
Icon=input-keyboard
Categories=Utility;HardwareSettings;
StartupNotify=false
EOF

echo ""
echo "Done."
echo "  Launch now:   $TRAY_BIN &"
echo "  Autostart:    active at next login"
echo "  Uninstall:    ./uninstall.sh"
