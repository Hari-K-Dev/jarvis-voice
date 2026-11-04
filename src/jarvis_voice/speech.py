"""Synthesis and playback. Only one voice speaks at a time, across all sessions."""

import fcntl
import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager

from . import config
from .log import log

PAUSE_SECONDS = 0.45


@contextmanager
def speech_lock() -> Iterator[None]:
    """Blocks until any other session has finished talking."""
    config.ensure_home()
    with config.LOCK.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
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


def speak(*parts: str) -> None:
    """Speak with a short pause between parts. Falls back to the macOS voice if Kokoro fails."""
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
            log(f"kokoro failed, using say: {type(exc).__name__}")
            try:
                subprocess.run(["say", "-v", "Daniel", " ".join(parts)], check=False, timeout=60)
            except (OSError, subprocess.SubprocessError) as say_exc:
                log(f"say failed: {type(say_exc).__name__}")
            return
        play(wav)
