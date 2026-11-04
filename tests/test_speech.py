import stat
import subprocess

from jarvis_voice import config, speech
from jarvis_voice.log import log


def test_single_project_has_no_prefix(tmp_path):
    a = tmp_path / "alpha"
    a.mkdir()
    assert speech.with_project_prefix("Done.", str(a), now=1000) == "Done."
    assert speech.with_project_prefix("Done.", str(a), now=1100) == "Done."


def test_second_project_is_named_while_two_are_active(tmp_path):
    a, b = tmp_path / "alpha", tmp_path / "beta"
    a.mkdir()
    b.mkdir()
    speech.with_project_prefix("Done.", str(a), now=1000)
    assert speech.with_project_prefix("Done.", str(b), now=1100) == "beta: Done."
    assert speech.with_project_prefix("Done.", str(a), now=1200) == "alpha: Done."


def test_old_projects_stop_counting(tmp_path):
    a, b = tmp_path / "alpha", tmp_path / "beta"
    a.mkdir()
    b.mkdir()
    speech.with_project_prefix("Done.", str(a), now=1000)
    assert speech.with_project_prefix("Done.", str(b), now=1000 + 3600) == "Done."


def test_corrupt_state_does_not_lose_the_brief(tmp_path):
    config.RECENT.write_text("{not json")
    assert speech.with_project_prefix("Done.", str(tmp_path), now=1) == "Done."


def test_project_name_uses_the_repo_root(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    (tmp_path / "repo" / "src").mkdir()
    assert speech.project_name(str(tmp_path / "repo" / "src")) == "repo"


def test_kokoro_failure_falls_back_to_say(monkeypatch):
    calls = []

    def broken(*a):
        raise RuntimeError("model missing")

    monkeypatch.setattr(speech, "synthesise", broken)
    monkeypatch.setattr(speech.subprocess, "run", lambda cmd, **k: calls.append(cmd))
    speech.speak("Done.")
    assert calls[0][:3] == ["say", "-v", "Daniel"]


def test_stop_playback_with_nothing_playing():
    assert speech.stop_playback() is False


def test_say_timeout_leaves_no_brief_text_in_the_log(monkeypatch):
    """Regression: TimeoutExpired's message quotes the command, which holds the brief."""

    def broken(*a):
        raise RuntimeError("SECRET-BRIEF")

    def slow_say(cmd, **k):
        raise subprocess.TimeoutExpired(cmd, 60)

    monkeypatch.setattr(speech, "synthesise", broken)
    monkeypatch.setattr(speech.subprocess, "run", slow_say)
    speech.speak("SECRET-BRIEF")
    text = config.LOG.read_text()
    assert "say failed: TimeoutExpired" in text and "SECRET" not in text


def test_state_is_private_to_the_owner(tmp_path):
    config.HOME.chmod(0o755)
    log("hello")
    assert stat.S_IMODE(config.HOME.stat().st_mode) == 0o700
    assert stat.S_IMODE(config.LOG.stat().st_mode) == 0o600
