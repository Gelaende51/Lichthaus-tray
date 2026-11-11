import os
import stat

from lichthaus_tray import actions, model
from lichthaus_tray.i18n import Tr, is_german
from conftest import sample_state

EN, DE = Tr(False), Tr(True)


def by_id(items, i):
    for it in items:
        if it.id == i:
            return it
        found = by_id(it.children, i)
        if found:
            return found
    return None


def test_menu_items_and_states():
    st = sample_state()
    items = model.build_menu(st, EN)
    assert [i.id for i in items] == ["status", "s-status", "light", "brightness", "automatic", "profiles",
                                     "clap", "bulbs", "s-end", "settings", "quit"]
    assert by_id(items, "status").text == "Connected" and not by_id(items, "status").enabled
    light = by_id(items, "light")
    assert light.checkable and light.checked and light.cmd == ["off"]
    b = by_id(items, "brightness")
    assert b.text == "Brightness: 50 %"
    assert [c.text for c in b.children] == ["1 %", "10 %", "25 %", "50 %", "75 %", "100 %"]
    assert [c.checked for c in b.children] == [False, False, False, True, False, False]
    assert by_id(items, "bright-25").cmd == ["bulb", "25"]
    auto = by_id(items, "automatic")
    assert auto.checked
    assert auto.cmd == ["dim", "50"]  # the lit bulbs (Desk) at one level: hold it exactly
    assert model.hold_cmd(sample_state(bulbs_list=[dict(sample_state()["bulbs_list"][0]),
                                                    dict(sample_state()["bulbs_list"][0], id="mock:2", output=20.0)])) == ["pause"]
    prof = by_id(items, "profiles").children
    assert [(p.text, p.checked, p.group) for p in prof] == [("default", True, "profile"),
                                                             ("evening", False, "profile")]
    assert by_id(items, "profile-evening").cmd == ["profile", "apply", "evening"]
    clap = by_id(items, "clap")
    assert clap.checkable and not clap.checked and clap.cmd == ["set", "clap=both"]
    bulbs = by_id(items, "bulbs").children
    assert [c.id for c in bulbs] == ["select-all", "select-mock:1", "select-mock:2", "s-links",
                                     "link-mock:1", "link-mock:2"]
    assert by_id(items, "select-all").checked and by_id(items, "select-mock:1").cmd == ["select", "mock:1"]
    # Connect-on-press: connected -> disconnect, held -> connect, by `which`.
    l1, l2 = by_id(items, "link-mock:1"), by_id(items, "link-mock:2")
    assert (l1.text, l1.cmd, l1.which) == ("Disconnect Desk", ["disconnect"], "mock:1")
    assert (l2.text, l2.cmd, l2.which) == ("Connect Shelf", ["connect"], "mock:2")
    assert by_id(items, "select-mock:3") is None  # not in the widget


def test_hold_and_resume():
    st = sample_state(selected="mock:1")
    assert model.automatic_cmd(st) == ["dim", "50"]
    st["following"] = False
    items = model.build_menu(st, EN)
    assert not by_id(items, "automatic").checked
    assert model.automatic_cmd(st) == ["resume"]
    st = sample_state(following=True, audio=True, audio_level=30.0)
    assert not by_id(model.build_menu(st, EN), "automatic").checked
    assert by_id(model.build_menu(st, EN), "brightness").text == "Brightness: 30 %"


def test_light_off_and_clap_on():
    st = sample_state(power=False, bulbs=0.0, clap="snap")
    items = model.build_menu(st, EN, clap_last="snap")
    assert not by_id(items, "light").checked and by_id(items, "light").cmd == ["on"]
    assert by_id(items, "clap").checked and by_id(items, "clap").cmd == ["set", "clap=off"]
    assert model.clap_cmd(sample_state(), "snap") == ["set", "clap=snap"]


def test_clap_hidden_without_support():
    st = sample_state(clap_status={"available": False})
    assert by_id(model.build_menu(st, EN), "clap") is None
    st = sample_state()
    st.pop("clap")
    assert by_id(model.build_menu(st, EN), "clap") is None


