"""Paths and settings. Override with environment variables."""

import os
from pathlib import Path

from . import system

HOME = Path(os.environ.get("JARVIS_HOME") or system.default_home()).expanduser()
MODELS = HOME / "models"
MUTED = HOME / "muted"
AWAY = HOME / "away"
LOCK = HOME / "speech.lock"
PLAYER_PID = HOME / "player.pid"
TASKS = HOME / "tasks"
NAMES = HOME / "names.json"
LOG = HOME / "jarvis.log"

VOICE = os.environ.get("JARVIS_VOICE", "bm_fable")
SPEED = float(os.environ.get("JARVIS_SPEED", "1.0"))
LANG = "en-gb"
SUMMARY_MODEL = os.environ.get("JARVIS_SUMMARY_MODEL", "haiku")
WHISPER_MODEL = os.environ.get("JARVIS_WHISPER_MODEL", "small.en")

MODEL_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
MODEL_FILES = {
    "kokoro-v1.0.onnx": "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}

# Whisper models we will load by name: the exact Hugging Face commit and what its files hash to.
WHISPER_PINS = {
    "small.en": (
        "d1d751a5f8271d482d14ca55d9e2deeebbae577f",
        {
            "config.json": "666a9605530ac1f61fa8177f3702b4dacec9966749e42610839fcc32661d5fae",
            "model.bin": "62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a",
            "tokenizer.json": "929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df",
            "vocabulary.txt": "ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf",
        },
    ),
}


def ensure_home() -> None:
    """State can reveal project names and timings, so only the owner may read it."""
    HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    system.restrict(HOME, 0o700)


def model_path(name: str) -> Path:
    return MODELS / name


def is_muted() -> bool:
    return MUTED.exists()


def is_away() -> bool:
    """Nobody is at the desk, so the speakers stay off. Voice notes still go out."""
    return AWAY.exists()
