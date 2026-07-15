#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# ── preflight: report what will actually be removed ───────────────────────────
echo "==> Checking what is installed"
present=()
absent=()

for path in "$BAT_BIN" "$SERVICE_FILE" "$SUDOERS_FILE"; do
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

# ── system install ────────────────────────────────────────────────────────────
echo "==> Stopping and disabling battery-conservation service"
systemctl disable --now battery-conservation.service 2>/dev/null || true
rm -f "$SERVICE_FILE"
systemctl daemon-reload

echo "==> Removing sudo rule"
rm -f "$SUDOERS_FILE"

echo "==> Removing battery-conservation script"
rm -f "$BAT_BIN"

echo ""
echo "Done. Conservation mode is left at its current value — it will simply"
echo "stop being re-applied at boot. To turn it off manually:"
echo "  echo 0 | sudo tee /sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"