def test_unreachable_menu():
    items = model.build_menu(None, EN)
    assert [(i.id, i.text) for i in items if i.kind != "separator"] == [
        ("status", "Service not running"), ("start", "Start service"), ("settings", "Settings…"),
        ("quit", "Quit")]
    assert by_id(items, "start").special == "start-service"
    assert model.icon_state(None) == "disconnected"
    assert model.tooltip(None, EN) == "Lichthaus\nService not running"


def test_protocol_too_old():
    st = sample_state()
    st.pop("protocol")
    items = model.build_menu(st, EN)
    assert items[0].id == "update" and items[0].text == "Please update Lichthaus" and not items[0].enabled
    assert by_id(items, "light") is not None  # still usable
    assert by_id(model.build_menu(sample_state(protocol=0), EN), "update")
    assert by_id(model.build_menu(sample_state(), EN), "update") is None


def test_status_lines():
    assert model.status_text(sample_state(link="held"), EN) == "Idle (disconnected)"
    assert model.status_text(sample_state(link="failed", link_reason="offline"), EN) == "Not connected: offline"
    assert model.status_text(sample_state(link="failed", link_reason="offline"), DE) == "Nicht verbunden: offline"
    assert model.status_text(sample_state(in_widget=[]), EN) == "No bulbs"


def test_icon_state():
    assert model.icon_state(sample_state()) == "on"
    assert model.icon_state(sample_state(power=False, bulbs=0.0)) == "off"
    assert model.icon_state(sample_state(link="held")) == "disconnected"
    assert model.icon_state(sample_state(link="failed")) == "disconnected"
    assert model.icon_state(sample_state(link=None, online=False)) == "disconnected"


def test_tooltip():
    assert model.tooltip(sample_state(), EN) == "Lichthaus\nDesk: on, 50 %, connected\nShelf: off, 0 %, disconnected"
    assert model.tooltip(sample_state(), DE) == "Lichthaus\nDesk: an, 50 %, verbunden\nShelf: aus, 0 %, getrennt"


def test_german_menu():
    items = model.build_menu(sample_state(), DE)
    texts = [i.text for i in items if i.kind != "separator"]
    assert texts == ["Verbunden", "Licht", "Helligkeit: 50 %", "Automatisch", "Profile", "Klatschen schaltet",
                     "Lampen", "Einstellungen…", "Beenden"]
    assert by_id(items, "select-all").text == "Alle"
    assert by_id(items, "link-mock:1").text == "Desk trennen"
    assert by_id(items, "link-mock:2").text == "Shelf verbinden"
    assert [i.text for i in model.build_menu(None, DE) if i.kind != "separator"][:2] == [
        "Dienst läuft nicht", "Dienst starten"]


def test_every_string_translated():
    for st in (sample_state(), None, sample_state(protocol=0, link="failed")):
        def flat(items):
            for i in items:
                if i.kind != "separator" and not i.id.startswith(("profile-", "bright-", "select-mock")):
                    yield i.id, i.text
                yield from flat(i.children)
        en, de = dict(flat(model.build_menu(st, EN))), dict(flat(model.build_menu(st, DE)))
        assert en.keys() == de.keys()
        for k in en:
            assert en[k] != de[k], k


def test_is_german():
    assert is_german("de_DE.UTF-8") and is_german("de") and not is_german("en_GB.UTF-8")


def test_level_step():
    assert model.level_step(sample_state()) == 0.5
    assert model.level_step(sample_state(selected="mock:1")) == 1.0


def fake_bin(d, name, body):
    p = d / name
    p.write_text("#!/bin/sh\n" + body + "\n")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return p


def test_start_service_with_fake_systemctl(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "calls"
    fake_bin(bindir, "systemctl", f'echo "$@" >> "{log}"')
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    assert actions.start_service() == (True, "")
    assert log.read_text() == "--user start lichthaus.service\n"
    fake_bin(bindir, "systemctl", 'echo "Unit lichthaus.service not found." >&2; exit 5')
    ok, msg = actions.start_service()
    assert not ok and "not found" in msg


def test_settings_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setenv("PATH", str(bindir))
    assert actions.settings_argv() is None
    fake_bin(bindir, "lichthaus", "true")
    assert actions.settings_argv() == [str(bindir / "lichthaus"), "config"]
    (tmp_path / ".local" / "bin").mkdir(parents=True)
    local = fake_bin(tmp_path / ".local" / "bin", "lichthaus", "true")
    assert actions.settings_argv() == [str(local), "config"]
