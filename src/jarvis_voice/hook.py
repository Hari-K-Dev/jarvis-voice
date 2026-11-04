"""Claude Code Stop hook. Hands off and returns at once: it must never block or fail a session."""

import json
import os
import subprocess
import sys

from . import config, system
from .log import log


def skip_reason(payload: dict, env: dict, muted: bool) -> str | None:
    if env.get("JARVIS_SUMMARY"):
        return "summary session"
    # Headless runs (sdk-cli) are other tools' background work, not someone at the desk.
    if env.get("CLAUDE_CODE_ENTRYPOINT") != "cli":
        return f"entrypoint {env.get('CLAUDE_CODE_ENTRYPOINT')}"
    if payload.get("stop_hook_active"):
        return "stop hook continuation"
    if muted:
        return "muted"
    if not (payload.get("last_assistant_message") or "").strip():
        return "no message"
    return None


def worker_command() -> list[str]:
    """Isolated mode (-I), so nothing in the session's project can replace the worker's code."""
    return [sys.executable, "-I", "-m", "jarvis_voice.worker"]


def main() -> None:
    try:
        # Bytes, because Windows would otherwise decode UTF-8 with the local code page.
        payload = json.loads(sys.stdin.buffer.read())
        reason = skip_reason(payload, dict(os.environ), config.is_muted())
        if reason:
            log(f"skipped: {reason}")
            return
        config.ensure_home()
        worker = subprocess.Popen(
            worker_command(),
            cwd=config.HOME,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            **system.detached_kwargs(),
        )
        worker.stdin.write(json.dumps(payload))
        worker.stdin.close()
    except Exception as exc:  # noqa: BLE001 - a voice problem must never surface in the session
        log(f"hook failed: {type(exc).__name__}")
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
