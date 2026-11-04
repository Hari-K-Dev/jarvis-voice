"""Synthesis and playback. Only one voice speaks at a time, across all sessions."""

import fcntl
import json
import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from . import config
from .log import log

MULTI_SESSION_WINDOW = 1800


@contextmanager
def speech_lock() -> Iterator[None]:
    """Blocks until any other session has finished talking."""
    config.HOME.mkdir(parents=True, exist_ok=True)
    with config.LOCK.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def project_name(cwd: str) -> str:
    path = Path(cwd)
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate.name
    return path.name


def with_project_prefix(brief: str, cwd: str, now: float | None = None) -> str:
    """Name the project only when another project has spoken recently."""
    now = time.time() if now is None else now
    project = project_name(cwd) if cwd else ""
    try:
        recent = json.loads(config.RECENT.read_text())
    except (OSError, ValueError):
        recent = {}
    recent = {k: v for k, v in recent.items() if now - v < MULTI_SESSION_WINDOW}
    others = [name for name in recent if name != project]
    if project:
        recent[project] = now
    try:
        config.RECENT.write_text(json.dumps(recent))
    except OSError as exc:
        log(f"could not save recent projects: {exc}")
    return f"{project}: {brief}" if project and others else brief


def synthesise(text: str, path: str) -> None:
    # Imported here so the hook and CLI stay quick.
    import soundfile
    from kokoro_onnx import Kokoro

    engine = Kokoro(
        str(config.model_path("kokoro-v1.0.onnx")), str(config.model_path("voices-v1.0.bin"))
    )
    samples, rate = engine.create(text, voice=config.VOICE, speed=config.SPEED, lang=config.LANG)
    soundfile.write(path, samples, rate)


def play(path: str) -> None:
    player = subprocess.Popen(["afplay", path])
    config.PLAYER_PID.write_text(str(player.pid))
    try:
        player.wait(timeout=60)
    except subprocess.TimeoutExpired:
        player.kill()
        log("playback timed out")
    finally:
        config.PLAYER_PID.unlink(missing_ok=True)


def stop_playback() -> bool:
    try:
        os.kill(int(config.PLAYER_PID.read_text()), signal.SIGTERM)
        return True
    except (OSError, ValueError):
        return False


def speak(text: str) -> None:
    """Speak with Kokoro, falling back to the macOS voice so a brief is never lost."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "brief.wav")
        try:
            started = time.time()
            synthesise(text, wav)
            log(f"synthesised {len(text)} chars in {time.time() - started:.2f}s")
        except Exception as exc:  # noqa: BLE001 - any engine failure must still produce speech
            log(f"kokoro failed, using say: {type(exc).__name__}: {exc}")
            subprocess.run(["say", "-v", "Daniel", text], check=False, timeout=60)
            return
        play(wav)
