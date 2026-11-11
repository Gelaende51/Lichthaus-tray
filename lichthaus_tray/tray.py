"""The tray icon (QSystemTrayIcon): StatusNotifierItem + DBusMenu where a
watcher exists, XEmbed otherwise. Only plain, checkable and radio actions and
submenus: DBusMenu cannot carry custom widgets."""
from __future__ import annotations

import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon, QPainter, QPixmap, QPalette
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import actions, client, model
from .i18n import Tr

ICONS = Path(__file__).resolve().parent / "icons"
SIZES = (16, 22, 24, 32, 48, 64)


def render_icon(state: str, color: str) -> QIcon:
    """The set's SVG with Plasma's colour-scheme colour replaced by `color`."""
    svg = (ICONS / f"{state}.svg").read_text()
    svg = svg.replace("#232629", color).replace("currentColor", color)
    r = QSvgRenderer(QByteArray(svg.encode()))
    icon = QIcon()
    for s in SIZES:
        pm = QPixmap(s, s)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        r.render(p)
        p.end()
        icon.addPixmap(pm)
    return icon


class Bridge(QObject):
    state = Signal(object)
    error = Signal(str)
    done = Signal()


class Tray(QObject):
    def __init__(self, app: QApplication, tr: Optional[Tr] = None, path: Optional[Path] = None):
        super().__init__()
        self.app = app
        self.tr = tr or Tr()
        self.path = path
        self.st: Optional[dict] = None
        self.clap_last = "both"
        self._key = None
        self._submenus: list = []
        self.bridge = Bridge()
        self.bridge.state.connect(self.on_state)
        self.bridge.error.connect(self.on_error)
        self.bridge.done.connect(self.on_done)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lichthaus-cmd")
        color = app.palette().color(QPalette.WindowText).name()
        self.icons = {s: render_icon(s, color) for s in ("on", "off", "disconnected")}
        self.icon = QSystemTrayIcon(self.icons["disconnected"])
        self.menu = QMenu()
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self.on_activated)
        self.watcher = client.Watcher(self.bridge.state.emit, path=path)
        self.on_state(None)
        self.icon.show()
        self.watcher.start()

    # ------------------------------------------------------------ state
    def on_state(self, st):
        if st is not None and st.get("clap") in model.CLAP_MODES:
            self.clap_last = st["clap"]
        self.st = st
        self.icon.setIcon(self.icons[model.icon_state(st)])
        self.icon.setToolTip(model.tooltip(st, self.tr))
        items = model.build_menu(st, self.tr, self.clap_last)
        key = model.menu_key(items)
        if key != self._key:
            self._key = key
            self.fill(self.menu, items, top=True)

    def fill(self, menu: QMenu, items, top=False):
        if top:
            for m in self._submenus:
                m.deleteLater()
            self._submenus = []
        menu.clear()
        groups = {}
        for it in items:
            if it.kind == "separator":
                menu.addSeparator()
                continue
            if it.kind == "menu":
                sub = QMenu(it.text, menu)
                sub.setEnabled(it.enabled)
                self._submenus.append(sub)
                self.fill(sub, it.children)
                menu.addMenu(sub)
                continue
            a = QAction(it.text, menu)
            a.setObjectName(it.id)
            a.setEnabled(it.enabled)
            if it.checkable:
                a.setCheckable(True)
                a.setChecked(it.checked)
            if it.group:
                g = groups.get(it.group)
                if g is None:
                    g = groups[it.group] = QActionGroup(menu)
                    g.setExclusive(True)
                g.addAction(a)
            a.triggered.connect(lambda _=False, it=it: self.trigger(it))
            menu.addAction(a)

    # ---------------------------------------------------------- actions
    def trigger(self, it: model.Item):
        if it.special == "quit":
            self.quit()
        elif it.special == "settings":
            if not actions.open_settings():
                self.on_error(self.tr("lichthaus not found"))
        elif it.special == "start-service":
            threading.Thread(target=self._start_service, daemon=True).start()
        elif it.cmd:
            self.send(it.cmd, it.which)

    def _start_service(self):
        ok, msg = actions.start_service()
        if not ok:
            self.bridge.error.emit(self.tr("Could not start the service: %1", msg))
        self.watcher.kick()

    def send(self, cmd, which=None):
        def run():
            try:
                client.request(cmd, which=which, path=self.path)
            except client.CtlError as e:
                self.bridge.error.emit(str(e))
            except client.Unreachable:
                pass
            self.bridge.done.emit()
        self.pool.submit(run)

    def on_done(self):
        self._key = None  # a check Qt flipped is set back from the next state
        self.watcher.refresh(0.05)

    def on_error(self, msg: str):
        self.icon.showMessage(self.tr("Lichthaus"), msg, QSystemTrayIcon.Warning, 5000)

    def on_activated(self, reason):
        st = self.st
        if st is None:
            return
        if reason == QSystemTrayIcon.Trigger:
            self.send(model.toggle_cmd(st))
        elif reason == QSystemTrayIcon.MiddleClick:
            self.send(model.automatic_cmd(st))

    def quit(self):
        self.icon.hide()
        self.watcher.stop()
        self.pool.shutdown(wait=False)
        self.app.quit()


def main(argv=None):
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("lichthaus-tray")
    app.setApplicationDisplayName("Lichthaus")
    app.setDesktopFileName("lichthaus-tray")
    app.setQuitOnLastWindowClosed(False)
    tray = Tray(app)
    signal.signal(signal.SIGINT, lambda *a: tray.quit())
    signal.signal(signal.SIGTERM, lambda *a: tray.quit())
    t = QTimer()  # lets Python see signals while Qt's loop runs
    t.start(500)
    t.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
