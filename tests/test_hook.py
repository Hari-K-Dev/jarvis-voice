from jarvis_voice.hook import skip_reason

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
