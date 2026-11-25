"""Detached process that produces and speaks one brief. Reads the hook payload on stdin."""

import json
import sys
import time

from . import config, label
from .brief import Brief, make_brief
from .log import log
from .speech import speak, speech_lock


def prepare(payload: dict) -> tuple[str, Brief]:
    """The announcement and brief for one finished turn, for the speakers or a voice note."""
    session_id = payload.get("session_id", "")
    cached_task = label.load_task(session_id)
    brief = make_brief(
        payload["last_assistant_message"],
        label.last_request(payload.get("transcript_path", "")),
        cached_task,
    )
    if brief.task != cached_task:
        label.save_task(session_id, brief.task)
    return label.announcement(label.spoken_project(payload.get("cwd", "")), brief.task), brief


def run(payload: dict) -> None:
    started = time.time()
    heading, brief = prepare(payload)
    log(f"brief ready in {time.time() - started:.2f}s ({len(brief.text)} chars)")
    with speech_lock():
        # Checked again here: either may have been switched on while this was queued.
        if config.is_muted() or config.is_away():
            log("muted while queued, dropped")
            return
        speak(heading, brief.text)
    log(f"finished {time.time() - started:.2f}s after stop")


def main() -> None:
    try:
        run(json.loads(sys.stdin.buffer.read()))
    except Exception as exc:  # noqa: BLE001 - nothing is watching this process, so log it
        log(f"worker failed: {type(exc).__name__}")


if __name__ == "__main__":
    main()
