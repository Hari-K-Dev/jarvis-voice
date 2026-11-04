import json
import os

from jarvis_voice import config, label, worker
from jarvis_voice.brief import Brief


def _user(content, **extra):
    return json.dumps({"type": "user", "message": {"content": content}, **extra})


def _transcript(tmp_path, *rows):
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(rows) + "\n")
    return str(path)


def test_last_request_skips_everything_the_person_did_not_type(tmp_path):
    path = _transcript(
        tmp_path,
        _user("fix the delivery policy"),
        _user([{"type": "tool_result", "content": "NOT THIS"}], toolUseResult={}),
        _user("NOT THIS", isMeta=True),
        _user("NOT THIS", isSidechain=True),
        _user("<task-notification>\nNOT THIS\n</task-notification>"),
        _user("<local-command-stdout>NOT THIS</local-command-stdout>"),
        json.dumps({"type": "assistant", "message": {"content": "NOT THIS"}}),
        "{broken json",
    )
    assert label.last_request(path) == "fix the delivery policy"


def test_last_request_reads_text_blocks_and_strips_reminders(tmp_path):
    content = [{"type": "text", "text": "<system-reminder>NO</system-reminder> ship it"}]
    assert label.last_request(_transcript(tmp_path, _user(content))) == "ship it"


def test_last_request_with_a_missing_file_is_empty(tmp_path):
    assert label.last_request(str(tmp_path / "gone.jsonl")) == ""
    assert label.last_request("") == ""


def test_spoken_project_uses_repo_root_and_tidies_the_folder_name(tmp_path):
    (tmp_path / "acme-ai_shop" / ".git").mkdir(parents=True)
    (tmp_path / "acme-ai_shop" / "src").mkdir()
    assert label.spoken_project(str(tmp_path / "acme-ai_shop" / "src")) == "acme ai shop"


def test_chosen_spoken_name_wins(tmp_path):
    (tmp_path / "acme-ai").mkdir()
    label.set_spoken_name("acme-ai", "Acme")
    assert label.spoken_project(str(tmp_path / "acme-ai")) == "Acme"


def test_corrupt_names_file_falls_back_to_the_folder(tmp_path):
    config.NAMES.write_text("{not json")
    (tmp_path / "alpha").mkdir()
    assert label.spoken_project(str(tmp_path / "alpha")) == "alpha"


def test_tasks_are_per_session_and_old_ones_expire():
    label.save_task("session-a", "login fix", now=1)
    label.save_task("session-b", "pricing page")
    assert label.load_task("session-a") == "login fix"
    assert label.load_task("session-b") == "pricing page"
    os.utime(config.TASKS / "session-a", (1, 1))
    label.save_task("session-b", "pricing page")
    assert label.load_task("session-a") == ""


def test_session_id_cannot_escape_the_tasks_folder():
    label.save_task("../../evil", "x")
    assert not (config.HOME.parent.parent / "evil").exists()
    assert label.load_task("../../evil") == ""


def test_announcement_handles_missing_parts():
    assert label.announcement("Acme", "login fix") == "Acme, login fix."
    assert label.announcement("Acme", "") == "Acme."
    assert label.announcement("", "") == ""


def test_every_brief_is_announced_first_and_the_task_is_remembered(tmp_path, monkeypatch):
    (tmp_path / "alpha").mkdir()
    spoken = []
    monkeypatch.setattr(worker, "make_brief", lambda *a: Brief("login fix", "It's done."))
    monkeypatch.setattr(worker, "speak", lambda *parts: spoken.append(parts))
    worker.run({"last_assistant_message": "x", "cwd": str(tmp_path / "alpha"), "session_id": "s1"})
    assert spoken == [("alpha, login fix.", "It's done.")]
    assert label.load_task("s1") == "login fix"


def test_muted_while_queued_says_nothing(tmp_path, monkeypatch):
    spoken = []
    config.MUTED.touch()
    monkeypatch.setattr(worker, "make_brief", lambda *a: Brief("t", "x"))
    monkeypatch.setattr(worker, "speak", lambda *parts: spoken.append(parts))
    worker.run({"last_assistant_message": "x", "cwd": str(tmp_path), "session_id": "s1"})
    assert spoken == []
