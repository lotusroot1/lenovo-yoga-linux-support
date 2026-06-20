#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

INSTALL_USER="${SUDO_USER:-$USER}"
STARTUP_STATE="${1:-auto}"

die() { echo "ERROR: $*" >&2; exit 1; }

case "$STARTUP_STATE" in
    off|dim|on|auto) ;;
    *) die "invalid state '$STARTUP_STATE' — use: off, dim, on, auto" ;;
esac

# ── preflight: verify base directories exist ──────────────────────────────────
echo "==> Checking system directories"
errors=()

for path in "$KBD_BIN" "$SERVICE_FILE" "$MODULES_CONF" "$SUDOERS_FILE"; do
    dir="$(dirname "$path")"
    [ -d "$dir" ] || errors+=("$dir  (needed for $path)")
done

if [ "${#errors[@]}" -gt 0 ]; then
    echo ""
    echo "ERROR: The following directories do not exist on this system:"
    for e in "${errors[@]}"; do echo "  • $e"; done
    echo ""
    echo "This installer expects a systemd-based distro with sudo."
    echo "Edit config.sh to adjust paths for your distro."
    exit 1
fi
echo "    All base directories present"

# ── install ───────────────────────────────────────────────────────────────────
echo "==> Installing kbd-backlight to $KBD_BIN"
install -m 755 "$SCRIPT_DIR/kbd-backlight" "$KBD_BIN"

echo "==> Configuring acpi_call to load at boot ($MODULES_CONF)"
echo "acpi_call" > "$MODULES_CONF"

echo "==> Installing systemd service (startup state: $STARTUP_STATE)"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Set keyboard backlight state on boot
After=systemd-modules-load.service

[Service]
Type=oneshot
ExecStartPre=modprobe acpi_call
ExecStart=$KBD_BIN set $STARTUP_STATE
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable kbd-backlight.service

echo "==> Installing suspend/resume hook ($SLEEP_HOOK)"
cat > "$SLEEP_HOOK" <<'EOF'
#!/usr/bin/env bash
# Saves backlight state before suspend; restores it after resume.
KBD_BIN=/usr/local/bin/kbd-backlight
STATE_FILE=/run/kbd-backlight-suspend-state

case "$1" in
    pre)
        "$KBD_BIN" get > "$STATE_FILE" 2>/dev/null || true
        ;;
    post)
        if [ -f "$STATE_FILE" ]; then
            "$KBD_BIN" set "$(cat "$STATE_FILE")" 2>/dev/null || true
        fi
        ;;
esac
EOF
chmod 755 "$SLEEP_HOOK"

echo "==> Adding passwordless sudo rule ($SUDOERS_FILE)"
echo "$INSTALL_USER ALL=(ALL) NOPASSWD: $KBD_BIN" > "$SUDOERS_FILE"
chmod 440 "$SUDOERS_FILE"

echo ""
echo "Done. Startup state: $STARTUP_STATE"
echo ""
echo "Usage (no password needed):"
echo "  sudo kbd-backlight get"
echo "  sudo kbd-backlight set auto"
echo ""
echo "To change the startup state: sudo ./install.sh <state>"
