import io
import json
import os
import subprocess

import pytest

from jarvis_voice import config, hook
from jarvis_voice.hook import skip_reason, worker_command

CLI = {"CLAUDE_CODE_ENTRYPOINT": "cli"}
MSG = {"last_assistant_message": "Done."}


def test_interactive_reply_is_spoken():
    assert skip_reason(MSG, CLI, False) is None


def test_summary_session_never_speaks_so_it_cannot_loop():
    assert skip_reason(MSG, {**CLI, "JARVIS_SUMMARY": "1"}, False) == "summary session"


def test_headless_sessions_stay_silent():
    assert skip_reason(MSG, {"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}, False)
    assert skip_reason(MSG, {}, False)


def test_muted_stays_silent():
    assert skip_reason(MSG, CLI, True) == "muted"


def test_continuations_and_empty_messages_stay_silent():
    assert skip_reason({**MSG, "stop_hook_active": True}, CLI, False)
    assert skip_reason({"last_assistant_message": "  "}, CLI, False)
    assert skip_reason({}, CLI, False)


def test_worker_ignores_decoy_code_in_the_project(tmp_path):
    """Regression: python -m put the session's project first on sys.path."""
    project = tmp_path / "project"
    decoy = project / "jarvis_voice"
    decoy.mkdir(parents=True)
    marker = tmp_path / "pwned"
    code = f"open({str(marker)!r}, 'w').close()\n"
    (decoy / "__init__.py").write_text(code)
    (decoy / "worker.py").write_text(code)
    home = tmp_path / "home"
    subprocess.run(
        worker_command(),
        input="not json",  # the real worker logs this and exits without speaking
        text=True,
        cwd=project,
        env={**os.environ, "JARVIS_HOME": str(home), "PYTHONPATH": str(project)},
        check=True,
    )
    assert not marker.exists()
    assert "worker failed: JSONDecodeError" in (home / "jarvis.log").read_text()


def test_hook_starts_the_worker_outside_the_project(monkeypatch):
    seen = {}

    class FakeWorker:
        stdin = io.StringIO()

    def fake_popen(cmd, **kwargs):
        seen.update(cmd=cmd, cwd=kwargs["cwd"])
        return FakeWorker()

    monkeypatch.setattr(hook.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(hook.sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(MSG).encode())))
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.delenv("JARVIS_SUMMARY", raising=False)
    with pytest.raises(SystemExit):
        hook.main()
    assert "-I" in seen["cmd"] and seen["cwd"] == config.HOME


def test_hook_decodes_stdin_as_utf8_on_any_platform(monkeypatch):
    """Regression: text-mode stdin uses the local code page on Windows."""
    seen = {}

    class FakeWorker:
        stdin = io.StringIO()

    monkeypatch.setattr(hook.subprocess, "Popen", lambda *a, **k: FakeWorker())
    monkeypatch.setattr(hook, "skip_reason", lambda p, e, m: seen.update(p) or "stop")
    raw = json.dumps({"last_assistant_message": "caf\u00e9"}, ensure_ascii=False).encode("utf-8")
    monkeypatch.setattr(hook.sys, "stdin", io.TextIOWrapper(io.BytesIO(raw), encoding="cp1252"))
    with pytest.raises(SystemExit):
        hook.main()
    assert seen["last_assistant_message"] == "caf\u00e9"
