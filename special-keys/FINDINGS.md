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
| Microphone mute | `KEY_F20` (190) | 0x08 | event9 | Cinnamon handles — toggles mic mute + OSD (see note) |
| Lock | `Super+L` composite | — | event3 | *See bug below* |
| Calculator | `KEY_CALC` (140) | — | event3 | Opens calculator app |
| Refresh rate | `KEY_REFRESH_RATE_TOGGLE` (562) | 0x110 | event9 | None |

> **Mic mute note:** The physical mic mute key (F4, or Fn+F4 with Fn Lock on) fires
> `KEY_F20` — not `KEY_MICMUTE`. `KEY_MICMUTE` (248) appears in the device capability
> list but never fires with any physical key (phantom entry). On Linux Mint Cinnamon,
> `KEY_F20` is handled by the desktop environment — it toggles the microphone mute in
> PulseAudio/PipeWire and shows an OSD notification automatically. No custom setup needed.

### Other special keys

| Physical label | Linux keycode | Scan code | X11 keysym |
|---|---|---|---|
| Lenovo Star / Favorite | `KEY_FAVORITES` (364) | 0x101 | *(evdev code 364 → X11 keycode 372, beyond X11's 8–255 limit — handled via `/dev/input` directly in `yoga-tray`)* |
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

## Refresh rate toggle

The built-in display (eDP-1, SDC 0x4152) runs natively at **2880×1800** with
Cinnamon fractional scaling (scale=2, logical 1440×900). The EDID advertises
both 90Hz and 60Hz for the native resolution:

```
2880x1800     90.00 +  60.00
```

Switching between rates with `xrandr --output eDP-1 --mode 2880x1800 --rate 60`
(or `--rate 90`) does not trigger Cinnamon to recalculate display scaling because
the physical resolution is unchanged. No custom modelines or EDID patches are needed.

`refresh-rate-toggle` handles `KEY_REFRESH_RATE_TOGGLE` (Fn+R) using this approach.

---

## Remapping

Keys that emit standard keycodes (≤255) can be bound via Cinnamon custom shortcuts (gsettings). `KEY_FAVORITES` (364) and `KEY_REFRESH_RATE_TOGGLE` (562) map to X11 keycodes 372 and 570 — both beyond X11's 8–255 limit — so xmodmap cannot reach them. `yoga-tray` reads these directly from `/dev/input`, bypassing X11 entirely.

All five bindable keys are configurable from the `yoga-tray` context menu or the **Yoga Options** companion window (left-click the tray icon). Physical keyboard order top-to-bottom:

| Key | Evdev code | X11 reachable | Binding method |
|---|---|---|---|
| Lenovo Star | `KEY_FAVORITES` (364) | No | evdev direct read |
| Camera Blur | `KEY_PROG3` (202) | Yes | Cinnamon gsettings |
| Audio Profile | `KEY_PROG2` (149) | Yes | Cinnamon gsettings |
| Dark Mode | `KEY_PROG1` (148) | Yes | Cinnamon gsettings |
| Refresh Rate | `KEY_REFRESH_RATE_TOGGLE` (562) | No | evdev direct read |
