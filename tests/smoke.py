"""End-to-end check for CI. Needs the voice model, so it is not part of the unit tests.

Installs into a clean config, runs the hook exactly as Claude Code would (no shell), and
waits for a real brief to be synthesised. Audio devices are absent on CI, so playback itself
is the one thing this cannot prove.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def jarvis(*args: str) -> str:
    command = [sys.executable, "-m", "jarvis_voice.cli", *args]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def main() -> None:
    config_dir = Path(os.environ["CLAUDE_CONFIG_DIR"])
    home = Path(os.environ["JARVIS_HOME"])
    # Refuse to run against real settings or links, because this ends by uninstalling.
    assert os.environ.get("JARVIS_BIN_DIR"), "set JARVIS_BIN_DIR to a throwaway folder"
    assert config_dir != Path.home() / ".claude", "set CLAUDE_CONFIG_DIR to a throwaway folder"
    # An old log would satisfy the checks below without this run having done anything.
    (home / "jarvis.log").unlink(missing_ok=True)
    print(jarvis("install"))
    assert "already present" in jarvis("install"), "second install should change nothing"
    assert "installed" in jarvis("status")

    settings = json.loads((config_dir / "settings.json").read_text(encoding="utf-8"))
    hook = settings["hooks"]["Stop"][0]["hooks"][0]

    project = Path(tempfile.mkdtemp())
    (project / ".git").mkdir()
    payload = {
        "session_id": "smoke",
        "cwd": str(project),
        "transcript_path": "",
        "last_assistant_message": "Caf\u00e9 fix done \u2713. " + "Detail here. " * 30 + "Push it?",
    }
    env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "cli"}
    started = time.time()
    subprocess.run(
        [hook["command"], *hook["args"]],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        cwd=project,
        env=env,
        check=True,
        timeout=20,
    )
    print(f"hook returned in {time.time() - started:.2f}s")

    log = home / "jarvis.log"
    while time.time() - started < 240:
        text = log.read_text(encoding="utf-8") if log.exists() else ""
        if "finished" in text or "worker failed" in text:
            break
        time.sleep(2)
    print(text)
    assert "synthesised" in text, "the voice did not produce audio"
    assert "finished" in text, "the worker did not finish"
    assert "worker failed" not in text and "kokoro failed" not in text
    assert "Caf" not in text, "reply text must never reach the log"

    jarvis("uninstall")
    assert "not installed" in jarvis("status")
    print("smoke test passed")


if __name__ == "__main__":
    main()
