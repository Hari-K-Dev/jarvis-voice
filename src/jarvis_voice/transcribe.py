"""Speech to text, on this machine. Needs the optional `listen` extra."""

import hashlib
import os
from pathlib import Path

from . import config


def _verified(folder: str, files: dict[str, str]) -> bool:
    for name, expected in files.items():
        try:
            with open(Path(folder) / name, "rb") as f:
                if hashlib.file_digest(f, "sha256").hexdigest() != expected:
                    return False
        except OSError:
            return False
    return True


def _model_path() -> str:
    """An absolute path, always: the library would treat a bare name as a folder in the cwd."""
    name = config.WHISPER_MODEL
    if os.path.isabs(name):
        return name
    if name not in config.WHISPER_PINS:
        raise ValueError("JARVIS_WHISPER_MODEL must be a pinned model or an absolute path")
    from faster_whisper import download_model

    revision, files = config.WHISPER_PINS[name]
    options = {"cache_dir": str(config.MODELS / "whisper"), "revision": revision}
    try:
        # No network once the model is here, so a Hugging Face outage cannot stop a voice note.
        folder = download_model(name, local_files_only=True, **options)
        found = all((Path(folder) / f).exists() for f in files)
    except Exception:  # noqa: BLE001 - the library's error for "not downloaded yet" is not stable
        found = False
    if not found:
        folder = download_model(name, **options)
    if not _verified(folder, files):
        raise RuntimeError("the speech model failed its integrity check")
    return folder


def _load_model():
    # Imported here because it is optional and slow, and nothing else needs it.
    from faster_whisper import WhisperModel

    config.ensure_home()
    return WhisperModel(_model_path(), device="cpu", compute_type="int8", local_files_only=True)


def transcribe(path: str) -> str:
    segments, _info = _load_model().transcribe(
        path,
        language="en",
        # Skips gaps in the audio, where background noise tends to become invented words.
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()
