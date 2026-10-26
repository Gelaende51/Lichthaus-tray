import threading
import time

import pytest

from hauslicht_tray import client
from conftest import FakeDaemon, sample_state


def wait_for(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_sock_path_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HAUSLICHT_SOCK", str(tmp_path / "x.sock"))
    assert client.sock_path() == tmp_path / "x.sock"
    monkeypatch.delenv("HAUSLICHT_SOCK")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/42")
    assert str(client.sock_path()) == "/run/user/42/hauslicht.sock"


def test_build_request():
    assert client.build_request(["select", "mock:1"]) == {
        "cmd": "select", "args": ["mock:1"], "arg": "mock:1", "which": None}
    r = client.build_request(["profile", "apply", "My evening"], widget=2)
    assert r["cmd"] == "@2" and r["args"] == ["profile", "apply", "My evening"]
    assert client.build_request(["connect"], which="mock:2")["which"] == "mock:2"
    assert client.build_request(["bulb", 25])["args"] == ["25"]


def test_request_get_and_error(fake):
    st = client.request(["get"], path=fake.path)
    assert st["protocol"] == 1 and st["in_widget"] == ["mock:1", "mock:2"]
    with pytest.raises(client.CtlError, match="nope"):
        client.request(["refuse"], path=fake.path)
    assert fake.requests[0]["cmd"] == "get"


def test_request_unreachable(short_dir):
    with pytest.raises(client.Unreachable):
        client.request(["get"], path=short_dir / "none.sock")


def test_protocol_ok():
    assert client.protocol_ok({"protocol": 1})
    assert client.protocol_ok({"protocol": 3})
    assert not client.protocol_ok({"protocol": 0})
    assert not client.protocol_ok({})
    assert not client.protocol_ok({"protocol": True})
    assert not client.protocol_ok(None)


def test_watch_snapshot_events_and_reconnect(fake):
    states = []
    w = client.Watcher(states.append, path=fake.path, base_delay=0.05, max_delay=0.4, debounce=0.05)
    w.start()
    try:
        assert wait_for(lambda: states and states[-1] and states[-1].get("event") == "snapshot")
        assert w.connected
        # An event leads to a fresh `get` (debounced: one for a burst).
        fake.state["power"] = False
        n = len(states)
        fake.push({"event": "intended", "bulb": "mock:1", "power": False})
        fake.push({"event": "intended", "bulb": "mock:2", "power": False})
        assert wait_for(lambda: len(states) > n and states[-1] and states[-1].get("power") is False)
        time.sleep(0.15)
        gets = [r for r in fake.requests if r["cmd"] == "get"]
        assert 1 <= len(gets) <= 2
        # The daemon goes away: None, then back-off retries that grow.
        fake.stop()
        assert wait_for(lambda: states[-1] is None)
        assert wait_for(lambda: len(w.delays) >= 4)
        d = list(w.delays)
        assert d[1] > d[0] and d[2] > d[1] and max(d) <= 0.4
        # It comes back: a new snapshot, the back-off is reset.
        fake.state["power"] = True
        fake.start()
        assert wait_for(lambda: states[-1] and states[-1].get("event") == "snapshot", timeout=3)
        fake.stop()
        assert wait_for(lambda: states[-1] is None)
        assert wait_for(lambda: len(w.delays) >= len(d) + 1)
        assert w.delays[len(d)] == 0.05
    finally:
        w.stop()


def test_kick_retries_at_once(short_dir):
    states = []
    w = client.Watcher(states.append, path=short_dir / "s.sock", base_delay=10, max_delay=10)
    w.start()
    try:
        assert wait_for(lambda: states == [None])
        d = FakeDaemon(short_dir / "s.sock", sample_state())
        d.start()
        t0 = time.time()
        w.kick()
        assert wait_for(lambda: states[-1] is not None, timeout=3)
        assert time.time() - t0 < 3
        d.stop()
    finally:
        w.stop()


def test_watch_refused_falls_back_to_get(fake):
    fake.watch_supported = False
    fake.state.pop("protocol")
    states = []
    w = client.Watcher(states.append, path=fake.path, base_delay=0.05, max_delay=5)
    w.start()
    try:
        assert wait_for(lambda: states and states[-1] is not None)
        assert not client.protocol_ok(states[-1])
        time.sleep(0.2)
        assert None not in states  # reachable, only too old
    finally:
        w.stop()
