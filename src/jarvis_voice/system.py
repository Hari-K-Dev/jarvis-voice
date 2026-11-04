"""Everything that differs between macOS, Linux and Windows lives here."""

import os
import shutil
import sys
from pathlib import Path

# Numeric because the subprocess constants only exist on Windows.
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000

_POWERSHELL_ARGS = ["-NoProfile", "-NonInteractive", "-Command"]
# The file path and spoken text reach PowerShell through the environment and stdin, never the
# script itself, so nothing in them can be run as code.
_WINDOWS_PLAY = "(New-Object System.Media.SoundPlayer $env:JARVIS_WAV).PlaySync()"
_WINDOWS_SPEAK = (
    "[Console]::InputEncoding = [Text.Encoding]::UTF8; "
    "Add-Type -AssemblyName System.Speech; "
    "(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak([Console]::In.ReadToEnd())"
)


def is_windows() -> bool:
    return sys.platform == "win32"


def default_home(env: dict | None = None) -> Path:
    env = os.environ if env is None else env
    if is_windows() and env.get("LOCALAPPDATA"):
        return Path(env["LOCALAPPDATA"]) / "jarvis-voice"
    if sys.platform.startswith("linux") and env.get("XDG_DATA_HOME"):
        return Path(env["XDG_DATA_HOME"]) / "jarvis-voice"
    return Path("~/.local/share/jarvis-voice").expanduser()


def restrict(path: Path, mode: int) -> None:
    """Owner-only access. Windows has no such modes: the user profile's ACLs do this job."""
    if not is_windows():
        os.chmod(path, mode)


def detached_kwargs() -> dict:
    """Lets the worker outlive the hook, and the session that started it."""
    if is_windows():
        return {"creationflags": _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def no_window_flags() -> int:
    """Stops console windows flashing up on Windows. Zero elsewhere."""
    return _CREATE_NO_WINDOW if is_windows() else 0


def which(name: str) -> str | None:
    """Absolute path to a program, from absolute PATH entries only.

    Tools run from inside whatever project a session is in, and that project may be untrusted.
    Windows searches the current folder first, so a planted claude.exe could otherwise run.
    """
    # Python's own which() adds the current folder on Windows unless this is set.
    os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"
    entries = os.environ.get("PATH", "").split(os.pathsep)
    trusted = os.pathsep.join(entry for entry in entries if os.path.isabs(entry))
    found = shutil.which(name, path=trusted)
    return found if found and os.path.isabs(found) else None


def _windows_system_dir() -> str:
    """From the Windows API, because SystemRoot is an environment variable anyone can set."""
    import ctypes

    buffer = ctypes.create_unicode_buffer(260)
    if not ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer)):
        raise OSError("could not find the Windows system folder")
    return buffer.value


def _powershell(script: str) -> list[str]:
    executable = os.path.join(_windows_system_dir(), "WindowsPowerShell", "v1.0", "powershell.exe")
    return [executable, *_POWERSHELL_ARGS, script]


def player_command(path: str) -> list[str] | None:
    """How to play a WAV file, or None if nothing suitable is installed."""
    if is_windows():
        return _powershell(_WINDOWS_PLAY)
    if sys.platform == "darwin":
        found = which("afplay")
        return [found, path] if found else None
    for name, *options in (
        ["paplay"],
        ["pw-play"],
        ["aplay", "-q"],
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
    ):
        found = which(name)
        if found:
            return [found, *options, path]
    return None


def fallback_voice_command() -> list[str] | None:
    """A system voice that reads text from stdin, or None if there is not one."""
    if is_windows():
        return _powershell(_WINDOWS_SPEAK)
    if sys.platform == "darwin":
        found = which("say")
        return [found, "-v", "Daniel"] if found else None
    for name in ("espeak-ng", "espeak"):
        found = which(name)
        if found:
            return [found, "--stdin", "-v", "en-gb"]
    return None


def find_claude() -> str:
    """Absolute path, which also lets Windows start the npm .cmd shim."""
    found = which("claude") or shutil.which("claude", path=str(Path("~/.local/bin").expanduser()))
    if not found or not os.path.isabs(found):
        raise FileNotFoundError("claude")
    return found
