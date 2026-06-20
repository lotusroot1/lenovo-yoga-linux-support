# Contributing

This document explains how the project is structured and how to extend it.

---

## Repository layout

```
lenovo-yoga-linux-support/
├── install.sh              # Root orchestrator (sudo) — installs system backends
├── kbd-backlight/          # Keyboard backlight backend + systemd service
├── perf-profile/           # Platform profile backend + sudoers rule
├── special-keys/           # Key investigation findings, toggle scripts, remap tool
│   ├── FINDINGS.md         # Evdev key map, keycodes, known quirks
│   ├── refresh-rate-toggle # Bash script: toggles xrandr between 90Hz and 60Hz
│   └── remap.sh            # Interactive menu: bind any Yoga key via Cinnamon
└── tray-app/               # GTK3 system tray app (yoga-tray)
    ├── yoga-tray           # Single-file Python app
    ├── install.sh          # User install (no sudo) — deploys tray + scripts
    └── uninstall.sh        # User uninstall
```

---

## Adding a new toggle script

Scripts that live in `special-keys/` (or anywhere on `$PATH`) can be launched
from the tray or bound to a hardware key.

1. Write a bash script in `special-keys/`. Follow the pattern in
   `refresh-rate-toggle`: use `set -euo pipefail`, send a `notify-send`
   notification so the user gets feedback.

2. Add it to `tray-app/install.sh` so it lands in `~/.local/bin/`:
   ```bash
   install -m 755 "$SCRIPT_DIR/../special-keys/my-script" "$(dirname "$TRAY_BIN")/my-script"
   ```

3. Remove it again in `tray-app/uninstall.sh`:
   ```bash
   rm -f "$HOME/.local/bin/my-script"
   ```

---

## Adding a preset action to the Key Bindings menu

`PRESET_ACTIONS` in `tray-app/yoga-tray` is a list of `(label, command)` tuples
shown in every key's binding submenu. To add a new preset:

```python
PRESET_ACTIONS = [
    ...
    ('My new action', '/path/to/my-script'),
]
```

The label appears in the submenu for all bindable keys. No other changes needed.

---

## Binding a new hardware key

If a new key is confirmed via `evtest` (see `special-keys/FINDINGS.md` for how):

1. Calculate the X11 keycode: `evdev_keycode + 8`.

2. If the key has no keysym, choose an unused one from the `XF86Launch*` family
   (XF86Launch5–XF86LaunchF are generally free) and add an `_ensure_xmodmap`
   call — see `_on_bind_preset` for the pattern.

3. Add the key to `BINDABLE_KEYS` in `tray-app/yoga-tray`:
   ```python
   BINDABLE_KEYS = [
       ...
       # (id, menu_label, keysym, xmodmap_keycode_or_None, xmodmap_keysym_name_or_None)
       ('mykey', 'My Key', 'XF86Launch6', 571, 'XF86Launch6'),
   ]
   ```
   The tray will automatically show it in the Key Bindings submenu with all
   preset and custom binding options.

4. If you want the key auto-wired on install, add the xmodmap + gsettings block
   to `tray-app/install.sh` following the pattern used for the Refresh Rate key.

5. Document it in `special-keys/FINDINGS.md` and add a handler to
   `special-keys/remap.sh` if a terminal-based setup path is also wanted.

---

## Tray app architecture

`yoga-tray` is a single Python file using GTK3 (`python3-gi`). Key points:

- **`_build_menu()`** constructs the static menu skeleton once at startup.
- **`_on_menu_open()`** is called on every menu open via `GLib.idle_add` and
  refreshes all dynamic state (backlight, profile, refresh rate, key bindings).
- **Polling**: `GLib.timeout_add` drives backlight (500 ms) and profile (500 ms)
  polls so the icon updates without opening the menu. Refresh rate polls every 3 s.
- **Key binding submenus** are fully rebuilt on each menu open so they always
  show the current Cinnamon binding without requiring a restart.
- **gsettings helpers** (`_gs_*` functions) call the `gsettings` CLI rather than
  using the Python GSettings API, keeping the code simple and avoiding schema
  compilation requirements.
- **`_ensure_xmodmap`** applies the keycode→keysym mapping immediately via
  `xmodmap` and appends it to `~/.Xmodmap` for persistence across X restarts.

---

## Running locally

```bash
# Install system backends first (once)
sudo ./install.sh

# Install and launch the tray
./tray-app/install.sh
~/.local/bin/yoga-tray &
```

Logs go to stderr. To debug key binding calls, run with the terminal open and
watch for Python tracebacks.
