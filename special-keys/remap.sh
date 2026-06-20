#!/usr/bin/env bash
# Lenovo Yoga 9i Gen 7 — special key remapper
# Binds the unmapped top-row keys to common Cinnamon actions via gsettings.
# Run without sudo; does not require extra packages beyond a standard Mint install.
set -euo pipefail

# ── key definitions ───────────────────────────────────────────────────────────

declare -A KEY_LABEL=(
    [prog1]="Dark Mode key       (KEY_PROG1 / XF86Launch1)"
    [prog2]="Audio Profile key   (KEY_PROG2 / XF86Launch2)"
    [prog3]="Camera Blur key     (KEY_PROG3 / XF86Launch3)"
    [fav]="Lenovo Star/Fav key  (KEY_FAVORITES)"
    [help]="Lenovo Support key   (KEY_HELP)"
)

declare -A KEY_KEYSYM=(
    [prog1]="XF86Launch1"
    [prog2]="XF86Launch2"
    [prog3]="XF86Launch3"
    [fav]="XF86Favorites"     # requires xmodmap entry — handled below
    [help]="Help"
)

# KEY_FAVORITES (evdev 364 → X11 keycode 372) has no keysym by default.
# We assign XF86Favorites via xmodmap, persisted in ~/.Xmodmap.
ensure_favorites_keysym() {
    if ! xmodmap -pk 2>/dev/null | grep -q "XF86Favorites"; then
        xmodmap -e "keycode 372 = XF86Favorites" 2>/dev/null || true
        local xmod="$HOME/.Xmodmap"
        if ! grep -q "keycode 372" "$xmod" 2>/dev/null; then
            echo "keycode 372 = XF86Favorites" >> "$xmod"
            echo "  → Added keycode 372 = XF86Favorites to ~/.Xmodmap (loaded at login)"
        fi
    fi
}

# ── action definitions ────────────────────────────────────────────────────────

print_actions() {
    echo ""
    echo "  Common actions:"
    echo "   1) Toggle dark / light Cinnamon theme"
    echo "   2) Full screenshot (gnome-screenshot)"
    echo "   3) Area screenshot (gnome-screenshot --area)"
    echo "   4) Open file manager (nemo)"
    echo "   5) Open terminal (xterm / x-terminal-emulator)"
    echo "   6) Cycle performance mode (platform_profile)"
    echo "   7) Custom command (you type it)"
    echo "   8) Show current binding"
    echo "   9) Clear / remove binding"
    echo "   0) Back"
    echo ""
}

action_command() {
    local choice="$1"
    case "$choice" in
        1) echo 'bash -c '"'"'t=$(gsettings get org.cinnamon.desktop.interface gtk-theme); if echo "$t"|grep -qi dark; then gsettings set org.cinnamon.desktop.interface gtk-theme "Mint-Y"; else gsettings set org.cinnamon.desktop.interface gtk-theme "Mint-Y-Dark"; fi'"'" ;;
        2) echo "gnome-screenshot" ;;
        3) echo "gnome-screenshot --area" ;;
        4) echo "nemo" ;;
        5) echo "x-terminal-emulator" ;;
        6) echo 'bash -c '"'"'p=/sys/firmware/acpi/platform_profile; c=$(cat $p); case $c in low-power) echo balanced|sudo tee $p;; balanced) echo performance|sudo tee $p;; *) echo low-power|sudo tee $p;; esac'"'" ;;
        7) read -rp "  Enter command: " cmd; echo "$cmd" ;;
        *) echo "" ;;
    esac
}

action_label() {
    local choice="$1"
    case "$choice" in
        1) echo "Toggle dark/light theme" ;;
        2) echo "Full screenshot" ;;
        3) echo "Area screenshot" ;;
        4) echo "Open file manager" ;;
        5) echo "Open terminal" ;;
        6) echo "Cycle performance mode" ;;
        7) echo "Custom command" ;;
        *) echo "?" ;;
    esac
}

# ── cinnamon gsettings helpers ────────────────────────────────────────────────

# Returns the slot name (e.g. "custom3") for a given keysym, or "" if not bound.
find_slot_for_keysym() {
    local ksym="$1"
    local list
    list=$(gsettings get org.cinnamon.desktop.keybindings custom-list 2>/dev/null | tr -d "[]' " | tr ',' '\n')
    for slot in $list; do
        [ -z "$slot" ] && continue
        local path="/org/cinnamon/desktop/keybindings/custom-keybindings/$slot/"
        local binding
        binding=$(gsettings get "org.cinnamon.desktop.keybindings.custom-keybindings:$path" binding 2>/dev/null)
        if echo "$binding" | grep -q "$ksym"; then
            echo "$slot"
            return
        fi
    done
    echo ""
}

# Returns the next available slot name (custom0, custom1, …)
next_free_slot() {
    local list
    list=$(gsettings get org.cinnamon.desktop.keybindings custom-list 2>/dev/null | tr -d "[]' " | tr ',' '\n')
    local i=0
    while true; do
        local candidate="custom$i"
        if ! echo "$list" | grep -qx "$candidate"; then
            echo "$candidate"
            return
        fi
        ((i++))
    done
}

