import subprocess
from types import SimpleNamespace

from jarvis_voice import brief, config


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


def test_cap_keeps_whole_sentences():
    assert brief.cap("One here. Two here. Three here.", 20) == "One here. Two here."


def test_cap_handles_one_long_sentence():
    out = brief.cap("word " * 100, 50)
    assert len(out) <= 51 and out.endswith(".")


def test_short_plain_reply_skips_the_model():
    def fail(*a, **k):
        raise AssertionError("model should not be called")

    assert brief.make_brief("Tests pass. Want me to push?", fail) == "Tests pass. Want me to push?"


def test_long_reply_uses_the_model_and_its_output_is_cleaned():
    assert brief.make_brief("x " * 200, ok("**Done** \u2014 all good.")) == "Done, all good."


def test_code_forces_a_summary_even_when_short():
    assert brief.needs_summary("Run:\n```\nls\n```")
    assert brief.needs_summary("See /src/app.py")


def test_summary_failure_falls_back_and_keeps_the_question():
    raw = "Login is fixed. " + "Detail here. " * 40 + "Should I push it?"
    assert brief.make_brief(raw, boom) == "Login is fixed. Should I push it?"


def test_nonzero_exit_falls_back():
    raw = "Build failed on step two. " + "More. " * 60
    out = brief.make_brief(raw, lambda *a, **k: SimpleNamespace(returncode=1, stdout=""))
    assert out == "Build failed on step two."


def test_empty_summary_falls_back():
    raw = "Build failed on step two. " + "More. " * 60
    assert brief.make_brief(raw, ok("  ")) == "Build failed on step two."


def test_failure_never_logs_reply_text():
    brief.make_brief("SECRET-CLIENT-TEXT. " * 30, boom)
    assert "SECRET" not in config.LOG.read_text()


def test_summary_call_is_isolated_from_hooks_and_tools():
    seen = {}

    def spy(cmd, **kwargs):
        seen.update(cmd=cmd, env=kwargs["env"], input=kwargs["input"])
        return SimpleNamespace(returncode=0, stdout="Done.")

    brief.summarise("hello", spy)
    assert seen["env"]["JARVIS_SUMMARY"] == "1"
    for flag in ("--setting-sources", "--strict-mcp-config", "--no-session-persistence"):
        assert flag in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("--tools") + 1] == ""
    assert "<reply>" in seen["input"]


def test_long_input_keeps_start_and_end():
    out = brief.trim_input("A" * 5000 + "B" * 5000)
    assert out.startswith("A") and out.endswith("B") and len(out) < 6100
