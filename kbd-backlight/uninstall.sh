#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# ── preflight: report what will actually be removed ───────────────────────────
echo "==> Checking what is installed"
present=()
absent=()

for path in "$KBD_BIN" "$SERVICE_FILE" "$MODULES_CONF" "$SUDOERS_FILE" \
            "$SLEEP_HOOK" "$TRAY_BIN" "$TRAY_DESKTOP"; do
    if [ -e "$path" ]; then
        present+=("$path")
    else
        absent+=("$path")
    fi
done

if [ "${#present[@]}" -eq 0 ]; then
    echo "Nothing from this installer found on the system. Nothing to do."
    exit 0
fi

echo "    Will remove:"
for p in "${present[@]}"; do echo "      $p"; done

if [ "${#absent[@]}" -gt 0 ]; then
    echo "    Already absent (skipping):"
    for a in "${absent[@]}"; do echo "      $a"; done
fi
echo ""

# ── tray app (user-level) ─────────────────────────────────────────────────────
if [ -f "$TRAY_BIN" ] || [ -f "$TRAY_DESKTOP" ]; then
    echo "==> Removing tray app"
    pkill -f kbd-backlight-tray 2>/dev/null || true
    rm -f "$TRAY_BIN" "$TRAY_DESKTOP"
fi

# ── system install ────────────────────────────────────────────────────────────
echo "==> Stopping and disabling kbd-backlight service"
systemctl disable --now kbd-backlight.service 2>/dev/null || true
rm -f "$SERVICE_FILE"
systemctl daemon-reload

echo "==> Removing acpi_call autoload"
rm -f "$MODULES_CONF"

echo "==> Removing sudo rule"
rm -f "$SUDOERS_FILE"

echo "==> Removing suspend/resume hook"
rm -f "$SLEEP_HOOK"

echo "==> Removing kbd-backlight script"
rm -f "$KBD_BIN"

echo ""
echo "Done. acpi_call is still loaded this session; it will not reload on next boot."
echo ""
echo "When native kernel support lands, use sysfs directly:"
echo "  echo 2 > /sys/class/leds/platform::kbd_backlight/brightness  (on)"
echo "  echo 1 > /sys/class/leds/platform::kbd_backlight/brightness  (dim)"
echo "  echo 0 > /sys/class/leds/platform::kbd_backlight/brightness  (off)"
echo "systemd-backlight persists the value across reboots automatically."
