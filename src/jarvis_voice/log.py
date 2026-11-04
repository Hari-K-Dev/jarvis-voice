"""Metadata-only log. Reply text is never written, because it can hold client work."""

import time

from . import config

MAX_BYTES = 1_000_000


def log(line: str) -> None:
    try:
        config.HOME.mkdir(parents=True, exist_ok=True)
        if config.LOG.exists() and config.LOG.stat().st_size > MAX_BYTES:
            config.LOG.unlink()
        with config.LOG.open("a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    except OSError:
        pass
