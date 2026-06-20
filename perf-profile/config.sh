# Shared path constants for install.sh, uninstall.sh, and tray-app/install.sh.
# Edit here to relocate everything — scripts source this file.

# System install locations (root)
PROFILE_BIN=/usr/local/bin/platform-profile
SUDOERS_FILE=/etc/sudoers.d/platform-profile

# Tray app (user-level)
TRAY_BIN="$HOME/.local/bin/platform-profile-tray"
TRAY_DESKTOP="$HOME/.config/autostart/platform-profile-tray.desktop"
TRAY_APPENTRY="$HOME/.local/share/applications/platform-profile-tray.desktop"
