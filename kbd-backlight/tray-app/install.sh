#!/usr/bin/env bash
# Installs the kbd-backlight tray app and adds it to the desktop autostart.
# Run as your normal user (not root).
#
# PREREQUISITE: the root install.sh in the repo root must be run first:
#   sudo ../install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

REPO_ROOT="$(dirname "$SCRIPT_DIR")"

die() { echo "ERROR: $*" >&2; exit 1; }

# ── preflight: check root install was done first ──────────────────────────────
echo "==> Checking prerequisites"
missing=()
[ -f "$KBD_BIN" ]      || missing+=("kbd-backlight script ($KBD_BIN)")
[ -f "$SUDOERS_FILE" ] || missing+=("sudoers rule ($SUDOERS_FILE)")
[ -f "$MODULES_CONF" ] || missing+=("acpi_call autoload ($MODULES_CONF)")

if [ "${#missing[@]}" -gt 0 ]; then
    echo ""
    echo "ERROR: root install is incomplete. Missing:"
    for m in "${missing[@]}"; do echo "  • $m"; done
    echo ""
    echo "Run first:  cd '$REPO_ROOT' && sudo ./install.sh"
    exit 1
fi

# Check tray autostart dir exists (XDG standard — should exist on any DE)
AUTOSTART_DIR="$(dirname "$TRAY_DESKTOP")"
[ -d "$(dirname "$TRAY_BIN")" ] || mkdir -p "$(dirname "$TRAY_BIN")"
[ -d "$AUTOSTART_DIR" ]         || mkdir -p "$AUTOSTART_DIR"
echo "    Prerequisites OK"

# ── Python / GTK dependencies ─────────────────────────────────────────────────
echo "==> Checking Python/GTK dependencies"

python3 -c "import gi" 2>/dev/null || {
    echo ""
    echo "ERROR: python3-gi not found. Install it for your distro:"
    echo "  Debian/Ubuntu/Mint:  sudo apt install python3-gi"
    echo "  Fedora:              sudo dnf install python3-gobject"
    echo "  Arch:                sudo pacman -S python-gobject"
    exit 1
}

if ! python3 -c "
import gi
gi.require_version('AppIndicator3','0.1')
from gi.repository import AppIndicator3
" 2>/dev/null; then
    echo "    AppIndicator3 not found — tray will use Gtk.StatusIcon fallback"
    echo "    For better Cinnamon integration, install it:"
    echo "      Debian/Ubuntu/Mint:  sudo apt install gir1.2-appindicator3-0.1"
    echo "      Fedora:              sudo dnf install libappindicator-gtk3"
    echo "    (continuing without it)"
else
    echo "    AppIndicator3 present"
fi

if ! python3 -c "
import gi
gi.require_version('Notify','0.7')
from gi.repository import Notify
" 2>/dev/null; then
    echo "    libnotify not found — Fn+Space state-change notifications disabled"
    echo "    To enable desktop notifications, install it:"
    echo "      Debian/Ubuntu/Mint:  sudo apt install gir1.2-notify-0.7"
    echo "      Fedora:              sudo dnf install libnotify"
    echo "      Arch:                sudo pacman -S libnotify"
    echo "    (continuing without it)"
else
    echo "    libnotify present"
fi

# ── install ───────────────────────────────────────────────────────────────────
echo "==> Installing to $TRAY_BIN"
install -m 755 "$SCRIPT_DIR/kbd-backlight-tray" "$TRAY_BIN"

echo "==> Adding autostart entry ($TRAY_DESKTOP)"
cat > "$TRAY_DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Keyboard Backlight Tray
Comment=System tray control for Yoga 9i Gen 7 keyboard backlight
Exec=$TRAY_BIN
Icon=input-keyboard
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

echo "==> Adding application menu entry ($TRAY_APPENTRY)"
[ -d "$(dirname "$TRAY_APPENTRY")" ] || mkdir -p "$(dirname "$TRAY_APPENTRY")"
cat > "$TRAY_APPENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Keyboard Backlight Tray
Comment=System tray control for Yoga 9i Gen 7 keyboard backlight
Exec=$TRAY_BIN
Icon=input-keyboard
Categories=Utility;HardwareSettings;
StartupNotify=false
EOF

echo ""
echo "Done."
echo "  Launch now:   $TRAY_BIN &"
echo "  Find in menu: search for 'Keyboard Backlight' in your application launcher"
echo "  Autostart:    active at next login"
echo "  Uninstall:    sudo '$REPO_ROOT/uninstall.sh'  (removes everything)"
