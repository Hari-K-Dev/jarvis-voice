"""Speech to text, on this machine. Needs the optional `listen` extra."""

from . import config


def _load_model():
    # Imported here because it is optional and slow, and nothing else needs it.
    from faster_whisper import WhisperModel

    config.ensure_home()
    options = {
        "device": "cpu",
        "compute_type": "int8",
        "download_root": str(config.MODELS / "whisper"),
    }
    try:
        # No network once the model is here, so a Hugging Face outage cannot stop a voice note.
        return WhisperModel(config.WHISPER_MODEL, local_files_only=True, **options)
    except Exception:  # noqa: BLE001 - the library's error for "not downloaded yet" is not stable
        return WhisperModel(config.WHISPER_MODEL, **options)


def transcribe(path: str) -> str:
    segments, _info = _load_model().transcribe(
        path,
        language="en",
        # Skips gaps in the audio, where background noise tends to become invented words.
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()
