"""Detached process that produces and speaks one brief. Reads the hook payload on stdin."""

import json
import sys
import time

from . import config
from .brief import make_brief
from .log import log
from .speech import speak, speech_lock, with_project_prefix


def run(payload: dict) -> None:
    started = time.time()
    brief = make_brief(payload["last_assistant_message"])
    log(f"brief ready in {time.time() - started:.2f}s ({len(brief)} chars)")
    with speech_lock():
        # Checked again here: mute may have been switched on while this was queued.
        if config.is_muted():
            log("muted while queued, dropped")
            return
        speak(with_project_prefix(brief, payload.get("cwd", "")))
    log(f"finished {time.time() - started:.2f}s after stop")


def main() -> None:
    try:
        run(json.load(sys.stdin))
    except Exception as exc:  # noqa: BLE001 - nothing is watching this process, so log it
        log(f"worker failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
