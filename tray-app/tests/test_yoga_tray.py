import io
import os
import struct
import subprocess
import unittest.mock as mock

import pytest
import yoga_tray


# ── _cmd_basename ─────────────────────────────────────────────────────────────

class TestCmdBasename:
    def test_simple(self):
        assert yoga_tray._cmd_basename('gnome-screenshot') == 'gnome-screenshot'

    def test_args_stripped(self):
        assert yoga_tray._cmd_basename('gnome-screenshot --area') == 'gnome-screenshot'

    def test_absolute_path(self):
        assert yoga_tray._cmd_basename('/usr/bin/gnome-screenshot --area') == 'gnome-screenshot'

    def test_tilde_path(self):
        assert yoga_tray._cmd_basename('~/.local/bin/refresh-rate-toggle --silent') == 'refresh-rate-toggle'

    def test_empty_string(self):
        assert yoga_tray._cmd_basename('') == ''

    def test_unclosed_quote_returns_empty(self):
        assert yoga_tray._cmd_basename("echo 'unclosed") == ''


# ── _parse_gs_list ────────────────────────────────────────────────────────────

class TestParseGsList:
    def test_empty_brackets(self):
        assert yoga_tray._parse_gs_list('[]') == []

    def test_at_as_empty(self):
        assert yoga_tray._parse_gs_list('@as []') == []

    def test_empty_string(self):
        assert yoga_tray._parse_gs_list('') == []

    def test_single_item(self):
        assert yoga_tray._parse_gs_list("['custom0']") == ['custom0']

    def test_multiple_items(self):
        assert yoga_tray._parse_gs_list("['custom0', 'custom1', 'custom2']") == [
            'custom0', 'custom1', 'custom2',
        ]

    def test_whitespace_is_stripped(self):
        assert yoga_tray._parse_gs_list("  [ 'custom0' ]  ") == ['custom0']


# ── _load_timing ──────────────────────────────────────────────────────────────

class TestLoadTiming:
    def test_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        assert yoga_tray._load_timing() == yoga_tray._TIMING_DEFAULTS

    def test_valid_override(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'timing.conf').write_text('display_interval_ms = 2000\n')
        t = yoga_tray._load_timing()
        assert t['display_interval_ms'] == 2000
        assert t['performance_interval_ms'] == yoga_tray._TIMING_DEFAULTS['performance_interval_ms']

    def test_multiple_overrides(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'timing.conf').write_text(
            'display_interval_ms = 2000\n'
            'performance_interval_ms = 750\n'
        )
        t = yoga_tray._load_timing()
        assert t['display_interval_ms'] == 2000
        assert t['performance_interval_ms'] == 750

    def test_rejects_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'timing.conf').write_text('display_interval_ms = 0\n')
        assert yoga_tray._load_timing()['display_interval_ms'] == yoga_tray._TIMING_DEFAULTS['display_interval_ms']

    def test_rejects_negative(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'timing.conf').write_text('display_interval_ms = -500\n')
        assert yoga_tray._load_timing()['display_interval_ms'] == yoga_tray._TIMING_DEFAULTS['display_interval_ms']

    def test_ignores_unknown_keys(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'timing.conf').write_text('unknown_key = 9999\n')
        t = yoga_tray._load_timing()
        assert 'unknown_key' not in t
        assert t == yoga_tray._TIMING_DEFAULTS

    def test_ignores_comment_lines(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'timing.conf').write_text('# display_interval_ms = 9999\n')
        assert yoga_tray._load_timing()['display_interval_ms'] == yoga_tray._TIMING_DEFAULTS['display_interval_ms']

    def test_ignores_non_integer_values(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'timing.conf').write_text('display_interval_ms = fast\n')
        assert yoga_tray._load_timing()['display_interval_ms'] == yoga_tray._TIMING_DEFAULTS['display_interval_ms']


# ── load_pref / save_pref ─────────────────────────────────────────────────────

