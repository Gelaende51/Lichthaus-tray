# Takeaways

## Qt drops the StatusNotifierItem `Scroll` event (no mouse wheel)

`QSystemTrayIcon` has no wheel or scroll signal at all, on any backend: its
only signals are `activated(ActivationReason)` and `messageClicked()`
(PySide6 6.12 meta-object), and `ActivationReason` has no wheel value.
Qt's StatusNotifierItem adaptor (qtbase `src/gui/platform/unix/dbustray/`)
accepts the D-Bus `Scroll` call and drops it; `SecondaryActivate` becomes
`MiddleClick`, `Activate` becomes `Trigger`. Checked live with PySide6 6.12
on Plasma 6: `busctl --user call <unique name> /StatusNotifierItem
org.kde.StatusNotifierItem Scroll is 120 vertical` returns success and
nothing reaches the application; `Activate` and `SecondaryActivate` did
toggle the light and switch to Manual on the mock daemon. So the wheel is not offered. A brightness wheel
would need our own SNI (D-Bus object with `Scroll`), which the design rules
out; a candidate for a Qt feature request (a `QSystemTrayIcon::wheel`
signal, fed from SNI `Scroll` and the XEmbed widget's wheel events).

## Qt registers the SNI under its unique bus name

Qt 6 registers `:1.NNN/StatusNotifierItem` with the watcher, not a
well-known `org.kde.StatusNotifierItem-PID-N` name as KDE apps do. To find
the tray on the bus, read the watcher's `RegisteredStatusNotifierItems` and
match the unique name's PID (`GetConnectionUnixProcessID`). The menu is at
`/MenuBar` (`Menu` property), `com.canonical.dbusmenu`.

## busctl takes `-1` for an option

`busctl call … GetLayout iias 0 -1 0` fails: `-1` is parsed as an option.
Put `--` before the positional arguments.

## Socket timeouts and `makefile`

A `socket.makefile()` reader is unusable after one `socket.timeout`
("cannot read from timed out object"). The `watch` reader therefore uses
`recv` with its own line buffer, so the timeout can drive the slow safety
refresh.

## `watch` does not report every change

`watch` streams device events and intended states, not changes like a
profile picked or the selection moved by another front end. The tray reads
`get` after each burst of events (debounced), after its own commands, and
every 30 s while connected; when the service is gone it retries with
back-off from 1 s doubling to 30 s.

## Testing beside the live daemon

`HAUSLICHT_STATE` alone moves the state file, the `.armed.json` and the
`.lock` (they derive from it); without it the daemon uses the checkout's
`hauslicht.json`. The tests also give it its own `HOME`, XDG directories
and `XDG_RUNTIME_DIR`, a dead `DBUS_SESSION_BUS_ADDRESS` (no hotkeys or
panel scripting), `HAUSLICHT_BACKENDS=mock` (no Bluetooth), confirm the
paths with `haus.common` first, and check the live files' mtime and size
afterwards. Unix socket paths must stay under ~107 bytes, so the temp
directory goes into `$XDG_RUNTIME_DIR`.

## Icons

The widget's SVGs carry Plasma's `current-color-scheme` stylesheet
(`#232629`, `fill:currentColor`). Outside Plasma nothing recolours them, so
the tray substitutes the palette's text colour and renders pixmaps itself
(SNI then sends `IconPixmap`).
