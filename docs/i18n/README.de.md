# Haus.Licht-tray

[English](../../README.md) · **Deutsch**

Ein Tray-Symbol für [Haus.Licht](https://github.com/Gelaende51/Haus.Licht)
auf anderen Desktops als KDE Plasma: GNOME (mit der AppIndicator-Erweiterung),
XFCE, Cinnamon, MATE, Budgie, LXQt, Waybar und andere Trays. **Unter KDE
Plasma stattdessen [Haus.Licht-plasma](https://github.com/Gelaende51/Haus.Licht-plasma)
verwenden**: Das Widget kann all das und mehr, und der Autostart-Eintrag
dieses Trays überspringt Plasma.

- **KI-Offenlegung**
  - Agent: Claude Code mit Claude Opus 5.5 (Anthropic) hat Code, Tests und
    Doku geschrieben; etwa 5 Mio. Tokens verarbeitet (größtenteils
    zwischengespeicherter Kontext), etwa 50 k erzeugt (Stand 2026-10-26).
  - Autor: hat Design, Menü und Plattformen festgelegt.

[Lizenz: AGPL-3.0](../../LICENSE) · [Symbol-Lizenz](../../hauslicht_tray/icons/LICENSES.md) ·
[Notizen und Erkenntnisse](../../dev/takeaways.md)

## Was es tut

Es steuert dieselben Lampen wie die erste Instanz des Plasma-Widgets
(Widget 1), spricht über den ctl-Socket mit dem Haus.Licht-Dienst und
aktualisiert sich live.

- **Symbol:** Die ausgewählten Lampen sind an, aus oder nicht verbunden (der
  Dienst läuft nicht oder die Verbindung fehlt). **Tooltip:** jede Lampe mit
  an/aus, Helligkeit und Verbindung.
- **Linksklick:** Licht an/aus. **Mittelklick:** Automatisch / Manuell.
- **Menü:** Status, *Licht*, *Helligkeit* (1–100 %), *Automatisch* (dem
  Bildschirm folgen oder die Helligkeit halten), *Profile*, *Klatschen
  schaltet* (wenn der Dienst es kann), *Lampen* (alle oder eine; jede
  verbinden / trennen), *Einstellungen…*, *Beenden*. Läuft der Dienst
  nicht: *Dienst starten*.
- *Einstellungen…* öffnet das Einstellungsfenster von Haus.Licht
  (`hauslicht config`): Lampen, Profile, Ton und alles Weitere werden dort
  eingerichtet.
- Englisch und Deutsch.

Das Mausrad bewirkt nichts: Qts Tray-Symbol reicht es nicht weiter (siehe
[Erkenntnisse](../../dev/takeaways.md)).

## Installation

Braucht Haus.Licht (mit laufendem Dienst), Python 3 und PySide6 (das Paket
der Distribution, z. B. `python-pyside6`, oder `pip install --user PySide6`).

```sh
git clone <dieses Repository> Haus.Licht-tray && cd Haus.Licht-tray
./install.sh      # ~/.local, dazu ein Autostart-Eintrag (nicht unter KDE Plasma)
hauslicht-tray &  # oder neu anmelden
```

`./uninstall.sh` entfernt es wieder. Mit pip: `pip install --user .` liefert
den Befehl `hauslicht-tray` (ohne Autostart-Eintrag).
