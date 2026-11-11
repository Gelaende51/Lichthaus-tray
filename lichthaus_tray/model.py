"""What the tray shows, as plain data: no Qt here, so it is tested directly.

The `get` object (Lichthaus docs/ctl-protocol.md) of widget 1 goes in; the
icon state, the tooltip and the menu entries come out. Each entry carries the
ctl command it sends; the Plasma widget (Lichthaus-plasma main.qml) is the
reference for what each control does.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .client import protocol_ok

BRIGHTNESS_STEPS = (1, 10, 25, 50, 75, 100)
CLAP_MODES = ("clap", "snap", "both")


@dataclass
class Item:
    id: str
    text: str = ""
    kind: str = "action"            # action | separator | menu
    checkable: bool = False
    checked: bool = False
    enabled: bool = True
    group: Optional[str] = None     # radio group
    cmd: Optional[list] = None      # ctl command (args) it sends
    which: Optional[str] = None     # `which`: one bulb instead of the selection
    special: Optional[str] = None   # start-service | settings | quit
    children: list = field(default_factory=list)


def sep(i: str) -> Item:
    return Item(id=i, kind="separator")


def fmt(x) -> str:
    x = float(x)
    return str(int(round(x))) if abs(x - round(x)) < 0.05 else f"{x:.1f}"


def widget_bulbs(st: dict) -> list:
    """Widget 1's used bulbs (`in_widget`), in list order."""
    ids = st.get("in_widget") or []
    return [b for b in st.get("bulbs_list") or [] if b.get("id") in ids]


def selected_bulb(st: dict):
    for b in st.get("bulbs_list") or []:
        if b.get("id") == st.get("selected"):
            return b
    return None


def selection_bulbs(st: dict) -> list:
    b = selected_bulb(st)
    return [b] if b else widget_bulbs(st)


def level_step(st: dict) -> float:
    """The selection's native brightness step (percent); "all": the finest."""
    steps = [float(b["step"]) for b in selection_bulbs(st)
             if isinstance(b.get("step"), (int, float)) and b["step"] > 0]
    return min(steps) if steps else 1.0


def shown_level(st: dict):
    """The level the selection shows: follow audio / video's, else the output."""
    if st.get("audio") is True and isinstance(st.get("audio_level"), (int, float)):
        return st["audio_level"]
    if st.get("video") is True and isinstance(st.get("video_level"), (int, float)):
        return st["video_level"]
    b = st.get("bulbs")
    return b if isinstance(b, (int, float)) else None


def is_lit(st: dict) -> bool:
    b = st.get("bulbs")
    return st.get("power") is not False and isinstance(b, (int, float)) and b > 0


def is_disconnected(st: Optional[dict]) -> bool:
    if not st:
        return True
    link = st.get("link")
    if link in ("held", "failed"):
        return True
    return st.get("connected") is False or st.get("online") is False


def icon_state(st: Optional[dict]) -> str:
    """on, off or disconnected (daemon unreachable, or the link not connected)."""
    if is_disconnected(st):
        return "disconnected"
    return "on" if is_lit(st) else "off"


def bulb_link(b: dict) -> str:
    link = b.get("link")
    if link:
        return link
    if b.get("connected") is False or b.get("online") is False:
        return "failed"
    return "connected"


def status_text(st: Optional[dict], tr) -> str:
    if st is None:
        return tr("Service not running")
    if not widget_bulbs(st):
        return tr("No bulbs")
    link = st.get("link")
    if link == "held":
        return tr("Idle (disconnected)")
    if link == "failed" or st.get("connected") is False or st.get("online") is False:
        return tr("Not connected: %1", tr(st.get("link_reason") or "not connected"))
    return tr("Connected")


def tooltip(st: Optional[dict], tr) -> str:
    lines = [tr("Lichthaus")]
    if st is None:
        lines.append(tr("Service not running"))
        return "\n".join(lines)
    if not protocol_ok(st):
        lines.append(tr("Please update Lichthaus"))
    for b in widget_bulbs(st):
        on = b.get("power") is not False and isinstance(b.get("output"), (int, float)) and b["output"] > 0
        out = b.get("output")
        pct = f"{fmt(out)} %" if isinstance(out, (int, float)) else "–"
        link = bulb_link(b)
        link_text = {"connected": tr("connected"), "held": tr("disconnected"),
                     "idle": tr("idle")}.get(link, tr(b.get("link_reason") or "not connected"))
        lines.append(f"{b.get('name') or b.get('id')}: {tr('on') if on else tr('off')}, {pct}, {link_text}")
    if len(lines) == 1:
        lines.append(tr("No bulbs"))
    return "\n".join(lines)


def manual(st: dict) -> bool:
    return st.get("following") is False


def follow_on(st: dict) -> bool:
    return st.get("audio") is True or st.get("video") is True


