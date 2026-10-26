#!/bin/sh
# Installs Haus.Licht-tray for the current user into ~/.local (no root):
# the package, a launcher, a menu entry and an XDG autostart entry that
# skips KDE Plasma (Plasma has the Haus.Licht-plasma widget).
set -eu
src=$(cd "$(dirname "$0")" && pwd)
share="$HOME/.local/share/hauslicht-tray"
bin="$HOME/.local/bin"
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
autostart="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
python=$(command -v "${PYTHON:-python3}") || { echo "python3 not found" >&2; exit 1; }
if ! "$python" -c 'import PySide6' 2>/dev/null; then
    echo "warning: PySide6 is missing for $python; install your distribution's PySide6" >&2
    echo "(python-pyside6, python3-pyside6.qtwidgets …) or: pip install --user PySide6" >&2
fi

mkdir -p "$share" "$bin" "$apps" "$autostart"
rm -rf "$share/hauslicht_tray"
cp -R "$src/hauslicht_tray" "$share/"
find "$share" -name __pycache__ -prune -exec rm -rf {} +
cp "$src/LICENSE" "$share/LICENSE"

cat > "$bin/hauslicht-tray" <<EOF
#!/bin/sh
# Haus.Licht-tray launcher (install.sh)
PYTHONPATH="$share\${PYTHONPATH:+:\$PYTHONPATH}" exec "$python" -m hauslicht_tray "\$@"
EOF
chmod 755 "$bin/hauslicht-tray"

entry() {
    cat <<EOF
[Desktop Entry]
Type=Application
Name=Haus.Licht tray
Name[de]=Haus.Licht-Tray
Comment=Smart bulbs from the system tray
Comment[de]=Smarte Lampen aus dem Systemabschnitt
Exec=$bin/hauslicht-tray
Icon=$share/hauslicht_tray/icons/on.svg
Terminal=false
Categories=Utility;
NotShowIn=KDE;
EOF
}
entry > "$apps/hauslicht-tray.desktop"
{ entry; echo "X-GNOME-Autostart-enabled=true"; } > "$autostart/hauslicht-tray.desktop"

echo "Installed: $bin/hauslicht-tray (starts with your next login outside KDE Plasma)."
case ":$PATH:" in *":$bin:"*) ;; *) echo "Note: $bin is not on PATH." ;; esac
