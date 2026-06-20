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

if ! python3 -c "
import gi; gi.require_version('AppIndicator3','0.1')
from gi.repository import AppIndicator3
" 2>/dev/null; then
    echo "    AppIndicator3 not found — tray will use Gtk.StatusIcon fallback"
    echo "    For better Cinnamon integration: sudo apt install gir1.2-appindicator3-0.1"
else
    echo "    AppIndicator3 present"
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

# ── install ───────────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$TRAY_BIN")"
echo "==> Installing tray app to $TRAY_BIN"
install -m 755 "$SCRIPT_DIR/yoga-tray" "$TRAY_BIN"

echo "==> Installing refresh-rate-toggle to $(dirname "$TRAY_BIN")/refresh-rate-toggle"
install -m 755 "$SCRIPT_DIR/../special-keys/refresh-rate-toggle" "$(dirname "$TRAY_BIN")/refresh-rate-toggle"


echo "==> Setting up Fn+R hardware key binding"
# Assign XF86Launch5 keysym to the KEY_REFRESH_RATE_TOGGLE keycode (evdev 562 → X11 570)
xmodmap -e "keycode 570 = XF86Launch5" 2>/dev/null || true
if ! grep -q "keycode 570" "$HOME/.Xmodmap" 2>/dev/null; then
    echo "keycode 570 = XF86Launch5" >> "$HOME/.Xmodmap"
fi
echo "    Keycode 570 = XF86Launch5 (active now + persisted to ~/.Xmodmap)"

# Wire XF86Launch5 → refresh-rate-toggle via Cinnamon custom keybinding
_KSYM="XF86Launch5"
_REFRESH_BIN="$(dirname "$TRAY_BIN")/refresh-rate-toggle"
_RAW_LIST=$(gsettings get org.cinnamon.desktop.keybindings custom-list 2>/dev/null | sed 's/^@as //')
_SLOT=""
for _s in $(echo "$_RAW_LIST" | tr -d "[]'" | tr ',' '\n'); do
    [ -z "$_s" ] && continue
    _p="/org/cinnamon/desktop/keybindings/custom-keybindings/$_s/"
    if gsettings get "org.cinnamon.desktop.keybindings.custom-keybinding:$_p" binding 2>/dev/null \
            | grep -q "$_KSYM"; then
        _SLOT="$_s"
        break
    fi
done
if [ -z "$_SLOT" ]; then
    _i=0
    _EXISTING=$(echo "$_RAW_LIST" | tr -d "[]'" | tr ',' '\n')
    while echo "$_EXISTING" | grep -qx "custom$_i"; do ((_i++)); done
    _SLOT="custom$_i"
    if [ "$_RAW_LIST" = "[]" ] || [ -z "$(echo "$_RAW_LIST" | tr -d "[]' ")" ]; then
        gsettings set org.cinnamon.desktop.keybindings custom-list "['$_SLOT']"
    else
        gsettings set org.cinnamon.desktop.keybindings custom-list \
            "$(echo "$_RAW_LIST" | sed "s/]$/, '$_SLOT']/")"
    fi
fi
_p="/org/cinnamon/desktop/keybindings/custom-keybindings/$_SLOT/"
_sc="org.cinnamon.desktop.keybindings.custom-keybinding:$_p"
gsettings set "$_sc" name    "Toggle Refresh Rate"  || true
gsettings set "$_sc" command "$_REFRESH_BIN"         || true
gsettings set "$_sc" binding "['$_KSYM']"            || true
echo "    Bound $_KSYM → $_REFRESH_BIN (Cinnamon slot: $_SLOT)"

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
