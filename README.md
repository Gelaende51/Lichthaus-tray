# Haus.Licht-tray

**English** · [Deutsch](docs/i18n/README.de.md)

A tray icon for [Haus.Licht](https://github.com/Gelaende51/Haus.Licht) on
desktops other than KDE Plasma: GNOME (with the AppIndicator extension;
the native choice there is [Haus.Licht-gnome](https://github.com/Gelaende51/Haus.Licht-gnome)),
XFCE, Cinnamon, MATE, Budgie, LXQt, Waybar and other trays. **On KDE Plasma,
use [Haus.Licht-plasma](https://github.com/Gelaende51/Haus.Licht-plasma)
instead**: its widget does all of this and more, and this tray's autostart
entry skips Plasma.

- **AI disclosure**
  - Agent: Claude Code with Claude Opus 5.5 (Anthropic) wrote the code,
    tests and docs; about 5 M tokens processed (mostly cached context),
    about 50 k generated (as of 2026-10-26).
  - Author: chose the design, the menu and the platforms.

[License: AGPL-3.0](LICENSE) · [Icon licence](hauslicht_tray/icons/LICENSES.md) ·
[Notes and findings](dev/takeaways.md)

## What it does

It drives the same bulbs as the Plasma widget's first instance (widget 1),
talking to the Haus.Licht service over its ctl socket and updating live.

- **Icon:** the selected bulbs are on, off, or not connected (the service
  is not running, or the link is down). **Tooltip:** each bulb with on/off,
  brightness and link.
- **Left click:** light on/off. **Middle click:** Automatic / Manual.
- **Menu:** status, *Light*, *Brightness* (1–100 %), *Automatic* (follow
  the screen or hold the level), *Profiles*, *Clap to toggle* (when the
  service supports it), *Bulbs* (all or one; connect / disconnect each),
  *Settings…*, *Quit*. When the service is not running: *Start service*.
- *Settings…* opens Haus.Licht's own settings window (`hauslicht config`):
  bulbs, profiles, sound and everything else are set up there.
- English and German.

The mouse wheel does nothing: Qt's tray icon does not pass it on (see
[takeaways](dev/takeaways.md)).

## Install

Needs Haus.Licht (its service running), Python 3 and PySide6 (your
distribution's package, e.g. `python-pyside6`, or `pip install --user PySide6`).

```sh
git clone <this repository> Haus.Licht-tray && cd Haus.Licht-tray
./install.sh      # ~/.local, plus an autostart entry (not on KDE Plasma)
hauslicht-tray &  # or log in again
```

`./uninstall.sh` removes it. With pip: `pip install --user .` gives the
`hauslicht-tray` command (no autostart entry).