class TestPrefs:
    def test_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        yoga_tray.save_pref('key', 'value')
        assert yoga_tray.load_pref('key') == 'value'

    def test_missing_returns_explicit_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        assert yoga_tray.load_pref('missing', 'fallback') == 'fallback'

    def test_missing_returns_empty_string_by_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        assert yoga_tray.load_pref('missing') == ''

    def test_save_creates_config_dir(self, tmp_path, monkeypatch):
        subdir = tmp_path / 'newdir'
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(subdir))
        yoga_tray.save_pref('k', 'v')
        assert (subdir / 'k').read_text() == 'v'

    def test_save_overwrites_existing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        yoga_tray.save_pref('k', 'first')
        yoga_tray.save_pref('k', 'second')
        assert yoga_tray.load_pref('k') == 'second'

    def test_load_strips_surrounding_whitespace(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'k').write_text('  value  \n')
        assert yoga_tray.load_pref('k') == 'value'


# ── read_sysfs_brightness ─────────────────────────────────────────────────────

class TestReadSysfsBrightness:
    def test_reads_integer_value(self, tmp_path, monkeypatch):
        f = tmp_path / 'brightness'
        f.write_text('3\n')
        monkeypatch.setattr(yoga_tray, 'SYSFS_BRIGHTNESS', str(f))
        assert yoga_tray.read_sysfs_brightness() == 3

    def test_returns_zero(self, tmp_path, monkeypatch):
        f = tmp_path / 'brightness'
        f.write_text('0\n')
        monkeypatch.setattr(yoga_tray, 'SYSFS_BRIGHTNESS', str(f))
        assert yoga_tray.read_sysfs_brightness() == 0

    def test_missing_file_returns_sentinel(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'SYSFS_BRIGHTNESS', str(tmp_path / 'missing'))
        assert yoga_tray.read_sysfs_brightness() == -1

    def test_non_integer_content_returns_sentinel(self, tmp_path, monkeypatch):
        f = tmp_path / 'brightness'
        f.write_text('not-a-number\n')
        monkeypatch.setattr(yoga_tray, 'SYSFS_BRIGHTNESS', str(f))
        assert yoga_tray.read_sysfs_brightness() == -1


# ── read_profile ──────────────────────────────────────────────────────────────

class TestReadProfile:
    def test_reads_profile(self, tmp_path, monkeypatch):
        f = tmp_path / 'platform_profile'
        f.write_text('balanced\n')
        monkeypatch.setattr(yoga_tray, 'SYSFS_PROFILE', str(f))
        assert yoga_tray.read_profile() == 'balanced'

    def test_strips_whitespace(self, tmp_path, monkeypatch):
        f = tmp_path / 'platform_profile'
        f.write_text('  performance  \n')
        monkeypatch.setattr(yoga_tray, 'SYSFS_PROFILE', str(f))
        assert yoga_tray.read_profile() == 'performance'

    def test_missing_file_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'SYSFS_PROFILE', str(tmp_path / 'missing'))
        assert yoga_tray.read_profile() is None


# ── is_autostart_enabled / set_autostart ─────────────────────────────────────

class TestAutostart:
    def test_not_enabled_by_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'TRAY_DESKTOP', str(tmp_path / 'tray.desktop'))
        assert yoga_tray.is_autostart_enabled() is False

    def test_enabled_after_set_true(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'TRAY_DESKTOP', str(tmp_path / 'tray.desktop'))
        yoga_tray.set_autostart(True)
        assert yoga_tray.is_autostart_enabled() is True

    def test_disabled_after_set_false(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'TRAY_DESKTOP', str(tmp_path / 'tray.desktop'))
        yoga_tray.set_autostart(True)
        yoga_tray.set_autostart(False)
        assert yoga_tray.is_autostart_enabled() is False

    def test_desktop_file_contains_required_fields(self, tmp_path, monkeypatch):
        desktop = tmp_path / 'tray.desktop'
        monkeypatch.setattr(yoga_tray, 'TRAY_DESKTOP', str(desktop))
        yoga_tray.set_autostart(True)
        content = desktop.read_text()
        assert 'Type=Application' in content
        assert 'X-GNOME-Autostart-enabled=true' in content


# ── get_refresh_rate ──────────────────────────────────────────────────────────

from types import SimpleNamespace