def hold_cmd(st: dict) -> list:
    """Manual: hold the current level. Lit bulbs all at one level: `dim` that
    level exactly; otherwise `pause` (the widget's setManual)."""
    levels = [b.get("output") for b in selection_bulbs(st)
              if b.get("power") is not False and b.get("online") is not False]
    if levels and all(isinstance(x, (int, float)) and x > 0 and abs(x - levels[0]) < 0.05 for x in levels):
        return ["dim", fmt(levels[0]) if float(levels[0]).is_integer() else str(levels[0])]
    return ["pause"]


def automatic_cmd(st: dict) -> list:
    """The "Automatic" item flips the mode: resume following, or hold."""
    return ["resume"] if manual(st) else hold_cmd(st)


def toggle_cmd(st: Optional[dict]) -> list:
    return ["toggle"]


def light_cmd(st: dict) -> list:
    return ["off"] if st.get("power") is True else ["on"]


def clap_supported(st: dict) -> bool:
    cs = st.get("clap_status")
    return "clap" in st and isinstance(cs, dict) and cs.get("available") is not False


def clap_cmd(st: dict, clap_last: str = "both") -> list:
    on = st.get("clap") not in (None, "off")
    return ["set", "clap=off" if on else f"clap={clap_last if clap_last in CLAP_MODES else 'both'}"]


def link_cmd(b: dict) -> tuple:
    """Per bulb, as the widget's connect-on-press: a connected bulb is held
    off its link (`disconnect`), any other is connected."""
    return (["disconnect"], b.get("id")) if bulb_link(b) == "connected" else (["connect"], b.get("id"))


def build_menu(st: Optional[dict], tr, clap_last: str = "both") -> list:
    items: list[Item] = []
    if st is None:
        items += [Item("status", tr("Service not running"), enabled=False),
                  Item("start", tr("Start service"), special="start-service"),
                  sep("s-end"),
                  Item("settings", tr("Settings…"), special="settings"),
                  Item("quit", tr("Quit"), special="quit")]
        return items
    if not protocol_ok(st):
        items.append(Item("update", tr("Please update Lichthaus"), enabled=False))
    items.append(Item("status", status_text(st, tr), enabled=False))
    items.append(sep("s-status"))
    has_bulbs = bool(widget_bulbs(st))
    items.append(Item("light", tr("Light"), checkable=True, checked=st.get("power") is True,
                      enabled=has_bulbs, cmd=light_cmd(st)))

    level = shown_level(st)
    title = tr("Brightness: %1 %", fmt(level)) if level is not None else tr("Brightness")
    bright = Item("brightness", title, kind="menu", enabled=has_bulbs)
    for v in BRIGHTNESS_STEPS:
        bright.children.append(Item(f"bright-{v}", f"{v} %", checkable=True, group="brightness",
                                    checked=level is not None and abs(float(level) - v) < 0.05,
                                    cmd=["bulb", str(v)]))
    items.append(bright)

    items.append(Item("automatic", tr("Automatic"), checkable=True,
                      checked=not manual(st) and not follow_on(st), enabled=has_bulbs,
                      cmd=automatic_cmd(st)))

    profiles = Item("profiles", tr("Profiles"), kind="menu")
    for name in st.get("profiles") or ["default"]:
        profiles.children.append(Item(f"profile-{name}", name, checkable=True, group="profile",
                                      checked=name == st.get("profile"),
                                      cmd=["profile", "apply", name]))
    items.append(profiles)

    if clap_supported(st):
        items.append(Item("clap", tr("Clap to toggle"), checkable=True,
                          checked=st.get("clap") not in (None, "off"), cmd=clap_cmd(st, clap_last)))

    bulbs = Item("bulbs", tr("Bulbs"), kind="menu")
    sel = st.get("selected") or "all"
    bulbs.children.append(Item("select-all", tr("All"), checkable=True, group="select",
                               checked=sel == "all", cmd=["select", "all"]))
    wb = widget_bulbs(st)
    for b in wb:
        bulbs.children.append(Item(f"select-{b['id']}", b.get("name") or b["id"], checkable=True,
                                   group="select", checked=sel == b["id"], cmd=["select", b["id"]]))
    if wb:
        bulbs.children.append(sep("s-links"))
    for b in wb:
        cmd, which = link_cmd(b)
        text = tr("Disconnect %1" if cmd == ["disconnect"] else "Connect %1", b.get("name") or b["id"])
        bulbs.children.append(Item(f"link-{b['id']}", text, cmd=cmd, which=which))
    items.append(bulbs)

    items += [sep("s-end"),
              Item("settings", tr("Settings…"), special="settings"),
              Item("quit", tr("Quit"), special="quit")]
    return items


def menu_key(items: list) -> tuple:
    """A comparable summary: rebuild the Qt menu only when this changes."""
    return tuple((i.id, i.text, i.kind, i.checkable, i.checked, i.enabled, tuple(i.cmd or ()),
                  i.which, menu_key(i.children)) for i in items)
