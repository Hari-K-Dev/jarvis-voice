import json

from jarvis_voice import cli

EXISTING = {
    "voice": {"enabled": True},
    "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "afplay x"}]}]},
}


def test_add_is_idempotent_and_keeps_other_hooks():
    settings = json.loads(json.dumps(EXISTING))
    assert cli.add_hook(settings, "/v/bin/jarvis-hook") is True
    assert cli.add_hook(settings, "/v/bin/jarvis-hook") is False
    assert len(settings["hooks"]["Stop"]) == 2
    assert settings["hooks"]["Stop"][0]["hooks"][0]["command"] == "afplay x"
    assert settings["voice"] == {"enabled": True}


def test_remove_restores_the_original():
    settings = json.loads(json.dumps(EXISTING))
    cli.add_hook(settings, "/v/bin/jarvis-hook")
    assert cli.remove_hook(settings) is True
    assert settings == EXISTING
    assert cli.remove_hook(settings) is False


def test_write_settings_makes_a_backup(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"a": 1}')
    cli.write_settings({"a": 2}, path)
    assert json.loads(path.read_text()) == {"a": 2}
    backups = list(tmp_path.glob("settings.json.bak-jarvis-*"))
    assert len(backups) == 1 and json.loads(backups[0].read_text()) == {"a": 1}
