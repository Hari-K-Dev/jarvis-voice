"""The jarvis command: mute, unmute, name, status, say, test, install, uninstall."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config, label, system
from .brief import make_brief
from .speech import speak, speech_lock, stop_playback

SETTINGS = Path(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser() / "settings.json"
BIN_DIR = Path(os.environ.get("JARVIS_BIN_DIR") or "~/.local/bin").expanduser()
LEGACY_HOOK_NAME = "jarvis-hook"
HOOK_MODULE = "jarvis_voice.hook"
SAMPLE = """I fixed the login bug in `src/auth.ts:42`. The session cookie was expiring early.

- All 212 tests pass
- I haven't pushed it to main

Do you want me to push it?"""


def hook_entry() -> dict:
    """Runs with no shell, so paths need no quoting on any platform, including Windows."""
    return {
        "type": "command",
        "command": sys.executable,
        "args": ["-I", "-m", HOOK_MODULE],
        "timeout": 5,
    }


def _is_ours(group: dict) -> bool:
    return any(
        LEGACY_HOOK_NAME in h.get("command", "") or HOOK_MODULE in h.get("args", [])
        for h in group.get("hooks", [])
    )


def add_hook(settings: dict, entry: dict) -> bool:
    """Returns False if already up to date. Other hooks are left untouched."""
    stops = settings.setdefault("hooks", {}).setdefault("Stop", [])
    wanted = {"hooks": [entry]}
    if wanted in stops:
        return False
    stops[:] = [group for group in stops if not _is_ours(group)]
    stops.append(wanted)
    return True


def load_settings(path: Path | None = None) -> dict:
    """A missing file is fine on a new machine. A broken one is left for the person to fix."""
    path = path or SETTINGS
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except ValueError as exc:
        raise SystemExit(f"{path} is not valid JSON, so it was left alone: {exc}") from exc
    if not isinstance(settings, dict):
        raise SystemExit(f"{path} is not a JSON object, so it was left alone")
    return settings


def remove_hook(settings: dict) -> bool:
    stops = settings.get("hooks", {}).get("Stop", [])
    kept = [group for group in stops if not _is_ours(group)]
    if len(kept) == len(stops):
        return False
    settings["hooks"]["Stop"] = kept
    return True


def write_settings(settings: dict, path: Path | None = None) -> None:
    """Backs up first, then replaces atomically so a crash cannot corrupt the file."""
    path = path or SETTINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    if existed:
        shutil.copy2(path, path.with_name(f"{path.name}.bak-jarvis-{int(time.time())}"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".settings-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")
    if existed:
        os.chmod(tmp, path.stat().st_mode)
    os.replace(tmp, path)


def fetch_models() -> None:
    curl = system.which("curl")
    if not curl:
        raise SystemExit("curl is needed to download the voice model. Please install it first.")
    config.ensure_home()
    config.MODELS.mkdir(parents=True, exist_ok=True)
    for name, expected in config.MODEL_FILES.items():
        target = config.model_path(name)
        if target.exists() and _sha256(target) == expected:
            print(f"model ok: {name}")
            continue
        partial = target.with_suffix(".part")
        print(f"downloading {name}")
        try:
            subprocess.run(
                [curl, "-fL", "--retry", "2", "-o", str(partial), f"{config.MODEL_BASE}/{name}"],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            partial.unlink(missing_ok=True)
            raise SystemExit(f"could not download {name}, curl exited {exc.returncode}") from exc
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


def link_files() -> dict[Path, str | None]:
    """Files that put jarvis on PATH. None means a symlink, which Windows restricts."""
    executable = Path(sys.executable).with_name("jarvis")
    if system.is_windows():
        target = executable.with_suffix(".exe")
        return {
            BIN_DIR / "jarvis.cmd": f'@"{target}" %*\n',
            BIN_DIR / "jarvis": f'#!/bin/sh\nexec "{target.as_posix()}" "$@"\n',
        }
    return {BIN_DIR / "jarvis": None}


def write_links() -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in link_files().items():
        path.unlink(missing_ok=True)
        if content is None:
            path.symlink_to(Path(sys.executable).with_name("jarvis"))
        else:
            path.write_text(content, encoding="utf-8")
        print(f"command linked: {path}")
    if str(BIN_DIR) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"Add {BIN_DIR} to your PATH to use the jarvis command.")


def install() -> None:
    fetch_models()
    settings = load_settings()
    if add_hook(settings, hook_entry()):
        write_settings(settings)
        print("Stop hook added")
    else:
        print("Stop hook already present")
    write_links()
    if not system.player_command("x"):
        print("No audio player found. Install one of: paplay, pw-play, aplay, ffplay.")


def uninstall() -> None:
    settings = load_settings()
    if remove_hook(settings):
        write_settings(settings)
        print("Stop hook removed")
    for path in link_files():
        path.unlink(missing_ok=True)
    print(f"Models kept in {config.MODELS}. Delete that folder to free 340 MB.")


def status() -> None:
    hooked = any(_is_ours(g) for g in load_settings().get("hooks", {}).get("Stop", []))
    models = all(config.model_path(name).exists() for name in config.MODEL_FILES)
    player = system.player_command("x")
    print(f"voice:  {config.VOICE}")
    print(f"muted:  {'yes' if config.is_muted() else 'no'}")
    print(f"hook:   {'installed' if hooked else 'not installed'}")
    print(f"models: {'present' if models else 'missing'}")
    print(f"audio:  {player[0] if player else 'no player found'}")
    print(f"log:    {config.LOG}")


def main() -> None:
    # A Windows console's code page cannot show every character a brief might hold.
    sys.stdout.reconfigure(errors="replace")
    args = sys.argv[1:]
    command = args[0] if args else "status"
    if command == "mute":
        config.ensure_home()
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
        brief = make_brief(SAMPLE, "Please fix the login bug")
        heading = label.announcement(label.spoken_project(os.getcwd()), brief.task)
        print(f"Spoken: {heading} ... {brief.text}")
        with speech_lock():
            speak(heading, brief.text)
    elif command == "name" and len(args) > 1:
        folder = label.project_name(os.getcwd())
        label.set_spoken_name(folder, " ".join(args[1:]))
        print(f"{folder} will be announced as: {' '.join(args[1:])}")
    elif command == "install":
        install()
    elif command == "uninstall":
        uninstall()
    else:
        raise SystemExit(
            "usage: jarvis [status|mute|unmute|name SPOKEN|say TEXT|test|install|uninstall]"
        )


if __name__ == "__main__":
    main()
