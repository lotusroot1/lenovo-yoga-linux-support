#!/usr/bin/env bash
# Verification script - cycles through all backlight states and reports raw values.
# Restores original state at the end.
# Run as: sudo ./verify.sh

KBLC='\\_SB.PC00.LPCB.EC0.VPC0.KBLC'
PROC=/proc/acpi/call
SYSFS=/sys/class/leds/platform::kbd_backlight/brightness

die() { echo "ERROR: $*" >&2; exit 1; }

kblc() {
    printf '%s %s' "$KBLC" "$1" > "$PROC"
    tr -d '\0' < "$PROC"
}

state_name() {
    local val=$(( $1 + 0 ))
    local s=$(( (val & 0xFFFE) >> 1 ))
    case $s in 0) echo "off";; 1) echo "dim";; 2) echo "on";; 3) echo "auto";; *) echo "unknown";; esac
}

[ -f "$PROC" ] || die "acpi_call not loaded (sudo modprobe acpi_call)"
[ -w "$PROC" ] || die "run as root"

echo "========================================"
echo " Keyboard Backlight Verification"
echo "========================================"
echo ""

# Device type query
type_raw=$(kblc 0x1)
echo "[1] Device type query: KBLC(0x1) = $type_raw"
case "$type_raw" in
    0x5) echo "    → KBD_BL_TRISTATE (3 states: off/dim/on)" ;;
    0x7) echo "    → KBD_BL_TRISTATE_AUTO (4 states: off/dim/on/auto) ✓" ;;
    *)   echo "    → UNEXPECTED value" ;;
esac
echo ""

# Current state before we touch anything
initial_raw=$(kblc 0x32)
initial_sysfs=$(cat "$SYSFS")
initial_name=$(state_name "$initial_raw")
echo "[2] Initial state:"
echo "    KBLC GET (0x32) = $initial_raw  → $initial_name"
echo "    sysfs brightness = $initial_sysfs"
echo ""

# Cycle through all 4 states
echo "[3] Cycling through all states:"
echo ""

for entry in "off:0x33:0" "dim:0x10033:1" "on:0x20033:2" "auto:0x30033:3"; do
    name="${entry%%:*}"
    rest="${entry#*:}"
    set_arg="${rest%%:*}"
    expected_state="${rest#*:}"

    set_raw=$(kblc "$set_arg")
    get_raw=$(kblc 0x32)
    sysfs_val=$(cat "$SYSFS")
    got_state=$(( ($(( get_raw + 0 )) & 0xFFFE) >> 1 ))
    got_name=$(state_name "$get_raw")

    pass="✓"
    [ "$got_state" = "$expected_state" ] || pass="✗ MISMATCH"

    echo "    SET $name ($set_arg):"
    echo "      SET return  = $set_raw"
    echo "      GET (0x32)  = $get_raw  → $got_name  $pass"
    echo "      sysfs       = $sysfs_val"
    echo ""
    sleep 0.5
done

# Restore original state
echo "[4] Restoring original state: $initial_name"
case "$initial_name" in
    off)  kblc 0x33    > /dev/null ;;
    dim)  kblc 0x10033 > /dev/null ;;
    on)   kblc 0x20033 > /dev/null ;;
    auto) kblc 0x30033 > /dev/null ;;
esac
restored_raw=$(kblc 0x32)
echo "    Restored: KBLC GET = $restored_raw  → $(state_name "$restored_raw")"
echo ""
echo "========================================"
