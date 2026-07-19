# Lenovo Yoga 9i Gen 7 — Linux Support

Linux support utilities for the Lenovo Yoga 9i Gen 7 (14IAP7) on Linux Mint / Ubuntu-based distros.

## What's included

| Subfolder | What it does |
|---|---|
| `tray-app/` | Combined system tray app — keyboard backlight, performance profile, battery conservation toggle, battery health, refresh rate, and special key bindings |
| `special-keys/` | Key map reference for the Yoga-specific top-row and function-row keys |
| `battery-conservation/` | Caps battery charging around 75-80% via `ideapad_acpi` conservation mode, reapplied at every boot — reduces long-term battery wear on machines that stay plugged in |

## Requirements

- Linux kernel 6.2+ (special key evdev support merged ~6.1/6.2 via `ideapad_laptop`)
- `acpi-call-dkms` — for keyboard backlight (ACPI KBLC method)
- `python3-gi` — for the tray app
- `python3-xlib` — refresh rate detection without spawning `xrandr` (avoids fullscreen video disruption)
- `gir1.2-xapp-1.0` *(optional, recommended on Cinnamon/MATE)* — enables left-click to open the companion window; right-click for the menu
- `gir1.2-appindicator3-0.1` *(optional, fallback)* — menu-only tray integration when XApp is unavailable
- `gir1.2-notify-0.7` *(optional)* — desktop notifications on hardware key changes

```bash
sudo apt install acpi-call-dkms python3-gi python3-xlib gir1.2-xapp-1.0 gir1.2-notify-0.7
```

## Install

```bash
# 1. System components (backend scripts, sudoers, systemd service)
sudo ./install.sh

# 2. Tray app + autostart (run as your normal user)
cd tray-app && ./install.sh
```

The tray app starts automatically at login after step 2.

## Uninstall

```bash
cd tray-app && ./uninstall.sh     # remove tray app
sudo ./uninstall.sh               # remove system components
```

## Tray app

`yoga-tray` sits in the system tray with two interaction modes:

- **Left-click** (XApp/StatusIcon) — opens the Yoga Options companion window
- **Right-click** — opens the context menu inline

The companion window (**Yoga Options**) shows all controls in one persistent, resolution-safe panel that stays open independently of the menu. It auto-updates when hardware keys or the context menu change any value.

The context menu covers:

### Keyboard backlight

Four states: off / dim / on / auto (ambient light sensor). The tray detects Fn+Space presses and updates automatically.

The kernel's sysfs interface conflates `auto` and `off` (both read 0). This project calls the ACPI `KBLC` method directly via `acpi_call` to distinguish them.

```bash
sudo kbd-backlight get          # off | dim | on | auto
sudo kbd-backlight set auto
```

### Performance profile

Switches between Power Saver / Balanced / Performance. The hardware performance key cycles the profile silently (no Linux keycode — the EC updates `/sys/firmware/acpi/platform_profile` directly). The tray polls for changes and notifies when the profile switches.

```bash
cat /sys/firmware/acpi/platform_profile
sudo platform-profile set balanced
```

> **Note on dmesg errors:** Every performance key press logs `ACPI BIOS Error: Could not resolve symbol [WM00]`. This is a Lenovo BIOS bug — it assumes the Windows WMI handler is always present. The profile still changes correctly through a separate path. The errors are harmless.

### Battery conservation

Toggles charge-cap conservation mode on/off (~75-80% cap) via `ideapad_acpi`, backed by the `battery-conservation/` systemd service so the setting survives reboots.

```bash
cat /sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode
sudo battery-conservation set on
```

### Battery health

Read-only wear indicator, similar to coconutBattery on macOS: full-charge capacity vs. design capacity, plus charge-cycle count, read from `/sys/class/power_supply/BAT*/`. Cinnamon's built-in battery UI only shows current charge percentage, not wear — this fills that gap. Refreshes every 60s (wear changes slowly) and on every menu open.

```bash
cat /sys/class/power_supply/BAT0/energy_full        # current full-charge capacity (µWh)
cat /sys/class/power_supply/BAT0/energy_full_design  # original design capacity (µWh)
cat /sys/class/power_supply/BAT0/cycle_count
```

### Display refresh rate

Toggles between 90 Hz and 60 Hz. The built-in display (eDP-1) advertises both rates for the native 2880×1800 resolution in its EDID, so no custom modelines are needed.

The tray reads the current rate via `python3-xlib` (RandR in-process on X11, or `org.gnome.Mutter.DisplayConfig` D-Bus on Wayland) rather than spawning `xrandr` periodically — this avoids disrupting fullscreen video rendering.

### Key bindings

Binds commands to the Yoga-specific special keys. Order matches the physical keyboard layout:

| Key | Method |
|---|---|
| Lenovo Star | `/dev/input` (evdev) — beyond X11's keycode range |
| Camera Blur | Cinnamon custom shortcut (gsettings) |
| Audio Profile | Cinnamon custom shortcut (gsettings) |
| Dark Mode | Cinnamon custom shortcut (gsettings) |
| Refresh Rate toggle | `/dev/input` (evdev) — beyond X11's keycode range |

The Star key (`KEY_FAVORITES`, evdev 364) and Refresh Rate key (`KEY_REFRESH_RATE_TOGGLE`, evdev 562) map to X11 keycodes 372 and 570 respectively — both beyond X11's hard limit of 255. xmodmap cannot map them. The tray reads `/dev/input` directly, bypassing X11 entirely.

Bindings can be set from the context menu (presets + custom command + browse) or from the Yoga Options window.

**Requires the `input` group** — the install script adds you automatically, but you need to log out and back in once for it to take effect.

## Notifications

When hardware keys change the profile, backlight, or refresh rate, a desktop notification appears after a short settling period. If multiple things change at once (e.g. you switch both the profile and refresh rate), they are batched into a single notification.

## Timing config

Optional — create `~/.config/yoga-tray/timing.conf` to override defaults:

```ini
# How often to check each hardware value (milliseconds)
performance_interval_ms    = 500
display_interval_ms        = 5000
backlight_interval_ms      = 500
conservation_interval_ms   = 5000
battery_health_interval_ms = 60000

# Extra settling time after the slowest check before a notification fires.
# Effective debounce = max(intervals above) + notification_delay_ms
# Default: 5000 + 500 = 5500 ms
notification_delay_ms      = 500
```

## Special keys

See `special-keys/FINDINGS.md` for the full evdev key map and investigation notes.

Quick reference — keys handled by the tray or kernel automatically:

| Physical key | Handling |
|---|---|
| Lenovo Star | Bindable via tray / Yoga Options → runs command via evdev |
| Camera Blur | Bindable via tray / Yoga Options → Cinnamon shortcut |
| Audio Profile | Bindable via tray / Yoga Options → Cinnamon shortcut |
| Dark Mode | Bindable via tray / Yoga Options → Cinnamon shortcut |
| Refresh Rate | Bindable via tray / Yoga Options → runs command via evdev |
| Performance mode | Hardware cycles profile directly; tray detects and notifies |
| Airplane mode | Kernel (`KEY_RFKILL`) |
| Mic mute | Cinnamon (`KEY_F20`) |
| Calculator | Kernel (`KEY_CALC`) |
| Lock | Kernel (`Super+L`) |

## Tested on

- Lenovo Yoga 9i Gen 7 (14IAP7), 12th-gen Intel Alder Lake-P
- Linux Mint 22, kernel 6.17
