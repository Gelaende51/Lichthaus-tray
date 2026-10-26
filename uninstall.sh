#!/bin/sh
# Removes what install.sh put into ~/.local and the autostart entry.
# A running tray keeps running until you choose Quit in its menu.
set -eu
rm -rf "$HOME/.local/share/hauslicht-tray"
rm -f "$HOME/.local/bin/hauslicht-tray" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/applications/hauslicht-tray.desktop" \
      "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/hauslicht-tray.desktop"
echo "Haus.Licht-tray removed."
