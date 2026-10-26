import json
import os
import socket
import sys
import tempfile
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeDaemon:
    """A fake ctl socket: answers each request with ``handler(req)`` and keeps
    `watch` connections open, sending ``snapshot`` first."""

    def __init__(self, path: Path, state: dict):
        self.path = path
        self.state = state
        self.requests: list[dict] = []
        self.watchers: list[socket.socket] = []
        self.watch_supported = True
        self._srv = None
        self._stop = threading.Event()

    def start(self):
        self._stop.clear()
        self._srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if self.path.exists():
            self.path.unlink()
        self._srv.bind(str(self.path))
        self._srv.listen(8)
        self._srv.settimeout(0.1)
        threading.Thread(target=self._accept, daemon=True).start()

    def stop(self):
        """Go away like a stopped daemon: close everything, remove the socket."""
        self._stop.set()
        for w in self.watchers:
            try:
                w.shutdown(socket.SHUT_RDWR)
                w.close()
            except OSError:
                pass
        self.watchers.clear()
        if self._srv:
            self._srv.close()
        if self.path.exists():
            self.path.unlink()

    def push(self, event: dict):
        for w in list(self.watchers):
            try:
                w.sendall(json.dumps(event).encode() + b"\n")
            except OSError:
                pass

    def _accept(self):
        while not self._stop.is_set():
            try:
                c, _ = self._srv.accept()
            except (socket.timeout, OSError):
                continue
            threading.Thread(target=self._serve, args=(c,), daemon=True).start()

    def _serve(self, c):
        f = c.makefile("rb")
        line = f.readline()
        if not line:
            c.close()
            return
        req = json.loads(line)
        self.requests.append(req)
        if req["cmd"] == "watch":
            if not self.watch_supported:
                c.sendall(b'{"error": "unknown command: watch"}\n')
                c.close()
                return
            c.sendall(json.dumps(dict(self.state, event="snapshot")).encode() + b"\n")
            self.watchers.append(c)
            return
        if req["cmd"] == "refuse":
            c.sendall(b'{"error": "nope"}\n')
        else:
            c.sendall(json.dumps({"results": [self.state]}).encode() + b"\n")
        c.close()


def sample_state(**over):
    st = {
        "protocol": 1, "power": True, "bulbs": 50.0, "following": True, "audio": False,
        "video": False, "selected": "all", "profile": "default", "profiles": ["default", "evening"],
        "link": "connected", "connected": True, "online": True, "clap": "off",
        "clap_status": {"available": True},
        "in_widget": ["mock:1", "mock:2"],
        "bulbs_list": [
            {"id": "mock:1", "name": "Desk", "power": True, "output": 50.0, "connected": True,
             "online": True, "link": "connected", "step": 1.0, "use": True},
            {"id": "mock:2", "name": "Shelf", "power": False, "output": 0.0, "connected": False,
             "online": True, "link": "held", "step": 0.5, "use": True},
            {"id": "mock:3", "name": "Unused", "power": False, "output": 0.0, "connected": True,
             "online": True, "link": "idle", "step": 1.0, "use": False},
        ],
    }
    st.update(over)
    return st


@pytest.fixture
def short_dir():
    # Unix socket paths are limited to ~107 bytes: keep them short.
    d = tempfile.mkdtemp(prefix="hlt-", dir=os.environ.get("XDG_RUNTIME_DIR") or None)
    yield Path(d)
    import shutil
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def fake(short_dir):
    d = FakeDaemon(short_dir / "s.sock", sample_state())
    d.start()
    yield d
    d.stop()
