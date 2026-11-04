"""Paths and settings. Override with environment variables."""

import os
from pathlib import Path

HOME = Path(os.environ.get("JARVIS_HOME", "~/.local/share/jarvis-voice")).expanduser()
MODELS = HOME / "models"
MUTED = HOME / "muted"
LOCK = HOME / "speech.lock"
PLAYER_PID = HOME / "player.pid"
RECENT = HOME / "recent.json"
LOG = HOME / "jarvis.log"

VOICE = os.environ.get("JARVIS_VOICE", "bm_fable")
SPEED = float(os.environ.get("JARVIS_SPEED", "1.0"))
LANG = "en-gb"
SUMMARY_MODEL = os.environ.get("JARVIS_SUMMARY_MODEL", "haiku")

MODEL_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
MODEL_FILES = {
    "kokoro-v1.0.onnx": "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}


def model_path(name: str) -> Path:
    return MODELS / name


def is_muted() -> bool:
    return MUTED.exists()