def _patch_xlib(monkeypatch, rate_hz, active=True):
    """Wire up minimal python-xlib fakes so _get_refresh_rate_x11 returns rate_hz."""
    mode = SimpleNamespace(id=rate_hz, dot_clock=rate_hz, h_total=1, v_total=1)
    resources = SimpleNamespace(modes=[mode], crtcs=[1], config_timestamp=0)
    crtc = SimpleNamespace(mode=rate_hz if active else 0)
    screen = SimpleNamespace(root=object())
    display_inst = SimpleNamespace(screen=lambda: screen)

    monkeypatch.setattr(yoga_tray, '_HAS_XLIB', True)
    monkeypatch.setattr(yoga_tray, '_IS_WAYLAND', False)
    monkeypatch.setattr(yoga_tray._xlib_display, 'Display', lambda: display_inst)
    monkeypatch.setattr(yoga_tray._xlib_randr, 'get_screen_resources_current', lambda r: resources)
    monkeypatch.setattr(yoga_tray._xlib_randr, 'get_crtc_info', lambda r, c, t: crtc)


class TestGetRefreshRate:
    def test_detects_90hz(self, monkeypatch):
        _patch_xlib(monkeypatch, 90)
        assert yoga_tray.get_refresh_rate() == 90

    def test_detects_60hz(self, monkeypatch):
        _patch_xlib(monkeypatch, 60)
        assert yoga_tray.get_refresh_rate() == 60

    def test_85hz_rounds_up_to_90(self, monkeypatch):
        _patch_xlib(monkeypatch, 85)
        assert yoga_tray.get_refresh_rate() == 90

    def test_84hz_rounds_down_to_60(self, monkeypatch):
        _patch_xlib(monkeypatch, 84)
        assert yoga_tray.get_refresh_rate() == 60

    def test_returns_none_when_no_active_mode(self, monkeypatch):
        _patch_xlib(monkeypatch, 90, active=False)
        monkeypatch.setattr(subprocess, 'check_output', lambda *a, **kw: '')
        assert yoga_tray._get_refresh_rate_x11() is None

    def test_returns_none_on_xlib_error(self, monkeypatch):
        def raise_xlib(): raise RuntimeError('xlib failed')
        monkeypatch.setattr(yoga_tray, '_HAS_XLIB', True)
        monkeypatch.setattr(yoga_tray, '_IS_WAYLAND', False)
        monkeypatch.setattr(yoga_tray._xlib_display, 'Display', raise_xlib)
        monkeypatch.setattr(subprocess, 'check_output',
                            lambda *a, **kw: (_ for _ in ()).throw(subprocess.SubprocessError()))
        assert yoga_tray._get_refresh_rate_x11() is None

    def test_fallback_to_subprocess_when_no_xlib(self, monkeypatch):
        monkeypatch.setattr(yoga_tray, '_HAS_XLIB', False)
        monkeypatch.setattr(yoga_tray, '_IS_WAYLAND', False)
        monkeypatch.setattr(subprocess, 'check_output',
                            lambda *a, **kw: "   2880x1800     90.00*+  60.00  \n")
        assert yoga_tray._get_refresh_rate_x11() == 90

    def test_dispatches_to_wayland(self, monkeypatch):
        monkeypatch.setattr(yoga_tray, '_IS_WAYLAND', True)
        monkeypatch.setattr(yoga_tray, '_get_refresh_rate_wayland', lambda: 60)
        assert yoga_tray.get_refresh_rate() == 60


# ── _find_ideapad_device ──────────────────────────────────────────────────────

_PROC_WITH_IDEAPAD = (
    "I: Bus=0018 Vendor=0000\n"
    "N: Name=\"Ideapad extra buttons\"\n"
    "H: Handlers=sysrq kbd event9 rfkill\n"
    "\n"
    "I: Bus=0011 Vendor=0001\n"
    "N: Name=\"AT Translated Set 2 keyboard\"\n"
    "H: Handlers=sysrq kbd event3\n"
)
_PROC_WITHOUT_IDEAPAD = (
    "I: Bus=0011 Vendor=0001\n"
    "N: Name=\"AT Translated Set 2 keyboard\"\n"
    "H: Handlers=sysrq kbd event3\n"
)


