"""install.sh / uninstall.sh in a temporary HOME, never the real one."""
import os
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parent.parent


def run(script, home):
    env = {"HOME": str(home), "PATH": os.environ["PATH"]}
    assert Path(env["HOME"]) != Path.home()
    return subprocess.run(["sh", str(R / script)], env=env, capture_output=True, text=True, check=True)


def test_install_and_uninstall(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    out = run("install.sh", home).stdout
    assert "Installed" in out
    launcher = home / ".local/bin/lichthaus-tray"
    share = home / ".local/share/lichthaus-tray"
    auto = home / ".config/autostart/lichthaus-tray.desktop"
    app = home / ".local/share/applications/lichthaus-tray.desktop"
    for p in (launcher, share / "lichthaus_tray/tray.py", share / "lichthaus_tray/icons/on.svg",
              share / "lichthaus_tray/icons/LICENSES.md", share / "LICENSE", auto, app):
        assert p.exists(), p
    assert os.access(launcher, os.X_OK)
    text = auto.read_text()
    assert "NotShowIn=KDE;" in text and f"Exec={launcher}" in text
    assert "NotShowIn=KDE;" in app.read_text()
    assert not list(share.rglob("__pycache__"))
    # The launcher's interpreter imports the package from the installed copy.
    py = launcher.read_text().split('exec "')[1].split('"')[0]
    r = subprocess.run([py, "-c", "import lichthaus_tray.model as m; print(m.__file__)"],
                       env={"HOME": str(home), "PATH": os.environ["PATH"], "PYTHONPATH": str(share)},
                       capture_output=True, text=True, check=True, cwd=tmp_path)
    assert r.stdout.startswith(str(share))
    # Twice is fine (an update).
    run("install.sh", home)
    run("uninstall.sh", home)
    for p in (launcher, share, auto, app):
        assert not p.exists(), p
