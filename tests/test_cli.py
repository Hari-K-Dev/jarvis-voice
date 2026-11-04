import json
import sys

import pytest

from jarvis_voice import cli

EXISTING = {
    "voice": {"enabled": True},
    "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "afplay x"}]}]},
}


ENTRY = {"type": "command", "command": "/v/python", "args": ["-I", "-m", cli.HOOK_MODULE]}


def test_add_is_idempotent_and_keeps_other_hooks():
    settings = json.loads(json.dumps(EXISTING))
    assert cli.add_hook(settings, ENTRY) is True
    assert cli.add_hook(settings, ENTRY) is False
    assert len(settings["hooks"]["Stop"]) == 2
    assert settings["hooks"]["Stop"][0]["hooks"][0]["command"] == "afplay x"
    assert settings["voice"] == {"enabled": True}


def test_add_upgrades_the_old_shell_style_hook_in_place():
    settings = json.loads(json.dumps(EXISTING))
    old = {"hooks": [{"type": "command", "command": "/v/bin/jarvis-hook", "timeout": 5}]}
    settings["hooks"]["Stop"].append(old)
    assert cli.add_hook(settings, ENTRY) is True
    assert old not in settings["hooks"]["Stop"]
    assert settings["hooks"]["Stop"][-1] == {"hooks": [ENTRY]}
    assert len(settings["hooks"]["Stop"]) == 2


def test_hook_entry_needs_no_shell():
    entry = cli.hook_entry()
    assert entry["command"] == sys.executable and "args" in entry
    assert "-I" in entry["args"]


def test_remove_restores_the_original():
    settings = json.loads(json.dumps(EXISTING))
    cli.add_hook(settings, ENTRY)
    assert cli.remove_hook(settings) is True
    assert settings == EXISTING
    assert cli.remove_hook(settings) is False


def test_new_machine_with_no_settings_file(tmp_path):
    path = tmp_path / "new" / "settings.json"
    assert cli.load_settings(path) == {}
    cli.write_settings({"a": 1}, path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}
    assert not list(path.parent.glob("*.bak-jarvis-*"))


def test_broken_settings_are_left_alone(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.load_settings(path)
    assert path.read_text(encoding="utf-8") == "{broken"


def test_non_ascii_settings_survive_a_round_trip(tmp_path):
    """Regression: the default Windows code page would have corrupted these."""
    path = tmp_path / "settings.json"
    path.write_bytes(json.dumps({"name": "caf\u00e9 \u2713"}, ensure_ascii=False).encode("utf-8"))
    cli.write_settings(cli.load_settings(path), path)
    assert "caf\u00e9 \u2713" in path.read_bytes().decode("utf-8")


def test_windows_links_avoid_symlinks(monkeypatch):
    monkeypatch.setattr(cli.system, "is_windows", lambda: True)
    files = cli.link_files()
    assert {path.name for path in files} == {"jarvis", "jarvis.cmd"}
    assert all(files.values())


def test_write_settings_makes_a_backup(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"a": 1}')
    cli.write_settings({"a": 2}, path)
    assert json.loads(path.read_text()) == {"a": 2}
    backups = list(tmp_path.glob("settings.json.bak-jarvis-*"))
    assert len(backups) == 1 and json.loads(backups[0].read_text()) == {"a": 1}
