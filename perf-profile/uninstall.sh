#!/usr/bin/env bash
# Root uninstall: removes the platform-profile backend and sudoers rule.
# Run as root: sudo ./uninstall.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

die() { echo "ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo $0"

echo "==> Checking what is installed"
present=()
absent=()
for path in "$PROFILE_BIN" "$SUDOERS_FILE"; do
    if [ -e "$path" ]; then present+=("$path"); else absent+=("$path"); fi
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

rm -f "$PROFILE_BIN" "$SUDOERS_FILE"

echo "Done. (Tray app files are user-level — run tray-app/uninstall.sh to remove those.)"
