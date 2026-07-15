#!/usr/bin/env bash
# Root install: deploys the battery-conservation backend, a sudoers rule, and
# a systemd oneshot service that re-enables conservation mode at every boot
# (the ideapad_acpi conservation_mode sysfs value does not reliably persist
# across reboots on its own).
# Run as root: sudo ./install.sh [on|off]   (default: on)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

STARTUP_STATE="${1:-on}"

die() { echo "ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo $0 $*"

case "$STARTUP_STATE" in
    on|off) ;;
    *) die "invalid state '$STARTUP_STATE' — use: on, off" ;;
esac

# ── preflight ─────────────────────────────────────────────────────────────────
echo "==> Checking prerequisites"

SYSFS=/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode
[ -f "$SYSFS" ] \
    || die "$SYSFS not found — is the ideapad_laptop module loaded?"

for dir in "$(dirname "$BAT_BIN")" "$(dirname "$SERVICE_FILE")" "$(dirname "$SUDOERS_FILE")"; do
    [ -d "$dir" ] || die "Directory not found: $dir"
done

echo "    All checks passed"

# ── install backend ───────────────────────────────────────────────────────────
echo "==> Installing backend to $BAT_BIN"
install -m 755 "$SCRIPT_DIR/battery-conservation" "$BAT_BIN"

# ── systemd service ────────────────────────────────────────────────────────────
echo "==> Installing systemd service (startup state: $STARTUP_STATE)"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Set battery conservation mode on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=$BAT_BIN set $STARTUP_STATE
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now battery-conservation.service

# ── sudoers rule ──────────────────────────────────────────────────────────────
echo "==> Installing sudoers rule to $SUDOERS_FILE"
cat > "$SUDOERS_FILE" <<'EOF'
# Allow members of the sudo group to toggle battery conservation mode
# without a password prompt.
%sudo ALL=(root) NOPASSWD: /usr/local/bin/battery-conservation set *
EOF
chmod 440 "$SUDOERS_FILE"

echo ""
echo "Done. Conservation mode: $STARTUP_STATE (applied now and on every boot)"
echo ""
echo "Usage (no password needed):"
echo "  sudo battery-conservation get"
echo "  sudo battery-conservation set off"
echo ""
echo "To change the startup state: sudo ./install.sh <on|off>"
