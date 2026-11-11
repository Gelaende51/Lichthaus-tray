"""Things the tray starts outside the daemon: the settings window and the
systemd user service. No Qt here."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

SERVICE = "lichthaus.service"


def lichthaus_bin() -> Optional[str]:
    """~/.local/bin/lichthaus, else lichthaus on PATH."""
    local = Path.home() / ".local" / "bin" / "lichthaus"
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    return shutil.which("lichthaus")


def settings_argv() -> Optional[list]:
    h = lichthaus_bin()
    return [h, "config"] if h else None


def open_settings() -> bool:
    """Run `lichthaus config` detached; False when lichthaus is not found."""
    argv = settings_argv()
    if not argv:
        return False
    subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def start_service(timeout: float = 30) -> tuple:
    """`systemctl --user start lichthaus.service` (found on PATH). Returns
    (ok, message). Never anything but start, never as root."""
    exe = shutil.which("systemctl")
    if not exe:
        return False, "systemctl not found"
    try:
        p = subprocess.run([exe, "--user", "start", SERVICE], capture_output=True, text=True,
                           timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    if p.returncode != 0:
        return False, (p.stderr or p.stdout).strip() or f"exit {p.returncode}"
    return True, ""
