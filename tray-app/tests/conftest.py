"""
Stub out gi (GTK/GLib/AppIndicator3/Notify) before yoga-tray is imported,
then load the module via importlib (it has no .py extension).

All tests can then do `import yoga_tray` normally.
"""

import importlib.machinery
import importlib.util
import pathlib
import sys
import types
import unittest.mock as mock


def _stub_gi():
    gi = types.ModuleType('gi')
    gi.require_version = mock.MagicMock()

    repo   = types.ModuleType('gi.repository')
    gtk    = mock.MagicMock(name='Gtk')
    glib   = mock.MagicMock(name='GLib')
    ai3    = mock.MagicMock(name='AppIndicator3')
    notify = mock.MagicMock(name='Notify')
    notify.init.return_value = True

    repo.Gtk           = gtk
    repo.GLib          = glib
    repo.AppIndicator3 = ai3
    repo.Notify        = notify

    sys.modules['gi']                          = gi
    sys.modules['gi.repository']               = repo
    sys.modules['gi.repository.Gtk']           = gtk
    sys.modules['gi.repository.GLib']          = glib
    sys.modules['gi.repository.AppIndicator3'] = ai3
    sys.modules['gi.repository.Notify']        = notify


_stub_gi()

_tray_path = str(pathlib.Path(__file__).parent.parent / 'yoga-tray')
_loader    = importlib.machinery.SourceFileLoader('yoga_tray', _tray_path)
_spec      = importlib.util.spec_from_loader('yoga_tray', _loader)
yoga_tray  = importlib.util.module_from_spec(_spec)
_loader.exec_module(yoga_tray)
sys.modules['yoga_tray'] = yoga_tray
