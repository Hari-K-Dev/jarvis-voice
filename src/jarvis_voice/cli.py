"""The jarvis command: mute, unmute, status, say, test, install, uninstall."""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config
from .brief import make_brief
from .speech import speak, speech_lock, stop_playback

SETTINGS = Path("~/.claude/settings.json").expanduser()
LINK = Path("~/.local/bin/jarvis").expanduser()
HOOK_NAME = "jarvis-hook"
SAMPLE = """I fixed the login bug in `src/auth.ts:42`. The session cookie was expiring early.

- All 212 tests pass
- I haven't pushed it to main

Do you want me to push it?"""


def hook_command() -> str:
    return shlex.quote(str(Path(sys.executable).with_name(HOOK_NAME)))


def _is_ours(group: dict) -> bool:
    return any(HOOK_NAME in h.get("command", "") for h in group.get("hooks", []))


def add_hook(settings: dict, command: str) -> bool:
    """Returns False if already present. Other hooks are left untouched."""
    stops = settings.setdefault("hooks", {}).setdefault("Stop", [])
    if any(_is_ours(group) for group in stops):
        return False
    stops.append({"hooks": [{"type": "command", "command": command, "timeout": 5}]})
    return True


def remove_hook(settings: dict) -> bool:
    stops = settings.get("hooks", {}).get("Stop", [])
    kept = [group for group in stops if not _is_ours(group)]
    if len(kept) == len(stops):
        return False
    settings["hooks"]["Stop"] = kept
    return True


def write_settings(settings: dict, path: Path = SETTINGS) -> None:
    """Backs up first, then replaces atomically so a crash cannot corrupt the file."""
    shutil.copy2(path, path.with_name(f"{path.name}.bak-jarvis-{int(time.time())}"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".settings-")
    with os.fdopen(fd, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.chmod(tmp, path.stat().st_mode)
    os.replace(tmp, path)


def fetch_models() -> None:
    config.MODELS.mkdir(parents=True, exist_ok=True)
    for name, expected in config.MODEL_FILES.items():
        target = config.model_path(name)
        if target.exists() and _sha256(target) == expected:
            print(f"model ok: {name}")
            continue
        partial = target.with_suffix(".part")
        print(f"downloading {name}")
        subprocess.run(
            ["curl", "-fL", "--retry", "2", "-o", str(partial), f"{config.MODEL_BASE}/{name}"],
            check=True,
        )
        if _sha256(partial) != expected:
            partial.unlink()
            raise SystemExit(f"checksum mismatch for {name}, not installed")
        partial.replace(target)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def install() -> None:
    fetch_models()
    settings = json.loads(SETTINGS.read_text())
    if add_hook(settings, hook_command()):
        write_settings(settings)
        print("Stop hook added")
    else:
        print("Stop hook already present")
    LINK.parent.mkdir(parents=True, exist_ok=True)
    LINK.unlink(missing_ok=True)
    LINK.symlink_to(Path(sys.executable).with_name("jarvis"))
    print(f"command linked: {LINK}")


def uninstall() -> None:
    settings = json.loads(SETTINGS.read_text())
    if remove_hook(settings):
        write_settings(settings)
        print("Stop hook removed")
    LINK.unlink(missing_ok=True)
    print(f"Models kept in {config.MODELS}. Delete that folder to free 340 MB.")


def status() -> None:
    settings = json.loads(SETTINGS.read_text())
    hooked = any(_is_ours(g) for g in settings.get("hooks", {}).get("Stop", []))
    models = all(config.model_path(name).exists() for name in config.MODEL_FILES)
    print(f"voice:  {config.VOICE}")
    print(f"muted:  {'yes' if config.is_muted() else 'no'}")
    print(f"hook:   {'installed' if hooked else 'not installed'}")
    print(f"models: {'present' if models else 'missing'}")
    print(f"log:    {config.LOG}")


def main() -> None:
    args = sys.argv[1:]
    command = args[0] if args else "status"
    if command == "mute":
        config.HOME.mkdir(parents=True, exist_ok=True)
        config.MUTED.touch()
        stop_playback()
        print("Muted.")
    elif command == "unmute":
        config.MUTED.unlink(missing_ok=True)
        print("Unmuted.")
    elif command == "status":
        status()
    elif command == "say" and len(args) > 1:
        with speech_lock():
            speak(" ".join(args[1:]))
    elif command == "test":
        brief = make_brief(SAMPLE)
        print(f"Spoken: {brief}")
        with speech_lock():
            speak(brief)
    elif command == "install":
        install()
    elif command == "uninstall":
        uninstall()
    else:
        raise SystemExit("usage: jarvis [status|mute|unmute|say TEXT|test|install|uninstall]")


if __name__ == "__main__":
    main()
