"""Against a real Lichthaus daemon with mock bulbs only, fully isolated:
its own state file, socket, config/cache/state directories, HOME, no session
bus and no Bluetooth (LICHTHAUS_BACKENDS=mock). Skipped without a checkout."""
import os
import subprocess
import time
from pathlib import Path

import pytest

from lichthaus_tray import client

HL = Path(os.environ.get("LICHTHAUS_CHECKOUT", Path.home() / "building_stuff" / "Lichthaus"))
PY = HL / ".venv" / "bin" / "python"
LIVE_FILES = [HL / "lichthaus.json", Path.home() / ".config" / "lichthaus" / "lichthaus.json"]

pytestmark = pytest.mark.skipif(not (HL / "lichthaus").exists() or not PY.exists(),
                                reason="no Lichthaus checkout")


def isolated_env(d: Path) -> dict:
    home = d / "home"
    home.mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_STATE_HOME": str(home / ".local" / "state"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_RUNTIME_DIR": str(d),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={d}/no-bus",
        "LICHTHAUS_STATE": str(d / "state.json"),
        "LICHTHAUS_SOCK": str(d / "d.sock"),
        "LICHTHAUS_BACKENDS": "mock",
        "LICHTHAUS_NO_PANEL": "1",
        "LANG": "C.UTF-8",
    }


def stamp(p: Path):
    try:
        s = p.stat()
        return (s.st_mtime_ns, s.st_size)
    except FileNotFoundError:
        return None


@pytest.fixture
def mock_daemon(short_dir):
    env = isolated_env(short_dir)
    # Confirm beforehand where it would read and write.
    out = subprocess.run([str(PY), "-c", "from haus import common; print(common.STATE_PATH);"
                          "print(common.SOCK_PATH); print(common.lock_path(common.STATE_PATH))"],
                         cwd=HL, env=env, capture_output=True, text=True, check=True).stdout.split("\n")
    assert out[0] == env["LICHTHAUS_STATE"]
    assert out[1] == env["LICHTHAUS_SOCK"]
    assert out[2].startswith(str(short_dir))
    for p in LIVE_FILES:
        assert str(p) not in out
    before = [stamp(p) for p in LIVE_FILES]
    log = open(short_dir / "daemon.log", "w")
    proc = subprocess.Popen([str(HL / "lichthaus"), "sync", "--no-desktop-writes"], cwd=short_dir,
                            env=env, stdout=log, stderr=subprocess.STDOUT)
    sock = Path(env["LICHTHAUS_SOCK"])
    try:
        end = time.time() + 30
        while time.time() < end:
            try:
                client.request(["get"], path=sock, timeout=2)
                break
            except client.Unreachable:
                time.sleep(0.2)
        else:
            pytest.fail("mock daemon did not start: " + (short_dir / "daemon.log").read_text()[-2000:])
        yield sock
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        assert [stamp(p) for p in LIVE_FILES] == before


def test_get_watch_and_commands(mock_daemon):
    sock = mock_daemon
    st = client.request(["add", "mock", "name=Desk"], path=sock)
    assert st["added"] == "mock:1"
    st = client.request(["get"], path=sock)
    assert client.protocol_ok(st)
    assert st["in_widget"] == ["mock:1"]

    states = []
    w = client.Watcher(states.append, path=sock, base_delay=0.1, max_delay=2)
    w.start()
    try:
        end = time.time() + 10
        while time.time() < end and not (states and states[-1] and states[-1].get("event") == "snapshot"):
            time.sleep(0.05)
        assert states[-1]["event"] == "snapshot"
        client.request(["off"], path=sock)
        end = time.time() + 10
        while time.time() < end and not (states[-1] and states[-1].get("power") is False):
            time.sleep(0.05)
        assert states[-1]["power"] is False
        client.request(["on"], path=sock)
        end = time.time() + 10
        while time.time() < end and not (states[-1] and states[-1].get("power") is True):
            time.sleep(0.05)
        assert states[-1]["power"] is True
        # `which` addresses one bulb: hold it off its link, then connect again.
        client.request(["disconnect"], which="mock:1", path=sock)
        assert client.request(["get"], path=sock)["link"] == "held"
        client.request(["connect"], which="mock:1", path=sock)
        assert client.request(["get"], path=sock)["link"] != "held"
    finally:
        w.stop()
