# Lenovo Yoga 9i Gen 7 — Linux Support

Linux support utilities for the Lenovo Yoga 9i Gen 7 (14IAP7) on Linux Mint / Ubuntu-based distros.

## What's included

| Subfolder | What it does |
|---|---|
| `kbd-backlight/` | Full 4-state keyboard backlight control (off / dim / on / auto) with a system tray app |
| `perf-profile/` | Performance profile tray app — shows and switches Power Saver / Balanced / Performance; notifies when the hardware key changes the profile |
| `special-keys/` | Key map reference and interactive remap script for the Yoga-specific top-row keys |

## Requirements

- Linux kernel 6.2+ (special key evdev support merged ~6.1/6.2 via `ideapad_laptop`)
- `acpi-call-dkms` — for keyboard backlight (ACPI KBLC method)
- `python3-gi` — for the tray apps
- `gir1.2-appindicator3-0.1` *(optional)* — better Cinnamon/Ubuntu tray integration
- `gir1.2-notify-0.7` *(optional)* — desktop notifications on key/profile changes

Install optional packages:
```bash
sudo apt install acpi-call-dkms python3-gi gir1.2-appindicator3-0.1 gir1.2-notify-0.7
```

## Install

```bash
# 1. System components (backend scripts, sudoers, systemd service)
sudo ./install.sh

# 2. Tray apps + autostart (run as your normal user)
./install-tray.sh
```

Both tray apps start automatically at login after step 2.

## Uninstall

```bash
./uninstall-tray.sh     # remove tray apps (run as your normal user)
sudo ./uninstall.sh     # remove system components
```

## Keyboard backlight

The kernel's `ideapad_laptop` sysfs interface only exposes 3 brightness levels and conflates `auto` with `off` (both read as 0). This project bypasses that by calling the ACPI `KBLC` method directly via `acpi_call`, giving full access to all 4 states.

```bash
sudo kbd-backlight get          # off | dim | on | auto
sudo kbd-backlight set auto     # set state
sudo kbd-backlight toggle       # cycle off → dim → on → auto → off
```

The tray app (right-click to switch states) also detects Fn+Space presses and updates the icon automatically.

The startup state defaults to `auto`. To change it:
```bash
sudo kbd-backlight/install.sh dim
```

## Performance profile

The hardware performance key cycles `/sys/firmware/acpi/platform_profile` silently — it emits no Linux keycode. The tray app polls the sysfs file every 2 seconds and shows a desktop notification when the profile changes.

You can also switch profiles from the tray menu without touching the keyboard.

```bash
cat /sys/firmware/acpi/platform_profile          # current profile
sudo platform-profile set balanced               # set manually
```

> **Note on dmesg errors:** Every performance key press logs `ACPI BIOS Error: Could not resolve symbol [WM00]`. This is a Lenovo BIOS bug — it assumes the Windows `WM00` WMI handler is always present. On Linux it isn't, but the profile still changes correctly through a separate path. The errors are harmless cosmetic noise.

## Special keys

See `special-keys/FINDINGS.md` for the full evdev key map and investigation notes.

Quick reference — keys that need manual binding (they emit keycodes but have no default action on Linux):

| Physical key | X11 keysym | Suggested use |
|---|---|---|
| Dark Mode | `XF86Launch1` | Toggle Cinnamon dark/light theme |
| Audio Profile | `XF86Launch2` | Cycle audio output |
| Camera BG Blur | `XF86Launch3` | Screenshot or custom app |
| Star / Favorite | *(needs xmodmap)* | User-defined |

Run the interactive setup menu to bind these to Cinnamon shortcuts:
```bash
special-keys/remap.sh
```

Keys handled automatically by the kernel (no setup needed): airplane mode (`KEY_RFKILL`), mic mute (`KEY_MICMUTE`), calculator (`KEY_CALC`), lock (`Super+L`).

## Tested on

- Lenovo Yoga 9i Gen 7 (14IAP7), 12th-gen Intel Alder Lake-P
- Linux Mint 22, kernel 6.17
