import os
import subprocess
from types import SimpleNamespace

import pytest

from jarvis_voice import brief, config


@pytest.fixture(autouse=True)
def claude_is_installed(monkeypatch):
    """CI machines have no claude command, and these tests supply a fake runner anyway."""
    monkeypatch.setattr(brief.system, "find_claude", lambda: "claude")


def ok(text):
    return lambda *a, **k: SimpleNamespace(returncode=0, stdout=text)


def boom(*a, **k):
    raise subprocess.TimeoutExpired("claude", 30)


def test_clean_removes_unspeakable_things():
    raw = "# Done\n\n**Fixed** `a.py` in /src/app/a.py:12 \u2014 see [docs](https://x.io).\n```py\nx=1\n```"
    out = brief.clean(raw)
    for bad in ("#", "*", "`", "/src", "https", "x=1", "\u2014", "]("):
        assert bad not in out
    assert "Fixed" in out and "docs" in out


def test_clean_keeps_and_or_and_fractions():
    assert brief.clean("Use and/or here, 3/4 passed.") == "Use and/or here, 3/4 passed."


def test_clean_drops_tables():
    assert "cell" not in brief.clean("Result.\n| a | b |\n| cell | cell |")


def test_clean_removes_windows_paths():
    assert brief.clean(r"Fixed C:\Users\me\app.py today.") == "Fixed today."
    assert brief.needs_summary(r"See C:\Users\me\app.py")


def test_cap_keeps_whole_sentences():
    assert brief.cap("One here. Two here. Three here.", 20) == "One here. Two here."


def test_cap_handles_one_long_sentence():
    out = brief.cap("word " * 100, 50)
    assert len(out) <= 51 and out.endswith(".")


def test_short_reply_with_a_known_task_skips_the_model():
    def fail(*a, **k):
        raise AssertionError("model should not be called")

    out = brief.make_brief("Tests pass.", "fix it", "login fix", fail)
    assert out == brief.Brief("login fix", "Tests pass.")


def test_short_reply_with_no_task_yet_still_gets_one():
    out = brief.make_brief("Tests pass.", "fix it", "", ok("TASK: login fix\nBRIEF: Tests pass."))
    assert out.task == "login fix"


def test_long_reply_returns_a_cleaned_task_and_brief():
    out = brief.make_brief(
        "x " * 200, run=ok("TASK: **login** fix.\nBRIEF: **Done** \u2014 all good.")
    )
    assert out == brief.Brief("login fix", "Done, all good.")


def test_multiline_brief_is_kept():
    out = brief.parse_summary("TASK: a fix\nBRIEF: One.\nTwo?", "")
    assert out.text == "One. Two?"


def test_unformatted_output_is_spoken_under_the_existing_task():
    assert brief.parse_summary("It's done.", "login fix") == brief.Brief("login fix", "It's done.")


def test_task_with_no_brief_uses_the_fallback_instead_of_reading_the_label():
    raw = "Build failed on step two. " + "More. " * 60
    out = brief.make_brief(raw, "fix", "", ok("TASK: build fix"))
    assert out.text == "Build failed on step two."


def test_code_forces_a_summary_even_when_short():
    assert brief.needs_summary("Run:\n```\nls\n```")
    assert brief.needs_summary("See /src/app.py")


def test_summary_failure_falls_back_and_keeps_the_question():
    raw = "Login is fixed. " + "Detail here. " * 40 + "Should I push it?"
    assert brief.make_brief(raw, run=boom).text == "Login is fixed. Should I push it?"


def test_nonzero_exit_falls_back():
    raw = "Build failed on step two. " + "More. " * 60
    failed = lambda *a, **k: SimpleNamespace(returncode=1, stdout="")  # noqa: E731
    out = brief.make_brief(raw, "fix", "build fix", failed)
    assert out == brief.Brief("build fix", "Build failed on step two.")


def test_empty_summary_falls_back():
    raw = "Build failed on step two. " + "More. " * 60
    assert brief.make_brief(raw, run=ok("  ")).text == "Build failed on step two."


def test_failure_never_logs_reply_text():
    brief.make_brief("SECRET-CLIENT-TEXT. " * 30, run=boom)
    assert "SECRET" not in config.LOG.read_text(encoding="utf-8")


def test_summary_call_is_isolated_from_hooks_and_tools():
    seen = {}

    def spy(cmd, **kwargs):
        prompt = cmd[cmd.index("--system-prompt-file") + 1]
        seen.update(cmd=cmd, env=kwargs["env"], input=kwargs["input"])
        seen.update(prompt=open(prompt, encoding="utf-8").read(), prompt_file=prompt)
        return SimpleNamespace(returncode=0, stdout="Done.")

    brief.summarise("hello", "my request", "old task", spy)
    assert seen["prompt"] == brief.SYSTEM_PROMPT
    assert not os.path.exists(seen["prompt_file"])
    assert seen["env"]["JARVIS_SUMMARY"] == "1"
    for flag in ("--setting-sources", "--strict-mcp-config", "--no-session-persistence"):
        assert flag in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("--tools") + 1] == ""
    for part in ("<reply>", "my request", "old task"):
        assert part in seen["input"]


def test_long_input_keeps_start_and_end():
    out = brief.trim_input("A" * 5000 + "B" * 5000)
    assert out.startswith("A") and out.endswith("B") and len(out) < 6100


def test_missing_claude_command_falls_back(monkeypatch):
    raw = "Build failed on step two. " + "More. " * 60

    def missing():
        raise FileNotFoundError("claude")

    monkeypatch.setattr(brief.system, "find_claude", missing)
    assert brief.make_brief(raw).text == "Build failed on step two."
