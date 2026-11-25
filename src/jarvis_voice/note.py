"""Turns a finished turn into a voice note, for programs that deliver it somewhere else."""

import math
import os
import subprocess
import tempfile

from . import config, system
from .brief import clean
from .speech import speech_lock, synthesise
from .worker import prepare


def encode_voice_note(wav: str, out: str) -> None:
    """Ogg Opus, the format messaging apps show as a voice note rather than an audio file."""
    ffmpeg = system.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            wav,
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "libopus",
            "-b:a",
            "32k",
            "-application",
            "voip",
            "-f",
            "ogg",
            out,
        ],
        check=True,
        capture_output=True,
        timeout=30,
        cwd=config.HOME,
        creationflags=system.no_window_flags(),
    )


def render(payload: dict, out: str) -> dict:
    """Writes the note to `out`. There is no system voice fallback: the caller falls back to text.

    `complete` means the brief is the whole reply, so a full text copy would only repeat it.
    """
    # Imported here so the jarvis command stays quick.
    import soundfile

    config.ensure_home()
    heading, brief = prepare(payload)
    parts = [part for part in (heading, brief.text) if part]
    with tempfile.TemporaryDirectory(dir=config.HOME) as tmp:
        wav = os.path.join(tmp, "note.wav")
        # One model in memory at a time when several sessions finish together.
        with speech_lock():
            synthesise(parts, wav)
        duration = math.ceil(soundfile.info(wav).duration)
        encode_voice_note(wav, out)
    return {
        "caption": "\n".join(parts),
        "duration": duration,
        "complete": clean(payload["last_assistant_message"]) == brief.text,
    }
