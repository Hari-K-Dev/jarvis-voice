"""Detached process that produces and speaks one brief. Reads the hook payload on stdin."""

import json
import sys
import time

from . import config, label
from .brief import make_brief
from .log import log
from .speech import speak, speech_lock


def run(payload: dict) -> None:
    started = time.time()
    session_id = payload.get("session_id", "")
    cached_task = label.load_task(session_id)
    brief = make_brief(
        payload["last_assistant_message"],
        label.last_request(payload.get("transcript_path", "")),
        cached_task,
    )
    log(f"brief ready in {time.time() - started:.2f}s ({len(brief.text)} chars)")
    if brief.task != cached_task:
        label.save_task(session_id, brief.task)
    with speech_lock():
        # Checked again here: mute may have been switched on while this was queued.
        if config.is_muted():
            log("muted while queued, dropped")
            return
        speak(
            label.announcement(label.spoken_project(payload.get("cwd", "")), brief.task), brief.text
        )
    log(f"finished {time.time() - started:.2f}s after stop")


def main() -> None:
    try:
        run(json.loads(sys.stdin.buffer.read()))
    except Exception as exc:  # noqa: BLE001 - nothing is watching this process, so log it
        log(f"worker failed: {type(exc).__name__}")


if __name__ == "__main__":
    main()
