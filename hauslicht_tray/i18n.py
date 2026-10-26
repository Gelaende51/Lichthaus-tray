"""English and German, like the Plasma widget's tr(): German when the locale
starts with "de". Every user-visible string goes through tr()."""
from __future__ import annotations

import locale
import os

DE = {
    "Service not running": "Dienst läuft nicht",
    "Start service": "Dienst starten",
    "Please update Haus.Licht": "Bitte Haus.Licht aktualisieren",
    "Connected": "Verbunden",
    "Idle (disconnected)": "Ruht (getrennt)",
    "Not connected: %1": "Nicht verbunden: %1",
    "No bulbs": "Keine Lampen",
    "Light": "Licht",
    "Brightness": "Helligkeit",
    "Brightness: %1 %": "Helligkeit: %1 %",
    "Automatic": "Automatisch",
    "Profiles": "Profile",
    "Clap to toggle": "Klatschen schaltet",
    "Bulbs": "Lampen",
    "All": "Alle",
    "Connect %1": "%1 verbinden",
    "Disconnect %1": "%1 trennen",
    "Settings…": "Einstellungen…",
    "Quit": "Beenden",
    "on": "an",
    "off": "aus",
    "connected": "verbunden",
    "disconnected": "getrennt",
    "not connected": "nicht verbunden",
    "offline": "offline",
    "idle": "ruht",
    "Haus.Licht": "Haus.Licht",
    "Could not start the service: %1": "Dienst konnte nicht gestartet werden: %1",
    "hauslicht not found": "hauslicht nicht gefunden",
}


def is_german(lang: str | None = None) -> bool:
    if lang is None:
        lang = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES")
                or os.environ.get("LANG") or (locale.getlocale()[0] or ""))
    return lang.lower().startswith("de")


class Tr:
    def __init__(self, german: bool | None = None):
        self.german = is_german() if german is None else german

    def __call__(self, text: str, *args) -> str:
        out = DE.get(text, text) if self.german else text
        for i, a in enumerate(args, 1):
            out = out.replace(f"%{i}", str(a))
        return out
