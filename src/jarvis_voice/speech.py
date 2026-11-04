"""Synthesis and playback. Only one voice speaks at a time, across all sessions."""

import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager

from filelock import FileLock

from . import config, system
from .log import log

PAUSE_SECONDS = 0.45


@contextmanager
def speech_lock() -> Iterator[None]:
    """Blocks until any other session has finished talking."""
    config.ensure_home()
    # The operating system releases this if a process dies, so it cannot get stuck.
    with FileLock(config.LOCK):
        yield


def synthesise(parts: list[str], path: str) -> None:
    # Imported here so the hook and CLI stay quick.
    import numpy
    import soundfile
    from kokoro_onnx import Kokoro

    engine = Kokoro(
        str(config.model_path("kokoro-v1.0.onnx")), str(config.model_path("voices-v1.0.bin"))
    )
    audio, rate = [], 24000
    for part in parts:
        samples, rate = engine.create(
            part, voice=config.VOICE, speed=config.SPEED, lang=config.LANG
        )
        if audio:
            audio.append(numpy.zeros(int(rate * PAUSE_SECONDS), dtype=samples.dtype))
        audio.append(samples)
    soundfile.write(path, numpy.concatenate(audio), rate)


def play(path: str) -> None:
    config.ensure_home()
    try:
        command = system.player_command(path)
        if not command:
            log("no audio player found, see the README")
            return
        player = subprocess.Popen(
            command,
            env={**os.environ, "JARVIS_WAV": path},
            cwd=config.HOME,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=system.no_window_flags(),
        )
    except OSError as exc:
        log(f"could not start audio player: {type(exc).__name__}")
        return
    config.PLAYER_PID.write_text(str(player.pid), encoding="utf-8")
    try:
        code = player.wait(timeout=60)
        if code != 0:
            log(f"audio player exited {code}")
    except subprocess.TimeoutExpired:
        player.kill()
        log("playback timed out")
    finally:
        config.PLAYER_PID.unlink(missing_ok=True)


def speak_with_system_voice(text: str) -> None:
    config.ensure_home()
    try:
        command = system.fallback_voice_command()
        if not command:
            log("no system voice found")
            return
        subprocess.run(
            command,
            input=text,
            encoding="utf-8",
            cwd=config.HOME,
            check=False,
            timeout=60,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=system.no_window_flags(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"system voice failed: {type(exc).__name__}")


def stop_playback() -> bool:
    try:
        os.kill(int(config.PLAYER_PID.read_text(encoding="utf-8")), signal.SIGTERM)
        return True
    except (OSError, ValueError):
        return False


def speak(*parts: str) -> None:
    """Speak with a short pause between parts. Falls back to a system voice if Kokoro fails."""
    parts = [part for part in parts if part]
    if not parts:
        return
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "brief.wav")
        try:
            started = time.time()
            synthesise(parts, wav)
            log(f"synthesised {sum(map(len, parts))} chars in {time.time() - started:.2f}s")
        except Exception as exc:  # noqa: BLE001 - any engine failure must still produce speech
            log(f"kokoro failed, using the system voice: {type(exc).__name__}")
            speak_with_system_voice(" ".join(parts))
            return
        play(wav)