class TestFindIdeapadDevice:
    def test_finds_device(self):
        with mock.patch('builtins.open', mock.mock_open(read_data=_PROC_WITH_IDEAPAD)):
            assert yoga_tray._find_ideapad_device() == '/dev/input/event9'

    def test_extracts_correct_event_number(self):
        content = "N: Name=\"Ideapad extra buttons\"\nH: Handlers=kbd event12\n\n"
        with mock.patch('builtins.open', mock.mock_open(read_data=content)):
            assert yoga_tray._find_ideapad_device() == '/dev/input/event12'

    def test_returns_none_when_device_absent(self):
        with mock.patch('builtins.open', mock.mock_open(read_data=_PROC_WITHOUT_IDEAPAD)):
            assert yoga_tray._find_ideapad_device() is None

    def test_returns_none_on_file_error(self):
        with mock.patch('builtins.open', side_effect=OSError('no such file')):
            assert yoga_tray._find_ideapad_device() is None


# ── gsettings helpers ─────────────────────────────────────────────────────────

class TestGsettingsHelpers:
    def test_gs_find_slot_found(self, monkeypatch):
        outputs = iter(["['custom0']\n", "['XF86Launch1']\n"])
        monkeypatch.setattr(subprocess, 'check_output', lambda *a, **kw: next(outputs))
        assert yoga_tray._gs_find_slot('XF86Launch1') == 'custom0'

    def test_gs_find_slot_not_found(self, monkeypatch):
        outputs = iter(["['custom0']\n", "['XF86Launch2']\n"])
        monkeypatch.setattr(subprocess, 'check_output', lambda *a, **kw: next(outputs))
        assert yoga_tray._gs_find_slot('XF86Launch1') is None

    def test_gs_find_slot_empty_list(self, monkeypatch):
        monkeypatch.setattr(subprocess, 'check_output', lambda *a, **kw: "[]\n")
        assert yoga_tray._gs_find_slot('XF86Launch1') is None

    def test_gs_find_slot_subprocess_error(self, monkeypatch):
        def raise_err(*a, **kw): raise subprocess.SubprocessError()
        monkeypatch.setattr(subprocess, 'check_output', raise_err)
        assert yoga_tray._gs_find_slot('XF86Launch1') is None

    def test_gs_next_slot_empty_list(self, monkeypatch):
        monkeypatch.setattr(subprocess, 'check_output', lambda *a, **kw: "[]\n")
        assert yoga_tray._gs_next_slot() == 'custom0'

    def test_gs_next_slot_skips_existing(self, monkeypatch):
        monkeypatch.setattr(subprocess, 'check_output',
                            lambda *a, **kw: "['custom0', 'custom1']\n")
        assert yoga_tray._gs_next_slot() == 'custom2'

    def test_gs_get_binding_found(self, monkeypatch):
        outputs = iter([
            "['custom0']\n",     # _gs_find_slot: custom-list
            "['XF86Launch1']\n", # _gs_find_slot: binding check
            "'Dark Mode'\n",     # _gs_get_binding: name
            "'toggle.sh'\n",     # _gs_get_binding: command
        ])
        monkeypatch.setattr(subprocess, 'check_output', lambda *a, **kw: next(outputs))
        name, cmd = yoga_tray._gs_get_binding('XF86Launch1')
        assert name == 'Dark Mode'
        assert cmd == 'toggle.sh'

    def test_gs_get_binding_not_found(self, monkeypatch):
        monkeypatch.setattr(subprocess, 'check_output', lambda *a, **kw: "[]\n")
        name, cmd = yoga_tray._gs_get_binding('XF86Launch1')
        assert name is None
        assert cmd is None


# ── TraySection change-detection logic ───────────────────────────────────────

class _StubSection(yoga_tray.TraySection):
    def __init__(self, state_sequence):
        super().__init__()
        self._sequence     = iter(state_sequence)
        self.display_calls = []

    def read_state(self):
        return next(self._sequence)

    def update_display(self, state):
        self.display_calls.append(state)

    def build_menu_items(self):
        return []

    def notify_info(self, state):
        return ('Title', str(state), 'icon') if state is not None else None


