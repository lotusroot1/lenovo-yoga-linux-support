#!/usr/bin/env bash
# Root install: deploys the platform-profile backend and sudoers rule.
# Run as root: sudo ./install.sh
#
# After this, run (as your normal user):
#   ./tray-app/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

die() { echo "ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo $0"

# ── preflight ─────────────────────────────────────────────────────────────────
echo "==> Checking prerequisites"

[ -f /sys/firmware/acpi/platform_profile ] \
    || die "/sys/firmware/acpi/platform_profile not found — is the ideapad_laptop module loaded?"

for dir in "$(dirname "$PROFILE_BIN")" "$(dirname "$SUDOERS_FILE")"; do
    [ -d "$dir" ] || die "Directory not found: $dir"
done

echo "    All checks passed"

# ── install backend ───────────────────────────────────────────────────────────
echo "==> Installing backend to $PROFILE_BIN"
install -m 755 "$SCRIPT_DIR/platform-profile" "$PROFILE_BIN"

# ── sudoers rule ──────────────────────────────────────────────────────────────
echo "==> Installing sudoers rule to $SUDOERS_FILE"
cat > "$SUDOERS_FILE" <<'EOF'
# Allow members of the sudo group to set the ACPI platform profile without a
# password prompt. The platform-profile-tray app calls this on menu selection.
%sudo ALL=(root) NOPASSWD: /usr/local/bin/platform-profile set *
EOF
chmod 440 "$SUDOERS_FILE"

echo ""
echo "Done. Now run (as your normal user):"
echo "  $SCRIPT_DIR/tray-app/install.sh"
echo ""
echo "To test the backend now:"
echo "  $PROFILE_BIN get"
echo "  sudo $PROFILE_BIN set balanced"
