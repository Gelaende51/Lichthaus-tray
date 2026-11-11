"""The Qt tray against the fake socket, offscreen (no session bus needed)."""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

from lichthaus_tray.i18n import Tr  # noqa: E402
from lichthaus_tray.tray import Tray  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def spin(app, cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def actions(menu):
    out = {}
    for a in menu.actions():
        if a.menu():
            out[a.text()] = actions(a.menu())
        elif not a.isSeparator():
            out[a.text()] = (a.isCheckable(), a.isChecked(), a.isEnabled())
    return out


def test_tray_menu_commands_and_icon(app, fake):
    t = Tray(app, Tr(False), path=fake.path)
    try:
        assert spin(app, lambda: t.st is not None)
        m = actions(t.menu)
        assert m["Connected"] == (False, False, False)
        assert m["Light"] == (True, True, True)
        assert m["Brightness: 50 %"]["50 %"] == (True, True, True)
        assert m["Bulbs"]["All"] == (True, True, True)
        assert "Desk" in t.icon.toolTip()
        # A menu item sends its command; the next state rebuilds the menu.
        light = next(a for a in t.menu.actions() if a.text() == "Light")
        fake.state.update(power=False, bulbs=0.0)
        light.trigger()
        assert spin(app, lambda: any(r["cmd"] == "off" for r in fake.requests))
        assert spin(app, lambda: actions(t.menu).get("Light") == (True, False, True))
        # Left click toggles, middle click flips Automatic.
        t.on_activated(QSystemTrayIcon.Trigger)
        assert spin(app, lambda: any(r["cmd"] == "toggle" for r in fake.requests))
        t.on_activated(QSystemTrayIcon.MiddleClick)
        assert spin(app, lambda: any(r["cmd"] in ("pause", "dim") for r in fake.requests))
        # Per-bulb connect uses `which`.
        bulbs = next(a for a in t.menu.actions() if a.text() == "Bulbs").menu()
        next(a for a in bulbs.actions() if a.text() == "Connect Shelf").trigger()
        assert spin(app, lambda: any(r["cmd"] == "connect" and r["which"] == "mock:2" for r in fake.requests))
        # The daemon goes away: "Service not running" with "Start service".
        fake.stop()
        assert spin(app, lambda: "Start service" in actions(t.menu))
        assert "Service not running" in t.icon.toolTip()
    finally:
        t.watcher.stop()
        t.icon.hide()