def _stub(states, notifications=False):
    sec = _StubSection(states)
    sec._tray = mock.MagicMock()
    sec._tray.notifications_enabled = notifications
    return sec


class TestTraySectionLogic:
    def test_first_refresh_sets_state_and_calls_display(self):
        sec = _stub(['balanced'])
        sec.refresh()
        assert sec._last_state == 'balanced'
        assert sec.display_calls == ['balanced']

    def test_no_redraw_on_unchanged_state(self):
        sec = _stub(['balanced', 'balanced'])
        sec.refresh()
        sec.refresh()
        assert sec.display_calls == ['balanced']

    def test_redraw_on_state_change(self):
        sec = _stub(['balanced', 'performance'])
        sec.refresh()
        sec.refresh()
        assert sec.display_calls == ['balanced', 'performance']

    def test_no_notify_on_first_read(self):
        sec = _stub(['balanced'], notifications=True)
        sec.refresh()
        sec._tray.queue_notify.assert_not_called()

    def test_notify_queued_on_subsequent_change(self):
        sec = _stub(['balanced', 'performance'], notifications=True)
        sec.refresh()
        sec.refresh()
        sec._tray.queue_notify.assert_called_once_with(sec)

    def test_apply_change_updates_last_state(self):
        sec = _stub([])
        sec._tray.notifications_enabled = False
        sec._last_state = 'balanced'
        sec._do_apply = mock.MagicMock(return_value=True)
        sec.apply_change('performance')
        assert sec._last_state == 'performance'
        assert sec.display_calls == ['performance']

    def test_apply_change_suppresses_next_poll_notify(self):
        sec = _stub(['performance'], notifications=True)
        sec._last_state = 'balanced'
        sec._do_apply = mock.MagicMock(return_value=True)
        sec.apply_change('performance')
        sec.refresh()  # poll sees 'performance' == _last_state → no notify
        sec._tray.queue_notify.assert_not_called()

    def test_apply_change_noop_when_do_apply_fails(self):
        sec = _stub([])
        sec._tray.notifications_enabled = False
        sec._last_state = 'balanced'
        sec._do_apply = mock.MagicMock(return_value=False)
        sec.apply_change('performance')
        assert sec._last_state == 'balanced'
        assert sec.display_calls == []

    def test_lone_failure_reading_is_ignored(self):
        sec = _stub(['performance', None, 'performance'])
        sec.refresh()  # establishes 'performance'
        sec.refresh()  # lone glitch — should be absorbed
        sec.refresh()  # recovers to the same value — no-op
        assert sec.display_calls == ['performance']
        assert sec._last_state == 'performance'

    def test_sustained_failure_is_accepted_after_debounce(self):
        sec = _stub(['performance', None, None])
        sec.refresh()
        sec.refresh()  # 1st failure — absorbed
        sec.refresh()  # 2nd consecutive failure — accepted as real
        assert sec.display_calls == ['performance', None]
        assert sec._last_state is None

    def test_failure_debounce_does_not_suppress_real_changes(self):
        sec = _stub(['balanced', 'performance', 'quiet'])
        sec.refresh()
        sec.refresh()
        sec.refresh()
        assert sec.display_calls == ['balanced', 'performance', 'quiet']


# ── KeyBindingsSection._run_key_cmd ──────────────────────────────────────────

