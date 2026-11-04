import pytest

from jarvis_voice import config


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Tests never touch real state."""
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "MUTED", tmp_path / "muted")
    monkeypatch.setattr(config, "LOCK", tmp_path / "speech.lock")
    monkeypatch.setattr(config, "PLAYER_PID", tmp_path / "player.pid")
    monkeypatch.setattr(config, "TASKS", tmp_path / "tasks")
    monkeypatch.setattr(config, "NAMES", tmp_path / "names.json")
    monkeypatch.setattr(config, "LOG", tmp_path / "jarvis.log")
    return tmp_path
