import stat
import subprocess

from jarvis_voice import config, speech
from jarvis_voice.log import log


def test_kokoro_failure_falls_back_to_say(monkeypatch):
    calls = []

    def broken(*a):
        raise RuntimeError("model missing")

    monkeypatch.setattr(speech, "synthesise", broken)
    monkeypatch.setattr(speech.subprocess, "run", lambda cmd, **k: calls.append(cmd))
    speech.speak("Psynapse, a fix.", "Done.")
    assert calls[0] == ["say", "-v", "Daniel", "Psynapse, a fix. Done."]


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


def test_speak_skips_an_empty_announcement_and_keeps_parts_in_order(monkeypatch):
    seen = []
    monkeypatch.setattr(speech, "synthesise", lambda parts, path: seen.extend(parts))
    monkeypatch.setattr(speech, "play", lambda path: None)
    speech.speak("", "Done.")
    assert seen == ["Done."]