class TestRunKeyCmd:
    def test_executes_command(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        yoga_tray.save_pref('fav-cmd', 'echo hello')
        sec = mock.MagicMock()
        with mock.patch('subprocess.Popen') as mock_popen:
            result = yoga_tray.KeyBindingsSection._run_key_cmd(sec, 'fav')
        mock_popen.assert_called_once_with(['echo', 'hello'])
        assert result is False

    def test_skips_empty_command(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        yoga_tray.save_pref('fav-cmd', '')
        sec = mock.MagicMock()
        with mock.patch('subprocess.Popen') as mock_popen:
            yoga_tray.KeyBindingsSection._run_key_cmd(sec, 'fav')
        mock_popen.assert_not_called()

    def test_malformed_command_does_not_raise(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        yoga_tray.save_pref('fav-cmd', "echo 'unclosed quote")
        sec = mock.MagicMock()
        with mock.patch('subprocess.Popen') as mock_popen:
            yoga_tray.KeyBindingsSection._run_key_cmd(sec, 'fav')
        mock_popen.assert_not_called()


# ── KeyBindingsSection._commit / _on_clear_binding ───────────────────────────

class TestKeyBindingCommit:
    def test_evdev_saves_cmd_and_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        sec = mock.MagicMock()
        with mock.patch.object(yoga_tray.KeyBindingsSection, '_update_key_item'):
            yoga_tray.KeyBindingsSection._commit(
                sec, 'fav', None, yoga_tray._KEY_FAVORITES,
                'Area screenshot', 'gnome-screenshot --area',
            )
        assert yoga_tray.load_pref('fav-cmd') == 'gnome-screenshot --area'
        assert yoga_tray.load_pref('fav-name') == 'Area screenshot'

    def test_clear_wipes_cmd_and_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        yoga_tray.save_pref('fav-cmd', 'gnome-screenshot --area')
        yoga_tray.save_pref('fav-name', 'Area screenshot')
        sec = mock.MagicMock()
        with mock.patch.object(yoga_tray.KeyBindingsSection, '_update_key_item'):
            yoga_tray.KeyBindingsSection._on_clear_binding(
                sec, None, 'fav', None, yoga_tray._KEY_FAVORITES,
            )
        assert yoga_tray.load_pref('fav-cmd') == ''
        assert yoga_tray.load_pref('fav-name') == ''


# ── YogaTray notification batching ────────────────────────────────────────────

def _fake_tray():
    t = mock.MagicMock()
    t._pending_notifs     = {}
    t._notify_timer       = None
    t._notify_debounce_ms = 1500
    return t


class TestNotificationBatching:
    def test_queue_starts_timer_on_first_change(self):
        tray = _fake_tray()
        sec  = mock.MagicMock()
        with mock.patch.object(yoga_tray.GLib, 'timeout_add', return_value=42) as mock_timer:
            yoga_tray.YogaTray.queue_notify(tray, sec)
        mock_timer.assert_called_once()
        assert id(sec) in tray._pending_notifs

    def test_queue_does_not_restart_timer_for_second_section(self):
        tray = _fake_tray()
        sec1, sec2 = mock.MagicMock(), mock.MagicMock()
        with mock.patch.object(yoga_tray.GLib, 'timeout_add', return_value=42) as mock_timer:
            yoga_tray.YogaTray.queue_notify(tray, sec1)
            tray._notify_timer = 42
            yoga_tray.YogaTray.queue_notify(tray, sec2)
        assert mock_timer.call_count == 1
        assert id(sec1) in tray._pending_notifs
        assert id(sec2) in tray._pending_notifs

    def test_fire_single_section_uses_section_title(self):
        tray = _fake_tray()
        sec  = mock.MagicMock()
        sec._last_state = 'balanced'
        sec.notify_info.return_value = ('Profile', 'Balanced', 'icon')
        tray._pending_notifs[id(sec)] = sec
        with mock.patch.object(yoga_tray, 'Notify') as mock_notify:
            yoga_tray.YogaTray._fire_combined_notify(tray)
        mock_notify.Notification.new.assert_called_once_with('Profile', 'Balanced', 'icon')

    def test_fire_multiple_sections_uses_yoga_status_title(self):
        tray = _fake_tray()
        sec1, sec2 = mock.MagicMock(), mock.MagicMock()
        sec1._last_state = 'balanced'
        sec1.notify_info.return_value = ('Profile', 'Balanced', 'i1')
        sec2._last_state = 60
        sec2.notify_info.return_value = ('Refresh Rate', '60 Hz', 'i2')
        tray._pending_notifs = {id(sec1): sec1, id(sec2): sec2}
        with mock.patch.object(yoga_tray, 'Notify') as mock_notify:
            yoga_tray.YogaTray._fire_combined_notify(tray)
        title, body, _ = mock_notify.Notification.new.call_args[0]
        assert title == 'Yoga Status'
        assert 'Profile: Balanced' in body
        assert 'Refresh Rate: 60 Hz' in body

    def test_fire_clears_pending_notifs(self):
        tray = _fake_tray()
        sec  = mock.MagicMock()
        sec._last_state = 'x'
        sec.notify_info.return_value = ('T', 'B', 'I')
        tray._pending_notifs[id(sec)] = sec
        with mock.patch.object(yoga_tray, 'Notify'):
            yoga_tray.YogaTray._fire_combined_notify(tray)
        assert tray._pending_notifs == {}

    def test_fire_skips_section_with_none_notify_info(self):
        tray = _fake_tray()
        sec  = mock.MagicMock()
        sec._last_state = None
        sec.notify_info.return_value = None
        tray._pending_notifs[id(sec)] = sec
        with mock.patch.object(yoga_tray, 'Notify') as mock_notify:
            yoga_tray.YogaTray._fire_combined_notify(tray)
        mock_notify.Notification.new.assert_not_called()


# ── main() PID guard ──────────────────────────────────────────────────────────

class TestPidGuard:
    def test_exits_if_process_is_running(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'yoga-tray.pid').write_text(str(os.getpid()))
        with pytest.raises(SystemExit) as exc:
            yoga_tray.main()
        assert exc.value.code == 0

    def test_continues_with_stale_pid(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'yoga-tray.pid').write_text('999999999')
        with mock.patch.object(yoga_tray, 'YogaTray'), \
             mock.patch.object(yoga_tray.Gtk, 'main'):
            yoga_tray.main()

    def test_pid_file_removed_on_clean_exit(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yoga_tray, 'CONFIG_DIR', str(tmp_path))
        with mock.patch.object(yoga_tray, 'YogaTray'), \
             mock.patch.object(yoga_tray.Gtk, 'main'):
            yoga_tray.main()
        assert not (tmp_path / 'yoga-tray.pid').exists()


# ── evdev struct parsing ──────────────────────────────────────────────────────

def _pack_event(ev_type, code, value):
    return struct.pack(yoga_tray._EVDEV_FMT, 0, 0, ev_type, code, value)


class TestEvdevStructParsing:
    def _run(self, raw_bytes):
        sec = mock.MagicMock(spec=yoga_tray.KeyBindingsSection)
        buf = io.BytesIO(raw_bytes)
        with mock.patch('builtins.open', return_value=buf), \
             mock.patch.object(yoga_tray.GLib, 'idle_add') as mock_idle:
            yoga_tray.KeyBindingsSection._evdev_loop(sec, '/dev/input/event9')
        return sec, mock_idle

    def test_key_favorites_dispatches_fav(self):
        data = _pack_event(yoga_tray._EV_KEY, yoga_tray._KEY_FAVORITES, 1)
        sec, mock_idle = self._run(data)
        mock_idle.assert_called_once_with(sec._run_key_cmd, 'fav')

    def test_key_refresh_dispatches_refresh(self):
        data = _pack_event(yoga_tray._EV_KEY, yoga_tray._KEY_REFRESH_RATE_TOGGLE, 1)
        sec, mock_idle = self._run(data)
        mock_idle.assert_called_once_with(sec._run_key_cmd, 'refresh')

    def test_key_up_event_ignored(self):
        data = _pack_event(yoga_tray._EV_KEY, yoga_tray._KEY_FAVORITES, 0)  # value 0 = key-up
        _, mock_idle = self._run(data)
        mock_idle.assert_not_called()

    def test_non_key_event_type_ignored(self):
        data = _pack_event(0, yoga_tray._KEY_FAVORITES, 1)  # ev_type 0 = EV_SYN
        _, mock_idle = self._run(data)
        mock_idle.assert_not_called()

    def test_unknown_keycode_ignored(self):
        data = _pack_event(yoga_tray._EV_KEY, 9999, 1)
        _, mock_idle = self._run(data)
        mock_idle.assert_not_called()

    def test_multiple_events_processed(self):
        data = (
            _pack_event(yoga_tray._EV_KEY, yoga_tray._KEY_FAVORITES, 1) +
            _pack_event(yoga_tray._EV_KEY, yoga_tray._KEY_REFRESH_RATE_TOGGLE, 1)
        )
        sec, mock_idle = self._run(data)
        assert mock_idle.call_count == 2
