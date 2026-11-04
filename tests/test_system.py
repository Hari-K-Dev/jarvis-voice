from pathlib import PurePosixPath

import pytest

from jarvis_voice import system


@pytest.fixture
def on(monkeypatch):
    def set_platform(name, installed=()):
        monkeypatch.setattr(system.sys, "platform", name)
        monkeypatch.setattr(
            system.shutil, "which", lambda cmd, **k: cmd if cmd in installed else None
        )

    return set_platform


def test_home_on_each_platform(on):
    on("win32")
    assert system.default_home({"LOCALAPPDATA": "/appdata"}).parts[-2:] == (
        "appdata",
        "jarvis-voice",
    )
    on("linux")
    assert system.default_home({"XDG_DATA_HOME": "/xdg"}).parts[-2:] == ("xdg", "jarvis-voice")
    assert system.default_home({}).parts[-3:] == (".local", "share", "jarvis-voice")
    on("darwin")
    assert system.default_home({"XDG_DATA_HOME": "/xdg"}).parts[-3:] == (
        ".local",
        "share",
        "jarvis-voice",
    )


def test_mac_commands(on):
    on("darwin")
    assert system.player_command("a.wav") == ["afplay", "a.wav"]
    assert system.fallback_voice_command() == ["say", "-v", "Daniel"]


def test_linux_prefers_paplay_then_works_down_the_list(on):
    on("linux", installed=("paplay", "aplay"))
    assert system.player_command("a.wav") == ["paplay", "a.wav"]
    on("linux", installed=("aplay",))
    assert system.player_command("a.wav") == ["aplay", "-q", "a.wav"]
    on("linux", installed=("ffplay",))
    assert system.player_command("a.wav")[0] == "ffplay"


def test_linux_with_nothing_installed(on):
    on("linux")
    assert system.player_command("a.wav") is None
    assert system.fallback_voice_command() is None


def test_linux_system_voice_reads_stdin(on):
    on("linux", installed=("espeak-ng",))
    assert system.fallback_voice_command() == ["espeak-ng", "--stdin", "-v", "en-gb"]


def test_windows_never_puts_the_path_or_text_in_the_script(on):
    """Regression guard: a quote in a path or brief must not become PowerShell code."""
    on("win32")
    awkward = "C:/it's; Remove-Item x.wav"
    assert not any(awkward in part for part in system.player_command(awkward))
    assert "$env:JARVIS_WAV" in system.player_command(awkward)[-1]
    assert "[Console]::In.ReadToEnd()" in system.fallback_voice_command()[-1]


def test_process_flags(on):
    on("win32")
    assert "creationflags" in system.detached_kwargs()
    assert system.no_window_flags() != 0
    on("linux")
    assert system.detached_kwargs() == {"start_new_session": True}
    assert system.no_window_flags() == 0


def test_find_claude_reports_a_missing_command(on):
    on("linux")
    with pytest.raises(FileNotFoundError):
        system.find_claude()


def test_find_claude_checks_the_native_install_folder(monkeypatch):
    def which(cmd, path=None):
        return "/home/me/.local/bin/claude" if path else None

    monkeypatch.setattr(system.shutil, "which", which)
    assert PurePosixPath(system.find_claude()).name == "claude"
