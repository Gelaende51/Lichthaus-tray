#!/bin/sh
# Removes what install.sh put into ~/.local and the autostart entry.
# A running tray keeps running until you choose Quit in its menu.
set -eu
rm -rf "$HOME/.local/share/lichthaus-tray"
rm -f "$HOME/.local/bin/lichthaus-tray" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/applications/lichthaus-tray.desktop" \
      "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/lichthaus-tray.desktop"
echo "Lichthaus-tray removed."
