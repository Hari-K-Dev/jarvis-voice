import stat
import subprocess
import sys

import pytest

from jarvis_voice import config, speech, system
from jarvis_voice.log import log


def _broken_engine(monkeypatch):
    def broken(*a):
        raise RuntimeError("SECRET-BRIEF")

    monkeypatch.setattr(speech, "synthesise", broken)


def test_kokoro_failure_uses_the_system_voice_with_text_on_stdin(monkeypatch):
    """The text stays out of the arguments, so it can never be run as code."""
    calls = []
    _broken_engine(monkeypatch)
    monkeypatch.setattr(system, "fallback_voice_command", lambda: ["voice", "--stdin"])
    monkeypatch.setattr(speech.subprocess, "run", lambda cmd, **k: calls.append((cmd, k["input"])))
    speech.speak("Acme, a fix.", "Done.")
    assert calls == [(["voice", "--stdin"], "Acme, a fix. Done.")]


def test_stop_playback_with_nothing_playing():
    assert speech.stop_playback() is False


def test_system_voice_timeout_leaves_no_brief_text_in_the_log(monkeypatch):
    """Regression: TimeoutExpired's message can quote its command."""

    def slow(cmd, **k):
        raise subprocess.TimeoutExpired(cmd, 60)

    _broken_engine(monkeypatch)
    monkeypatch.setattr(system, "fallback_voice_command", lambda: ["voice"])
    monkeypatch.setattr(speech.subprocess, "run", slow)
    speech.speak("SECRET-BRIEF")
    text = config.LOG.read_text(encoding="utf-8")
    assert "system voice failed: TimeoutExpired" in text and "SECRET" not in text


def test_no_system_voice_is_logged_not_fatal(monkeypatch):
    _broken_engine(monkeypatch)
    monkeypatch.setattr(system, "fallback_voice_command", lambda: None)
    speech.speak("Done.")
    assert "no system voice found" in config.LOG.read_text(encoding="utf-8")


def test_no_audio_player_is_logged_not_fatal(monkeypatch):
    monkeypatch.setattr(system, "player_command", lambda path: None)
    speech.play("x.wav")
    assert "no audio player found" in config.LOG.read_text(encoding="utf-8")


def test_player_failure_is_logged_and_clears_the_pid(monkeypatch):
    monkeypatch.setattr(system, "player_command", lambda path: [sys.executable, "-c", "exit(3)"])
    speech.play("x.wav")
    assert "audio player exited 3" in config.LOG.read_text(encoding="utf-8")
    assert not config.PLAYER_PID.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows relies on profile ACLs instead")
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
