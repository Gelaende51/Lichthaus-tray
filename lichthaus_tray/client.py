"""Lichthaus's ctl protocol (Lichthaus docs/ctl-protocol.md), spoken directly.

One JSON line per connection: a request in, a reply out. ``watch`` keeps its
connection open and streams events. No import of Lichthaus's package: the
socket is the only interface.
"""
from __future__ import annotations

import json
import os
import socket
import threading
from pathlib import Path
from typing import Callable, Optional

# The lowest ctl protocol this tray understands ("protocol" in `get`).
MIN_PROTOCOL = 1


class CtlError(Exception):
    """The daemon refused a command (its message is meant for the user)."""


class Unreachable(Exception):
    """No daemon answered on the socket."""


def sock_path() -> Path:
    """$LICHTHAUS_SOCK, else $XDG_RUNTIME_DIR/lichthaus.sock."""
    env = os.environ.get("LICHTHAUS_SOCK")
    if env:
        return Path(env)
    run = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(run) / "lichthaus.sock"


def build_request(args, widget: int = 1, which: Optional[str] = None) -> dict:
    """The JSON object for `args` (command first). Widget N > 1: `@N` in front."""
    args = [str(a) for a in args]
    if widget != 1:
        args = [f"@{widget}"] + args
    req = {"cmd": args[0], "args": args[1:], "arg": " ".join(args[1:]), "which": which}
    return req


def _connect(path: Path, timeout: float) -> socket.socket:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(path))
    except OSError as e:
        s.close()
        raise Unreachable(str(e)) from e
    return s


def _readline(f) -> bytes:
    line = f.readline()
    if not line:
        raise Unreachable("connection closed")
    return line


def request(args, widget: int = 1, which: Optional[str] = None,
            timeout: float = 15.0, path: Optional[Path] = None):
    """Send one command; return ``results[0]`` (or the whole reply when it has
    no ``results``). Raises CtlError on a refusal, Unreachable without daemon."""
    path = path or sock_path()
    s = _connect(path, timeout)
    try:
        with s, s.makefile("rb") as f:
            s.sendall(json.dumps(build_request(args, widget, which)).encode() + b"\n")
            reply = json.loads(_readline(f))
    except (OSError, ValueError) as e:
        raise Unreachable(str(e)) from e
    if isinstance(reply, dict) and "error" in reply:
        raise CtlError(str(reply["error"]))
    if isinstance(reply, dict) and "results" in reply:
        results = reply["results"]
        return results[0] if results else None
    return reply


def protocol_ok(state: Optional[dict]) -> bool:
    """The daemon reports a protocol this tray understands."""
    p = (state or {}).get("protocol")
    return isinstance(p, int) and not isinstance(p, bool) and p >= MIN_PROTOCOL


class Watcher:
    """Keeps a `watch` connection to widget N and reports the state.

    ``on_state(state)`` gets the full `get` object: the snapshot, then a fresh
    `get` after each burst of events (debounced) and after ``refresh()``;
    ``None`` while no daemon answers. When the connection ends it reconnects
    after ``base_delay`` seconds, doubling up to ``max_delay`` while the daemon
    stays away. While connected nothing polls except a slow safety refresh
    every ``max_delay`` seconds (changes that emit no event, e.g. a profile
    picked in another front end). Callbacks run on the watcher's threads.
    """

    def __init__(self, on_state: Callable[[Optional[dict]], None], widget: int = 1,
                 path: Optional[Path] = None, base_delay: float = 1.0,
                 max_delay: float = 30.0, debounce: float = 0.2):
        self.on_state = on_state
        self.widget = widget
        self.path = path
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.debounce = debounce
        self._stop = threading.Event()
        self._kick = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._refresh_timer: Optional[threading.Timer] = None
        self._thread = threading.Thread(target=self._run, name="lichthaus-watch", daemon=True)
        self.delays: list[float] = []  # the back-off waits taken (for tests)
        self.connected = False
        self.fallback = False

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._kick.set()
        with self._lock:
            if self._sock:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            if self._refresh_timer:
                self._refresh_timer.cancel()
        self._thread.join(timeout=5)

    def kick(self):
        """Retry at once (e.g. after "Start service"), resetting the back-off."""
        self._kick.set()

    def refresh(self, delay: Optional[float] = None):
        """Read `get` again soon (debounced); after a command, an event."""
        with self._lock:
            if self._stop.is_set():
                return
            if self._refresh_timer:
                self._refresh_timer.cancel()
            t = threading.Timer(self.debounce if delay is None else delay, self._do_refresh)
            t.daemon = True
            self._refresh_timer = t
            t.start()

    def _do_refresh(self):
        if self._stop.is_set():
            return
        try:
            st = request(["get"], widget=self.widget, path=self.path, timeout=5)
        except Unreachable:
            return  # the watch connection notices and reports None
        except CtlError:
            return
        if not self._stop.is_set() and isinstance(st, dict):
            self.on_state(st)

    def _run(self):
        delay = self.base_delay
        while not self._stop.is_set():
            got_snapshot = False
            self.fallback = False
            try:
                got_snapshot = self._watch_once()
            except (Unreachable, CtlError, OSError, ValueError):
                pass
            self.connected = False
            if self._stop.is_set():
                break
            if self.fallback:
                self._kick.wait(self.max_delay)
                self._kick.clear()
                continue
            self.on_state(None)
            if got_snapshot:
                delay = self.base_delay
            self.delays.append(delay)
            self._kick.wait(delay)
            if self._kick.is_set():
                self._kick.clear()
                delay = self.base_delay
            else:
                delay = min(delay * 2, self.max_delay)

    def _watch_once(self) -> bool:
        s = _connect(self.path or sock_path(), timeout=self.max_delay)
        with self._lock:
            self._sock = s
        got = False
        buf = b""
        try:
            with s:
                s.sendall(json.dumps(build_request(["watch"], self.widget)).encode() + b"\n")
                while not self._stop.is_set():
                    if b"\n" not in buf:
                        try:
                            chunk = s.recv(65536)
                        except socket.timeout:
                            if got:
                                self.refresh(0)  # the slow safety refresh
                            continue
                        if not chunk:
                            return got
                        buf += chunk
                        continue
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    if isinstance(msg, dict) and "error" in msg:
                        # A daemon without `watch` (older than protocol 1):
                        # show its `get` (the menu asks to update) and look
                        # again after max_delay.
                        st = request(["get"], widget=self.widget, path=self.path, timeout=5)
                        if isinstance(st, dict):
                            self.on_state(st)
                            self.fallback = True
                        return got
                    if isinstance(msg, dict) and msg.get("event") == "snapshot":
                        got = True
                        self.connected = True
                        self.on_state(msg)
                    else:
                        self.refresh()
        finally:
            with self._lock:
                self._sock = None
        return got
