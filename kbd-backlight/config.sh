# Shared path constants for install.sh, uninstall.sh, and tray-app/install.sh.
# Edit here to relocate everything — scripts source this file.

# System install locations
KBD_BIN=/usr/local/bin/kbd-backlight
SERVICE_FILE=/etc/systemd/system/kbd-backlight.service
MODULES_CONF=/etc/modules-load.d/acpi_call.conf
SUDOERS_FILE=/etc/sudoers.d/kbd-backlight
SLEEP_HOOK=/usr/lib/systemd/system-sleep/kbd-backlight

# Tray app (user-level)
TRAY_BIN="$HOME/.local/bin/kbd-backlight-tray"
TRAY_DESKTOP="$HOME/.config/autostart/kbd-backlight-tray.desktop"
TRAY_APPENTRY="$HOME/.local/share/applications/kbd-backlight-tray.desktop"
