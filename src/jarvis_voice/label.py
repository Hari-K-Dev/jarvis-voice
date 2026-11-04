"""Works out which project and task a brief belongs to, so it can be announced first."""

import json
import os
import re
import tempfile
import time
from pathlib import Path

from . import config
from .log import log

TAIL_BYTES = 3_000_000
MAX_REQUEST = 1500
TASK_MAX_AGE = 7 * 24 * 3600
_SAFE_ID = re.compile(r"^[\w-]{1,128}$")
_TAG_BLOCK = re.compile(r"<([a-z][\w-]*)\b[^>]*>.*?</\1>", re.DOTALL)


def last_request(transcript_path: str) -> str:
    """The person's latest message. Tool results, subagents and system notices are skipped."""
    if not transcript_path:
        return ""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - TAIL_BYTES))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except OSError as exc:
        log(f"could not read transcript: {type(exc).__name__}")
        return ""
    for line in reversed(lines):
        text = _request_text(line)
        if text:
            return text[:MAX_REQUEST]
    return ""


def _request_text(line: str) -> str:
    try:
        row = json.loads(line)
        if row.get("type") != "user" or row.get("isMeta") or row.get("isSidechain"):
            return ""
        content = row["message"]["content"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return ""
    if isinstance(content, list):
        content = " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    if not isinstance(content, str):
        return ""
    return _TAG_BLOCK.sub("", content).strip()


def project_name(cwd: str) -> str:
    path = Path(cwd)
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate.name
    return path.name


def _load_names() -> dict:
    try:
        names = json.loads(config.NAMES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return names if isinstance(names, dict) else {}


def spoken_project(cwd: str) -> str:
    """A chosen spoken name if there is one, otherwise the folder name without punctuation."""
    if not cwd:
        return ""
    folder = project_name(cwd)
    return str(_load_names().get(folder) or re.sub(r"[-_.]+", " ", folder)).strip()


def set_spoken_name(folder: str, spoken: str) -> None:
    config.ensure_home()
    _write_atomic(config.NAMES, json.dumps({**_load_names(), folder: spoken}, indent=2))


def _write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _task_file(session_id: str) -> Path | None:
    return config.TASKS / session_id if _SAFE_ID.match(session_id or "") else None


def load_task(session_id: str) -> str:
    path = _task_file(session_id)
    try:
        return path.read_text(encoding="utf-8").strip() if path else ""
    except OSError:
        return ""


def save_task(session_id: str, task: str, now: float | None = None) -> None:
    path = _task_file(session_id)
    if not path or not task:
        return
    now = time.time() if now is None else now
    try:
        config.ensure_home()
        config.TASKS.mkdir(exist_ok=True, mode=0o700)
        _write_atomic(path, task)
        for old in config.TASKS.iterdir():
            if now - old.stat().st_mtime > TASK_MAX_AGE:
                old.unlink(missing_ok=True)
    except OSError as exc:
        log(f"could not save task: {type(exc).__name__}")


def announcement(project: str, task: str) -> str:
    """For example: "Acme, delivery policy fix." """
    text = ", ".join(part for part in (project, task) if part)
    return f"{text}." if text else ""
