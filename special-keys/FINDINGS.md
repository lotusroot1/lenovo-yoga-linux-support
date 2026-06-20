# Lenovo Yoga 9i Gen 7 (14IAP7) — Special Keys on Linux

Investigation into the special/hotkey rows on the Lenovo Yoga 9i Gen 7 running
Linux Mint. Covers detection, key codes, and remapping.

---

## Hardware

- Model: Lenovo Yoga 9i Gen 7 (14IAP7), 12th-gen Intel Alder Lake-P
- OS: Linux Mint (kernel 6.17.0-35-generic tested)
- Relevant kernel driver: `ideapad_laptop` (device `VPC2004:00`)

---

## Key input devices

| /dev/input | Name | Key events |
|---|---|---|
| event3 | AT Translated Set 2 keyboard | Standard keys + Fn row |
| event8 | Intel HID events | Volume, brightness, sleep |
| event9 | Ideapad extra buttons | All Lenovo special keys |

---

## Confirmed key map (evtest verified)

### Top-row special keys (above F-row)

| Physical label | Linux keycode | Scan code | X11 keysym | Default action |
|---|---|---|---|---|
| Performance mode | *(none)* | — | — | Firmware cycles `/sys/firmware/acpi/platform_profile` silently |
| Camera BG Blur | `KEY_PROG3` (202) | 0x80 | `XF86Launch3` | None |
| Audio / Sound Profile | `KEY_PROG2` (149) | 0x70 | `XF86Launch2` | None |
| Dark Mode toggle | `KEY_PROG1` (148) | 0x71 | `XF86Launch1` | None |

### Function-row secondary keys (Fn+Fx)

| Physical label | Linux keycode | Scan code | Device | Default action |
|---|---|---|---|---|
| Airplane mode | `KEY_RFKILL` (247) | 0x0d | event9 | Kernel handles Wi-Fi toggle |
| Microphone mute | `KEY_F20` (190) | 0x08 | event9 | **None** — does not mute mic on Linux (see note) |
| Lock | `Super+L` composite | — | event3 | *See bug below* |
| Calculator | `KEY_CALC` (140) | — | event3 | Opens calculator app |
| Refresh rate | `KEY_REFRESH_RATE_TOGGLE` (562) | 0x110 | event9 | None |

> **Mic mute note:** The physical mic mute key (F4, or Fn+F4 with Fn Lock on) fires
> `KEY_F20` — not `KEY_MICMUTE`. `KEY_MICMUTE` (248) appears in the device capability
> list but never fires with any physical key (phantom entry). `KEY_F20` has no default
> action on Linux, so the mic mute key does nothing out of the box and requires a custom
> keybinding to toggle PulseAudio/PipeWire and show a notification.

### Other special keys

| Physical label | Linux keycode | Scan code | X11 keysym |
|---|---|---|---|
| Lenovo Star / Favorite | `KEY_FAVORITES` (364) | 0x101 | *(unmapped in X11 — needs xmodmap)* |
| Lenovo Support | `KEY_HELP` (138) | 0x7f | `Help` |

### Phantom capability entries (declared by driver, no physical key fires them)

`KEY_MICMUTE` (248), `KEY_PROG4` (203), `KEY_CAMERA` (212), `KEY_SWITCHVIDEOMODE` (227),
`KEY_F16` (186), `KEY_F22` (192), `KEY_F23` (193), `KEY_TOUCHPAD_TOGGLE` (530),
`KEY_ROOT_MENU` (618), `KEY_UNKNOWN` (240), `KEY_ESC` (1), `KEY_CUT` (137),
keycodes 445, 446, 634.

---

## Kernel support history

These keys were silent (no evdev events) until a patch merged for the Yoga 9
14IAP7 circa Linux 6.1/6.2:

```
platform/x86: ideapad-laptop: support for more special keys in WMI
https://patchwork.kernel.org/project/platform-driver-x86/patch/20221116110647.3438-1-p.jungkamp@gmx.net/
```

WMI event → keycode mapping added by that patch:

| WMI code | Keycode |
|---|---|
| 0x12 | KEY_PROG2 (audio/sound profile) |
| 0x13 | KEY_PROG1 (dark mode) |
| 0x27 | KEY_HELP (Lenovo Support) |
| 0x28 | KEY_PROG3 (virtual background / camera blur) |
| 0x01 | KEY_FAVORITES (star key) |
| 0x0a | KEY_REFRESH_RATE_TOGGLE |

All are available on kernel 6.2+ with no extra configuration.

---

## Performance mode

The performance mode key does **not** emit a Linux keycode. Instead, pressing
it causes the EC to fire query `_Q44`, which updates the ACPI platform profile
directly. The change is detectable via a udev `change` event:

```
SUBSYSTEM=platform-profile
ACTION=change
DEVPATH=.../VPC2004:00/platform-profile/platform-profile-0
```

Current state is readable at:

```bash
cat /sys/firmware/acpi/platform_profile          # low-power | balanced | performance
cat /sys/firmware/acpi/platform_profile_choices  # all available modes
```

To manually switch:
```bash
echo "balanced" | sudo tee /sys/firmware/acpi/platform_profile
```

To react to key presses, write a udev rule on `SUBSYSTEM=="platform-profile",
ACTION=="change"` — no polling required.

### ACPI WMI error spam (known BIOS bug)

Every performance mode keypress logs errors like:

```
ACPI BIOS Error (bug): Could not resolve symbol [\_SB.PC00.LPCB.EC0._Q44.WM00], AE_NOT_FOUND
ACPI Error: Aborting method \_SB.PC00.LPCB.EC0._Q44 due to previous error
```

**What this means:** `_Q44` (EC query for the performance key) tries to call
`WM00` — a WMI notification handler. On Windows, Lenovo Vantage registers this
method. On Linux, the WMI bus driver does not back-register `WM00` into the
ACPI namespace, so the call fails with `AE_NOT_FOUND`.

**Impact:** None — the platform profile still cycles correctly through a
separate code path in `ideapad_laptop`. The errors are purely cosmetic dmesg
noise caused by a Lenovo BIOS assumption that `WM00` always exists.

The same error pattern appears for other special keys:
- `_Q44` → performance mode key
- `_Q11`, `_Q12` → dark mode / audio / camera blur keys

No known workaround short of a kernel patch that stubs `WM00` into the ACPI
namespace.

---

## Bug fixed during investigation

**Problem:** The hardware lock key sends `Super+L`, but Cinnamon's Looking Glass
debugger was bound to `Super+L` by default, so pressing the lock key opened the
debugger instead of locking the screen.

**Fix applied:**
```bash
gsettings set org.cinnamon.desktop.keybindings looking-glass-keybinding "[]"
gsettings set org.cinnamon.desktop.keybindings.media-keys screensaver \
  "['<Control><Alt>l', 'XF86ScreenSaver', '<Super>l']"
```

---

## Remapping

Keys that emit keycodes can be bound via Cinnamon custom shortcuts (gsettings).
`KEY_FAVORITES` has no X11 keysym by default and needs an xmodmap entry first.

See `remap.sh` for an interactive setup menu.

The three most useful candidates for custom bindings:

| Key | Suggested action |
|---|---|
| `KEY_PROG1` / `XF86Launch1` | Toggle dark/light Cinnamon theme |
| `KEY_PROG2` / `XF86Launch2` | Cycle audio output or profile |
| `KEY_PROG3` / `XF86Launch3` | Screenshot, custom app, etc. |