show_binding() {
    local ksym="$1"
    local slot
    slot=$(find_slot_for_keysym "$ksym")
    if [ -z "$slot" ]; then
        echo "  (not bound)"
    else
        local path="/org/cinnamon/desktop/keybindings/custom-keybindings/$slot/"
        local name cmd
        name=$(gsettings get "org.cinnamon.desktop.keybindings.custom-keybindings:$path" name 2>/dev/null | tr -d "'")
        cmd=$(gsettings get  "org.cinnamon.desktop.keybindings.custom-keybindings:$path" command 2>/dev/null | tr -d "'")
        echo "  Bound [$slot]: \"$name\" → $cmd"
    fi
}

set_binding() {
    local ksym="$1" label="$2" cmd="$3"
    local slot
    slot=$(find_slot_for_keysym "$ksym")
    if [ -z "$slot" ]; then
        slot=$(next_free_slot)
        # Add to list
        local current
        current=$(gsettings get org.cinnamon.desktop.keybindings custom-list 2>/dev/null | tr -d "@as")
        # Remove empty array markers and rebuild
        local new_list
        if [ "$current" = "[]" ] || [ -z "$(echo "$current" | tr -d "[]' ")" ]; then
            new_list="['$slot']"
        else
            new_list=$(echo "$current" | sed "s/]$/, '$slot']/")
        fi
        gsettings set org.cinnamon.desktop.keybindings custom-list "$new_list"
    fi
    local path="/org/cinnamon/desktop/keybindings/custom-keybindings/$slot/"
    gsettings set "org.cinnamon.desktop.keybindings.custom-keybindings:$path" name "$label"
    gsettings set "org.cinnamon.desktop.keybindings.custom-keybindings:$path" command "$cmd"
    gsettings set "org.cinnamon.desktop.keybindings.custom-keybindings:$path" binding "['$ksym']"
    echo "  → Bound $ksym to: $cmd"
}

clear_binding() {
    local ksym="$1"
    local slot
    slot=$(find_slot_for_keysym "$ksym")
    if [ -z "$slot" ]; then
        echo "  (nothing to clear)"
        return
    fi
    local path="/org/cinnamon/desktop/keybindings/custom-keybindings/$slot/"
    gsettings set "org.cinnamon.desktop.keybindings.custom-keybindings:$path" binding "[]"
    # Remove from list
    local current new_list
    current=$(gsettings get org.cinnamon.desktop.keybindings custom-list 2>/dev/null)
    new_list=$(echo "$current" | sed "s/'$slot', //g; s/, '$slot'//g; s/'$slot'//g")
    gsettings set org.cinnamon.desktop.keybindings custom-list "$new_list"
    echo "  → Cleared binding for $ksym"
}

# ── key submenu ───────────────────────────────────────────────────────────────

handle_key() {
    local key="$1"
    local ksym="${KEY_KEYSYM[$key]}"
    local label="${KEY_LABEL[$key]}"

    [ "$key" = "fav" ] && ensure_favorites_keysym

    while true; do
        echo ""
        echo "── $label ──"
        show_binding "$ksym"
        print_actions
        read -rp "  Choice: " choice
        case "$choice" in
            [1-7])
                local cmd alabel
                cmd=$(action_command "$choice")
                alabel=$(action_label "$choice")
                [ -z "$cmd" ] && echo "  Cancelled." && continue
                set_binding "$ksym" "$alabel" "$cmd"
                ;;
            8) show_binding "$ksym" ;;
            9) clear_binding "$ksym" ;;
            0) return ;;
            *) echo "  Invalid choice." ;;
        esac
    done
}

# ── main menu ─────────────────────────────────────────────────────────────────

main() {
    echo ""
    echo "╔═══════════════════════════════════════════════╗"
    echo "║  Lenovo Yoga 9i — Special Key Remapper        ║"
    echo "║  Binds to Cinnamon custom keyboard shortcuts  ║"
    echo "╚═══════════════════════════════════════════════╝"
    echo ""
    echo "  Keys you can configure:"
    echo ""
    local i=1
    local keys=(prog1 prog2 prog3 fav help)
    for key in "${keys[@]}"; do
        local ksym="${KEY_KEYSYM[$key]}"
        local current
        current=$(find_slot_for_keysym "$ksym" 2>/dev/null)
        local status="not bound"
        if [ -n "$current" ]; then
            local p="/org/cinnamon/desktop/keybindings/custom-keybindings/$current/"
            status=$(gsettings get "org.cinnamon.desktop.keybindings.custom-keybindings:$p" name 2>/dev/null | tr -d "'" || echo "bound")
        fi
        printf "   %d) %-50s [%s]\n" "$i" "${KEY_LABEL[$key]}" "$status"
        ((i++))
    done
    echo ""
    echo "   q) Quit"
    echo ""

    read -rp "  Select key to configure: " choice
    case "$choice" in
        1) handle_key prog1 ;;
        2) handle_key prog2 ;;
        3) handle_key prog3 ;;
        4) handle_key fav ;;
        5) handle_key help ;;
        q|Q) echo ""; exit 0 ;;
        *) echo "  Invalid choice." ;;
    esac

    main
}

main
