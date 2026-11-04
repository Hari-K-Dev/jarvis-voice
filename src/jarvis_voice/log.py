"""Metadata-only log. Reply text is never written, because it can hold client work.

Log exception types, not messages: a message can quote the text being spoken, as
subprocess.TimeoutExpired does with its command line.
"""

import os
import time

from . import config, system

MAX_BYTES = 1_000_000


def log(line: str) -> None:
    try:
        config.ensure_home()
        if config.LOG.exists() and config.LOG.stat().st_size > MAX_BYTES:
            config.LOG.unlink()
        fd = os.open(config.LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        system.restrict(config.LOG, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    except OSError:
        pass
